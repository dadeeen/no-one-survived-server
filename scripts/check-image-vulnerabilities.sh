#!/usr/bin/env bash
# Validate a Trivy JSON result without storing scan reports in the repository.
set -Eeuo pipefail

if (( $# != 1 )); then
  echo "Usage: check-image-vulnerabilities.sh TRIVY_JSON" >&2
  exit 2
fi

scan="$1"
if [[ ! -s "$scan" ]] || ! jq -e 'type == "object" and (.Results | type) == "array"' "$scan" >/dev/null; then
  echo "::error::Trivy result is missing or invalid; refusing to treat the scan as clean." >&2
  exit 1
fi

read -r high_fixed critical_fixed critical_unfixed <<<"$(
  jq -r '
    [.Results[]?.Vulnerabilities[]?] as $findings |
    [
      ([$findings[] | select(.Severity == "HIGH" and ((.FixedVersion // "") | length > 0))] | length),
      ([$findings[] | select(.Severity == "CRITICAL" and ((.FixedVersion // "") | length > 0))] | length),
      ([$findings[] | select(.Severity == "CRITICAL" and ((.FixedVersion // "") | length == 0))] | length)
    ] | @tsv
  ' "$scan"
)"

if (( critical_unfixed > 0 )); then
  echo "::warning::Trivy reported $critical_unfixed CRITICAL findings without a published fix; manual risk assessment is required."
fi
if (( high_fixed > 0 || critical_fixed > 0 )); then
  echo "::error::Container has $high_fixed HIGH and $critical_fixed CRITICAL vulnerabilities with available fixes."
  exit 1
fi

echo "Container vulnerability gate passed: no fixable HIGH/CRITICAL findings."
