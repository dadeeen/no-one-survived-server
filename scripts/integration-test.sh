#!/usr/bin/env bash
set -Eeuo pipefail

name=no-one-survived-integration
data_dir="${PWD}/.integration-data"
rm -rf "$data_dir"
mkdir -p "$data_dir"
docker rm -f "$name" >/dev/null 2>&1 || true

show_diagnostics() {
  echo "=== Integration container status ==="
  if docker inspect "$name" >/dev/null 2>&1; then
    docker exec "$name" nosctl status || true
    echo "=== Integration container logs ==="
    docker logs "$name" || true
  else
    echo "Integration container is unavailable" >&2
  fi
}

cleanup() {
  local status=$?
  trap - EXIT
  if (( status != 0 )); then
    echo "Integration test failed with exit code ${status}" >&2
    show_diagnostics
  fi
  if (( status == 0 )); then
    docker rm -f "$name" >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup EXIT

docker run -d \
  --name "$name" \
  -p 17777:7777/udp \
  -p 37015:27015/udp \
  -e PUID=1000 \
  -e PGID=1000 \
  -e USE_XVFB=true \
  -e UPDATE_ON_CONTAINER_START=true \
  -e PREPARE_ON_CONTAINER_START=true \
  -e START_SERVER_ON_CONTAINER_START=false \
  -e AUTO_SLEEP_ENABLED=true \
  -e IDLE_TIMEOUT_SECONDS=300 \
  -e MIN_UPTIME_SECONDS=0 \
  -e WAKE_SOURCE_POLICY=private \
  -e WAKE_ALLOWED_NETWORKS= \
  -e ADMIN_PASSWORD=integration-only-password \
  -v "$data_dir:/data" \
  nos-integration:local

wait_for_state() {
  local wanted="$1" timeout="$2" elapsed=0 state=""
  while (( elapsed < timeout )); do
    if [[ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" != true ]]; then
      echo "Integration container stopped while waiting for state(s): $wanted" >&2
      return 1
    fi
    state="$(docker exec "$name" nosctl status 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("state", ""))' 2>/dev/null || true)"
    case ",$wanted," in
      *",$state,"*) return 0 ;;
    esac
    if [[ "$state" == ERROR ]]; then
      echo "Integration container entered ERROR while waiting for state(s): $wanted" >&2
      return 1
    fi
    sleep 10
    elapsed=$((elapsed + 10))
  done
  echo "Timed out waiting for state(s): $wanted; last state: ${state:-unknown}" >&2
  return 1
}

require_file() {
  local path="$1" description="$2"
  [[ -f "$path" ]] || {
    echo "Missing ${description}: $path" >&2
    return 1
  }
}

require_symlink() {
  local path="$1" description="$2"
  [[ -L "$path" ]] || {
    echo "Missing ${description} symlink: $path" >&2
    return 1
  }
}

require_directory() {
  local path="$1" description="$2"
  [[ -d "$path" ]] || {
    echo "Missing ${description} directory: $path" >&2
    return 1
  }
}

echo "Waiting for SteamCMD installation and sleeping state..."
wait_for_state "SLEEPING" 5400

require_file "$data_dir/server/WRSH/Binaries/Win64/WRSHServer.exe" "dedicated server executable"
require_file "$data_dir/wine/system.reg" "Wine registry"
require_symlink "$data_dir/server/WRSH/Saved" "persistent save"

echo "Sending UDP wake packet through the published query port..."
python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.sendto(b'\xff\xff\xff\xffTSource Engine Query\x00', ('127.0.0.1', 37015))
PY

wait_for_state "STARTING,RUNNING,IDLE" 300

if [[ "${FULL_RUNTIME:-false}" == "true" ]]; then
  echo "Waiting for a successful real A2S response..."
  elapsed=0
  ok=false
  while (( elapsed < 1200 )); do
    ok="$(docker exec "$name" nosctl status 2>/dev/null | python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("a2s_ok", False)).lower())' 2>/dev/null || true)"
    [[ "$ok" == true ]] && break
    sleep 10
    elapsed=$((elapsed + 10))
  done
  [[ "$ok" == true ]] || { echo "No successful A2S response" >&2; exit 1; }
fi

echo "Requesting graceful sleep..."
docker exec "$name" nosctl sleep >/dev/null
wait_for_state "SLEEPING" 180

require_directory "$data_dir/saved" "persistent save"
echo "Integration test completed"
