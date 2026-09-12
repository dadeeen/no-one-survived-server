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
backup_root="$(realpath -m -- "$BACKUP_DIR")"
case "$backup_root" in
  "$saved_root"|"$saved_root"/*) echo "BACKUP_DIR must not be inside SAVED_DIR" >&2; exit 2 ;;
esac
exec 9>"$data_root/.nos-maintenance.lock"
flock -n 9 || { echo "data is busy; put the game to sleep and retry after maintenance" >&2; exit 1; }
# Validate again after acquiring the lock: a restore may have swapped the tree.
[[ -d "$SAVED_DIR" ]] || { echo "saved directory not found: $SAVED_DIR" >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y-%m-%d_%H-%M-%S)"
temporary="$(mktemp "${BACKUP_DIR}/.saved-${timestamp}.XXXXXX.tmp")"
archive="${BACKUP_DIR}/$(basename "${temporary%.tmp}" | cut -c2-).tar.gz"
cleanup() { rm -f -- "$temporary"; }
trap cleanup EXIT
tar -C "$SAVED_DIR" \
  --transform='s|^\./|saved/|;s|^\.$|saved|' \
  -czf "$temporary" .
chmod 0600 "$temporary"
# A hard link publishes the completed archive atomically without overwriting.
ln -- "$temporary" "$archive"
rm -- "$temporary"
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
