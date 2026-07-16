#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

tmp="$(mktemp -d)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

if DATA_DIR=/ bash ./docker-entrypoint.sh true >"$tmp/entrypoint.out" 2>&1; then
  echo "entrypoint safety test unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'DATA_DIR must be an absolute path other than /' "$tmp/entrypoint.out"

if FIX_PERMISSIONS=invalid DATA_DIR=/safe RUNTIME_DIR=/run/nos \
  bash ./docker-entrypoint.sh true >"$tmp/boolean.out" 2>&1; then
  echo "entrypoint boolean validation unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'FIX_PERMISSIONS must be a boolean' "$tmp/boolean.out"

mkdir -p "$tmp/data/saved"
printf 'original\n' >"$tmp/data/saved/world.sav"
DATA_DIR="$tmp/data" BACKUP_DIR="$tmp/data/backups" KEEP_BACKUPS=2 \
  ./scripts/backup.sh >"$tmp/backup.out"
archive="$(find "$tmp/data/backups" -name 'saved-*.tar.gz' -print -quit)"
printf 'changed\n' >"$tmp/data/saved/world.sav"
DATA_DIR="$tmp/data" ./scripts/restore.sh "$archive" >"$tmp/restore.out"
grep -q '^original$' "$tmp/data/saved/world.sav"
find "$tmp/data" -maxdepth 1 -type d -name 'saved.before-restore.*' | grep -q .

python3 - "$tmp/bad.tar.gz" <<'PY'
import io
import sys
import tarfile

with tarfile.open(sys.argv[1], "w:gz") as handle:
    content = b"bad"
    member = tarfile.TarInfo("../escape")
    member.size = len(content)
    handle.addfile(member, io.BytesIO(content))
PY

if DATA_DIR="$tmp/data" ./scripts/restore.sh "$tmp/bad.tar.gz" >"$tmp/bad.out" 2>&1; then
  echo "malicious restore unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'unsafe archive entry' "$tmp/bad.out"

python3 - "$tmp/link.tar.gz" <<'PY'
import sys
import tarfile

with tarfile.open(sys.argv[1], "w:gz") as handle:
    directory = tarfile.TarInfo("saved")
    directory.type = tarfile.DIRTYPE
    handle.addfile(directory)
    link = tarfile.TarInfo("saved/outside")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    handle.addfile(link)
PY

if DATA_DIR="$tmp/data" ./scripts/restore.sh "$tmp/link.tar.gz" >"$tmp/link.out" 2>&1; then
  echo "symlink restore unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'unsupported archive entry' "$tmp/link.out"

echo "Shell behavior tests passed"
