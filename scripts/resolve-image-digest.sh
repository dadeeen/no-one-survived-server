#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# != 1 )); then
  echo "Usage: $0 IMAGE_REFERENCE" >&2
  exit 2
fi

image_ref="$1"
if [[ -z "$image_ref" ]]; then
  echo "Image reference must not be empty" >&2
  exit 2
fi

inspect_output=""
if ! inspect_output="$(docker buildx imagetools inspect "$image_ref")"; then
  echo "Failed to inspect image manifest: $image_ref" >&2
  exit 1
fi

digest="$({
  awk '
    $1 == "Digest:" && digest == "" { digest = $2 }
    END {
      if (digest == "") {
        exit 1
      }
      print digest
    }
  ' <<<"$inspect_output"
})" || {
  echo "No digest found in image manifest inspection: $image_ref" >&2
  printf '%s\n' "$inspect_output" >&2
  exit 1
}

if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid image digest for $image_ref: $digest" >&2
  exit 1
fi

printf '%s\n' "$digest"
