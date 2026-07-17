#!/usr/bin/env bash
set -Eeuo pipefail

if (( EUID == 0 )); then
  exec gosu nos:nos "$0" "$@"
fi

DATA_DIR="${DATA_DIR:-/data}"
BACKUP_DIR="${BACKUP_DIR:-${DATA_DIR}/backups}"
KEEP_BACKUPS="${KEEP_BACKUPS:-5}"
[[ "$KEEP_BACKUPS" =~ ^[0-9]+$ ]] || { echo "KEEP_BACKUPS must be a non-negative integer" >&2; exit 2; }
[[ -d "${DATA_DIR}/saved" ]] || { echo "saved directory not found: ${DATA_DIR}/saved" >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
archive="${BACKUP_DIR}/saved-${timestamp}.tar.gz"
tar -C "$DATA_DIR" -czf "$archive" saved
chmod 0600 "$archive"
printf 'Created %s\n' "$archive"
mapfile -t old < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'saved-*.tar.gz' -printf '%T@ %p\n' | sort -nr | awk -v keep="$KEEP_BACKUPS" 'NR>keep {$1=""; sub(/^ /,""); print}')
((${#old[@]} == 0)) || rm -f -- "${old[@]}"
