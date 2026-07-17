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
    echo "=== Integration container logs (last 300 lines) ==="
    docker logs --tail 300 "$name" || true
  else
    echo "Integration container is unavailable" >&2
  fi
}

handle_exit() {
  local status=$?
  trap - EXIT
  if (( status != 0 )); then
    echo "Integration test failed with exit code ${status}" >&2
    show_diagnostics
  fi
  exit "$status"
}
trap handle_exit EXIT

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

require_container_path() {
  local test_flag="$1" path="$2" description="$3"
  if ! docker exec "$name" test "$test_flag" "$path"; then
    echo "Missing ${description} in container: $path" >&2
    return 1
  fi
}

require_container_symlink_target() {
  local path="$1" expected_target="$2" description="$3" actual_target
  actual_target="$(docker exec "$name" readlink -f "$path" 2>/dev/null || true)"
  if [[ "$actual_target" != "$expected_target" ]]; then
    echo "Invalid ${description} symlink in container: $path -> ${actual_target:-missing}; expected $expected_target" >&2
    return 1
  fi
}

echo "Waiting for SteamCMD installation and sleeping state..."
wait_for_state "SLEEPING" 5400

require_container_path -f /data/server/WRSH/Binaries/Win64/WRSHServer.exe "dedicated server executable"
require_container_path -f /data/wine/system.reg "Wine registry"
require_container_symlink_target /data/server/WRSH/Saved /data/saved "persistent save"

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

require_container_path -d /data/saved "persistent save directory"
echo "Integration test completed"
