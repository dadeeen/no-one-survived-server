#!/usr/bin/env bash
set -Eeuo pipefail
# Restores may contain Game.ini secrets; keep the staging tree private even
# when invoked through docker exec with a permissive default umask.
umask 0077
[[ $# -eq 1 ]] || { echo "usage: restore.sh BACKUP.tar.gz" >&2; exit 2; }

DATA_DIR="${DATA_DIR:-/data}"
SAVED_DIR="${SAVED_DIR:-${DATA_DIR}/saved}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
archive="$1"
[[ "$PUID" =~ ^[0-9]+$ ]] && (( PUID > 0 )) || { echo "PUID must be a positive integer" >&2; exit 2; }
[[ "$PGID" =~ ^[0-9]+$ ]] && (( PGID > 0 )) || { echo "PGID must be a positive integer" >&2; exit 2; }
[[ -d "$DATA_DIR" ]] || { echo "data directory not found: $DATA_DIR" >&2; exit 2; }
[[ "$SAVED_DIR" = /* && "$SAVED_DIR" != / ]] || { echo "SAVED_DIR must be an absolute path other than /" >&2; exit 2; }
[[ -f "$archive" ]] || { echo "backup not found: $archive" >&2; exit 2; }
archive="$(realpath "$archive")"
data_root="$(realpath -m -- "$DATA_DIR")"
saved_root="$(realpath -m -- "$SAVED_DIR")"
[[ "$data_root" != / ]] || { echo "DATA_DIR must not resolve to /" >&2; exit 2; }
case "$saved_root" in
  "$data_root"/*) ;;
  *) echo "SAVED_DIR must be located below DATA_DIR ($data_root)" >&2; exit 2 ;;
esac
SAVED_DIR="$saved_root"
saved_parent="$(dirname "$SAVED_DIR")"
saved_name="$(basename "$SAVED_DIR")"
mkdir -p "$saved_parent"

python3 - "$archive" <<'PY'
import posixpath
import sys
import tarfile

archive = sys.argv[1]
with tarfile.open(archive, "r:gz") as handle:
    members = handle.getmembers()
    if not members:
        raise SystemExit("backup archive is empty")
    for member in members:
        name = posixpath.normpath(member.name)
        if member.name.startswith("/") or name == ".." or name.startswith("../"):
            raise SystemExit(f"unsafe archive entry: {member.name}")
        if name != "saved" and not name.startswith("saved/"):
            raise SystemExit(f"unsafe archive entry: {member.name}")
        if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
            raise SystemExit(f"unsupported archive entry: {member.name}")
PY

stage="${saved_parent}/.restore-stage.$$"
previous="${saved_parent}/${saved_name}.before-restore.$(date +%s).$$"
cleanup() { rm -rf -- "$stage"; }
trap cleanup EXIT
rm -rf -- "$stage"
mkdir -p "$stage"
tar -C "$stage" --no-same-owner --no-same-permissions -xzf "$archive"
[[ -d "$stage/saved" ]] || { echo "backup does not contain a saved directory" >&2; exit 2; }
if (( EUID == 0 )); then
  chown -R "$PUID:$PGID" "$stage/saved"
fi

if [[ -e "$SAVED_DIR" ]]; then
  mv "$SAVED_DIR" "$previous"
fi
if ! mv "$stage/saved" "$SAVED_DIR"; then
  if [[ -e "$previous" && ! -e "$SAVED_DIR" ]]; then
    mv "$previous" "$SAVED_DIR"
  fi
  echo "restore swap failed; previous save data was restored" >&2
  exit 1
fi
rm -rf -- "$stage"
trap - EXIT
printf 'Restored %s into %s\n' "$archive" "$SAVED_DIR"
if [[ -e "$previous" ]]; then
  printf 'Previous save data retained at %s\n' "$previous"
fi
