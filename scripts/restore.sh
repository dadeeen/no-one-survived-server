#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -eq 1 ]] || { echo "usage: restore.sh BACKUP.tar.gz" >&2; exit 2; }

DATA_DIR="${DATA_DIR:-/data}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
archive="$1"
[[ "$PUID" =~ ^[0-9]+$ ]] && (( PUID > 0 )) || { echo "PUID must be a positive integer" >&2; exit 2; }
[[ "$PGID" =~ ^[0-9]+$ ]] && (( PGID > 0 )) || { echo "PGID must be a positive integer" >&2; exit 2; }
[[ -d "$DATA_DIR" ]] || { echo "data directory not found: $DATA_DIR" >&2; exit 2; }
[[ -f "$archive" ]] || { echo "backup not found: $archive" >&2; exit 2; }
archive="$(realpath "$archive")"

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

stage="${DATA_DIR}/.restore-stage.$$"
previous="${DATA_DIR}/saved.before-restore.$(date +%s).$$"
cleanup() { rm -rf -- "$stage"; }
trap cleanup EXIT
rm -rf -- "$stage"
mkdir -p "$stage"
tar -C "$stage" --no-same-owner --no-same-permissions -xzf "$archive"
[[ -d "$stage/saved" ]] || { echo "backup does not contain a saved directory" >&2; exit 2; }
if (( EUID == 0 )); then
  chown -R "$PUID:$PGID" "$stage/saved"
fi

if [[ -e "${DATA_DIR}/saved" ]]; then
  mv "${DATA_DIR}/saved" "$previous"
fi
if ! mv "$stage/saved" "${DATA_DIR}/saved"; then
  if [[ -e "$previous" && ! -e "${DATA_DIR}/saved" ]]; then
    mv "$previous" "${DATA_DIR}/saved"
  fi
  echo "restore swap failed; previous save data was restored" >&2
  exit 1
fi
rm -rf -- "$stage"
trap - EXIT
printf 'Restored %s into %s/saved\n' "$archive" "$DATA_DIR"
if [[ -e "$previous" ]]; then
  printf 'Previous save data retained at %s\n' "$previous"
fi
