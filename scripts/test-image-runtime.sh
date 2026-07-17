#!/usr/bin/env bash
set -Eeuo pipefail

expected_wine_major="${EXPECTED_WINE_MAJOR:-11}"

required_commands=(
  bash
  find
  getent
  gosu
  groupadd
  gzip
  python3
  tar
  tini
  useradd
  wine
  wineboot
  wineserver
  xvfb-run
)
for command_name in "${required_commands[@]}"; do
  command -v "$command_name" >/dev/null || {
    echo "missing runtime command: $command_name" >&2
    exit 1
  }
done

[[ "$(dpkg --print-architecture)" == "amd64" ]] || {
  echo "runtime image must be amd64" >&2
  exit 1
}
dpkg --print-foreign-architectures | grep -qx i386 || {
  echo "i386 multiarch support is missing" >&2
  exit 1
}

wine_version="$(wine --version)"
[[ "$wine_version" =~ ^wine-${expected_wine_major}([.]|$) ]] || {
  echo "unexpected Wine version: $wine_version" >&2
  exit 1
}
[[ -s /usr/local/share/nos/wine-package-version ]] || {
  echo "Wine package provenance file is missing" >&2
  exit 1
}
[[ -s /usr/local/share/nos/steamcmd-bootstrap-sha256 ]] || {
  echo "SteamCMD bootstrap provenance file is missing" >&2
  exit 1
}
[[ ! -e /ampstart.sh ]] || {
  echo "AMP runtime artifact unexpectedly present" >&2
  exit 1
}

steamcmd_binary=/opt/steamcmd-bootstrap/linux32/steamcmd
[[ -x "$steamcmd_binary" ]] || {
  echo "SteamCMD bootstrap binary is missing" >&2
  exit 1
}
if ldd "$steamcmd_binary" | grep -q 'not found'; then
  ldd "$steamcmd_binary" >&2
  echo "SteamCMD has unresolved shared libraries" >&2
  exit 1
fi

tmp="$(mktemp -d)"
cleanup() { rm -rf "$tmp" 2>/dev/null || true; }
trap cleanup EXIT

if TZ=../../../etc/passwd \
  DATA_DIR="$tmp/entry-data" \
  RUNTIME_DIR="$tmp/entry-run" \
  /usr/local/bin/nos-entrypoint true >"$tmp/timezone.out" 2>&1; then
  echo "unsafe timezone path unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'Unknown TZ value' "$tmp/timezone.out"

chown nos:nos "$tmp"
install -d -m 0700 -o nos -g nos "$tmp/home" "$tmp/xdg" "$tmp/wine"
cp -a /opt/steamcmd-bootstrap "$tmp/steamcmd"
chown -R nos:nos "$tmp/steamcmd"

steamcmd_ok=false
for attempt in 1 2 3; do
  if gosu nos:nos env HOME="$tmp/home" "$tmp/steamcmd/steamcmd.sh" +quit; then
    steamcmd_ok=true
    break
  fi
  echo "SteamCMD smoke attempt $attempt failed" >&2
  sleep 5
done
[[ "$steamcmd_ok" == true ]] || {
  echo "SteamCMD smoke test failed after three attempts" >&2
  exit 1
}

printf '\n== Wine prefix initialization ==\n'
wine_env=(
  HOME="$tmp/home"
  USER=nos
  LOGNAME=nos
  WINEPREFIX="$tmp/wine"
  WINEARCH=win64
  WINEDEBUG=-all
  WINEDLLOVERRIDES="${WINEDLLOVERRIDES:-mscoree,mshtml,winemenubuilder.exe=}"
  XDG_RUNTIME_DIR="$tmp/xdg"
)
wine_init_script='
wineboot --init
wineboot_status=$?
wineserver -k || true
wineserver -w || true
exit "$wineboot_status"
'
gosu nos:nos env "${wine_env[@]}" \
  timeout 240s xvfb-run -a /bin/sh -c "$wine_init_script"
[[ -f "$tmp/wine/system.reg" ]] || {
  echo "Wine prefix initialization did not create system.reg" >&2
  exit 1
}

printf 'Runtime smoke test passed with %s (package %s, SteamCMD %s)\n' \
  "$wine_version" \
  "$(cat /usr/local/share/nos/wine-package-version)" \
  "$(cat /usr/local/share/nos/steamcmd-bootstrap-sha256)"
