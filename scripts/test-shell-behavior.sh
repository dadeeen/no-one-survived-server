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
(umask 0000; DATA_DIR="$tmp/data" BACKUP_DIR="$tmp/data/backups" KEEP_BACKUPS=2 \
  ./scripts/backup.sh >"$tmp/backup.out")
archive="$(find "$tmp/data/backups" -name 'saved-*.tar.gz' -print -quit)"
[[ "$(stat -c '%a' "$archive")" == 600 ]]
[[ "$(stat -c '%a' "$tmp/data/backups")" == 700 ]]
printf 'changed\n' >"$tmp/data/saved/world.sav"
(umask 0000; DATA_DIR="$tmp/data" ./scripts/restore.sh "$archive" >"$tmp/restore.out")
grep -q '^original$' "$tmp/data/saved/world.sav"
[[ "$(stat -c '%a' "$tmp/data/saved")" == 700 ]]
find "$tmp/data" -maxdepth 1 -type d -name 'saved.before-restore.*' | grep -q .

mkdir -p "$tmp/outside-saved"
printf 'outside\n' >"$tmp/outside-saved/world.sav"
if DATA_DIR="$tmp/data" SAVED_DIR="$tmp/outside-saved" \
  BACKUP_DIR="$tmp/data/backups" ./scripts/backup.sh >"$tmp/outside-backup.out" 2>&1; then
  echo "backup accepted SAVED_DIR outside DATA_DIR" >&2
  exit 1
fi
grep -q 'SAVED_DIR must be located below DATA_DIR' "$tmp/outside-backup.out"
if DATA_DIR="$tmp/data" SAVED_DIR="$tmp/outside-saved" \
  ./scripts/restore.sh "$archive" >"$tmp/outside-restore.out" 2>&1; then
  echo "restore accepted SAVED_DIR outside DATA_DIR" >&2
  exit 1
fi
grep -q 'SAVED_DIR must be located below DATA_DIR' "$tmp/outside-restore.out"
grep -q '^outside$' "$tmp/outside-saved/world.sav"

mkdir -p "$tmp/custom-data/custom saves"
printf 'custom-original\n' >"$tmp/custom-data/custom saves/world.sav"
DATA_DIR="$tmp/custom-data" \
  SAVED_DIR="$tmp/custom-data/custom saves" \
  BACKUP_DIR="$tmp/custom-data/backups" \
  KEEP_BACKUPS=1 \
  ./scripts/backup.sh >"$tmp/custom-backup.out"
custom_archive="$(find "$tmp/custom-data/backups" -name 'saved-*.tar.gz' -print -quit)"
tar -tzf "$custom_archive" | grep -q '^saved/world\.sav$'
printf 'custom-changed\n' >"$tmp/custom-data/custom saves/world.sav"
DATA_DIR="$tmp/custom-data" SAVED_DIR="$tmp/custom-data/custom saves" \
  ./scripts/restore.sh "$custom_archive" >"$tmp/custom-restore.out"
grep -q '^custom-original$' "$tmp/custom-data/custom saves/world.sav"
find "$tmp/custom-data" -maxdepth 1 -type d -name 'custom saves.before-restore.*' | grep -q .

mkdir -p "$tmp/zero-data/saved"
printf 'keep-all\n' >"$tmp/zero-data/saved/world.sav"
DATA_DIR="$tmp/zero-data" BACKUP_DIR="$tmp/zero-data/backups" KEEP_BACKUPS=0 \
  ./scripts/backup.sh >"$tmp/backup-zero.out"
[[ "$(find "$tmp/zero-data/backups" -type f -name 'saved-*.tar.gz' | wc -l)" -eq 1 ]]

space_backup_dir="$tmp/my  backups"
DATA_DIR="$tmp/zero-data" BACKUP_DIR="$space_backup_dir" KEEP_BACKUPS=1 \
  ./scripts/backup.sh >"$tmp/backup-space-1.out"
sleep 1
DATA_DIR="$tmp/zero-data" BACKUP_DIR="$space_backup_dir" KEEP_BACKUPS=1 \
  ./scripts/backup.sh >"$tmp/backup-space-2.out"
[[ "$(find "$space_backup_dir" -type f -name 'saved-*.tar.gz' | wc -l)" -eq 1 ]]

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

mkdir -p "$tmp/bin"
cat >"$tmp/bin/docker" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$*" == "buildx imagetools inspect debian:trixie-slim" ]]
printf '%s\n' \
  'Name:      docker.io/library/debian:trixie-slim' \
  'MediaType: application/vnd.oci.image.index.v1+json' \
  'Digest:    sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  '' \
  'Manifests:'
for index in $(seq 1 100); do
  printf '  Name: manifest-%s\n' "$index"
done
SH
chmod +x "$tmp/bin/docker"

digest="$(PATH="$tmp/bin:$PATH" ./scripts/resolve-image-digest.sh debian:trixie-slim)"
[[ "$digest" == "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" ]]

cat >"$tmp/bin/docker" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' 'Name: docker.io/library/debian:trixie-slim' 'MediaType: application/vnd.oci.image.index.v1+json'
SH
chmod +x "$tmp/bin/docker"
if PATH="$tmp/bin:$PATH" ./scripts/resolve-image-digest.sh debian:trixie-slim >"$tmp/digest.out" 2>&1; then
  echo "digest resolution without a digest unexpectedly succeeded" >&2
  exit 1
fi
grep -q 'No digest found in image manifest inspection' "$tmp/digest.out"

echo "Shell behavior tests passed"
