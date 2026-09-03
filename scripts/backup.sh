#!/usr/bin/env bash
set -Eeuo pipefail

# Backups contain Game.ini and may therefore contain server/admin passwords.
# docker exec does not run the image entrypoint, so enforce a private mask here.
umask 0077

if (( EUID == 0 )); then
  exec gosu nos:nos "$0" "$@"
fi

DATA_DIR="${DATA_DIR:-/data}"
SAVED_DIR="${SAVED_DIR:-${DATA_DIR}/saved}"
BACKUP_DIR="${BACKUP_DIR:-${DATA_DIR}/backups}"
KEEP_BACKUPS="${KEEP_BACKUPS:-5}"
[[ "$KEEP_BACKUPS" =~ ^[0-9]+$ ]] || { echo "KEEP_BACKUPS must be a non-negative integer" >&2; exit 2; }
[[ "$SAVED_DIR" = /* && "$SAVED_DIR" != / ]] || { echo "SAVED_DIR must be an absolute path other than /" >&2; exit 2; }
[[ -d "$SAVED_DIR" ]] || { echo "saved directory not found: $SAVED_DIR" >&2; exit 2; }
data_root="$(realpath -m -- "$DATA_DIR")"
saved_root="$(realpath -m -- "$SAVED_DIR")"
[[ "$data_root" != / ]] || { echo "DATA_DIR must not resolve to /" >&2; exit 2; }
case "$saved_root" in
  "$data_root"/*) ;;
  *) echo "SAVED_DIR must be located below DATA_DIR ($data_root)" >&2; exit 2 ;;
esac
SAVED_DIR="$saved_root"
mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
archive="${BACKUP_DIR}/saved-${timestamp}.tar.gz"
temporary="$(mktemp "${BACKUP_DIR}/.saved-${timestamp}.XXXXXX.tmp")"
cleanup() { rm -f -- "$temporary"; }
trap cleanup EXIT
tar -C "$SAVED_DIR" \
  --transform='s|^\./|saved/|;s|^\.$|saved|' \
  -czf "$temporary" .
chmod 0600 "$temporary"
mv -f -- "$temporary" "$archive"
trap - EXIT
printf 'Created %s\n' "$archive"
if (( KEEP_BACKUPS > 0 )); then
  mapfile -d '' -t old < <(
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'saved-*.tar.gz' -printf '%T@\t%p\0' \
      | sort -z -nr -k1,1 \
      | tail -z -n "+$((KEEP_BACKUPS + 1))" \
      | cut -z -f2-
  )
  ((${#old[@]} == 0)) || rm -f -- "${old[@]}"
fi
