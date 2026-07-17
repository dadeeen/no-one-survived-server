#!/usr/bin/env bash
set -Eeuo pipefail

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
DATA_DIR="${DATA_DIR:-/data}"
RUNTIME_DIR="${RUNTIME_DIR:-/run/nos}"
STEAMCMD_DIR="${STEAMCMD_DIR:-${DATA_DIR}/steamcmd}"
UMASK="${UMASK:-0027}"
FIX_PERMISSIONS_VALUE="${FIX_PERMISSIONS:-true}"
FIX_PERMISSIONS_VALUE="${FIX_PERMISSIONS_VALUE,,}"

[[ "$PUID" =~ ^[0-9]+$ ]] && (( PUID > 0 )) || { echo "PUID must be a positive integer" >&2; exit 2; }
[[ "$PGID" =~ ^[0-9]+$ ]] && (( PGID > 0 )) || { echo "PGID must be a positive integer" >&2; exit 2; }
[[ "$UMASK" =~ ^0?[0-7]{3}$ ]] || { echo "UMASK must be a three- or four-digit octal mask" >&2; exit 2; }
case "$FIX_PERMISSIONS_VALUE" in
  1|true|yes|on|y) FIX_PERMISSIONS_VALUE=true ;;
  0|false|no|off|n) FIX_PERMISSIONS_VALUE=false ;;
  *) echo "FIX_PERMISSIONS must be a boolean" >&2; exit 2 ;;
esac
umask "$UMASK"
[[ "$DATA_DIR" == /* && "$DATA_DIR" != / ]] || { echo "DATA_DIR must be an absolute path other than /" >&2; exit 2; }
[[ "$RUNTIME_DIR" == /* && "$RUNTIME_DIR" != / ]] || { echo "RUNTIME_DIR must be an absolute path other than /" >&2; exit 2; }
DATA_REAL="$(realpath -m "$DATA_DIR")"
RUNTIME_REAL="$(realpath -m "$RUNTIME_DIR")"
STEAMCMD_REAL="$(realpath -m "$STEAMCMD_DIR")"
[[ "$DATA_REAL" != / && "$RUNTIME_REAL" != / ]] || { echo "DATA_DIR and RUNTIME_DIR must not resolve to /" >&2; exit 2; }
[[ "$STEAMCMD_REAL" == "$DATA_REAL"/* ]] || { echo "STEAMCMD_DIR must be below DATA_DIR" >&2; exit 2; }
DATA_DIR="$DATA_REAL"
RUNTIME_DIR="$RUNTIME_REAL"
STEAMCMD_DIR="$STEAMCMD_REAL"

if getent group nos >/dev/null 2>&1; then
  groupmod -o -g "$PGID" nos
else
  groupadd -o -g "$PGID" nos
fi
if id nos >/dev/null 2>&1; then
  usermod -o -u "$PUID" -g "$PGID" -d "${DATA_DIR}/home" nos
else
  useradd -o -u "$PUID" -g "$PGID" -d "${DATA_DIR}/home" -s /bin/bash nos
fi

mkdir -p "$DATA_DIR" "$RUNTIME_DIR" "${DATA_DIR}/home" "$STEAMCMD_DIR"
if [[ ! -x "${STEAMCMD_DIR}/steamcmd.sh" ]]; then
  echo "[entrypoint] Installing SteamCMD bootstrap into ${STEAMCMD_DIR}"
  cp -a /opt/steamcmd-bootstrap/. "$STEAMCMD_DIR/"
  chown -R "$PUID:$PGID" "$STEAMCMD_DIR"
fi
chown "$PUID:$PGID" "$DATA_DIR" "${DATA_DIR}/home" "$STEAMCMD_DIR"

if [[ "$FIX_PERMISSIONS_VALUE" == true ]]; then
  marker="${DATA_DIR}/.ownership-${PUID}-${PGID}"
  if [[ ! -e "$marker" ]]; then
    echo "[entrypoint] Applying ownership ${PUID}:${PGID} to persistent data"
    chown -R "$PUID:$PGID" "$DATA_DIR"
    rm -f "${DATA_DIR}"/.ownership-*
    touch "$marker"
    chown "$PUID:$PGID" "$marker"
  fi
fi
chown -R "$PUID:$PGID" "$RUNTIME_DIR"
chmod 0750 "$RUNTIME_DIR"

if [[ -n "${TZ:-}" ]]; then
  zoneinfo_root=/usr/share/zoneinfo
  case "$TZ" in
    /*|*..*|*//*) echo "Unknown TZ value: ${TZ}" >&2; exit 2 ;;
  esac
  zoneinfo_path="$(realpath -e "${zoneinfo_root}/${TZ}" 2>/dev/null)" || {
    echo "Unknown TZ value: ${TZ}" >&2
    exit 2
  }
  [[ "$zoneinfo_path" == "$zoneinfo_root"/* && -f "$zoneinfo_path" ]] || {
    echo "Unknown TZ value: ${TZ}" >&2
    exit 2
  }
  ln -snf "$zoneinfo_path" /etc/localtime
  echo "$TZ" >/etc/timezone
fi

export HOME="${DATA_DIR}/home"
export USER=nos LOGNAME=nos
export PYTHONUNBUFFERED=1
export PYTHONPATH=/opt/nos/src

exec gosu nos:nos "$@"
