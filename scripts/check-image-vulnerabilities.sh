#!/usr/bin/env bash
set -Eeuo pipefail

if (( $# != 1 )); then
  echo "Usage: check-image-vulnerabilities.sh TRIVY_JSON" >&2
  exit 2
fi

scan="$1"
if [[ ! -s "$scan" ]]; then
  echo "::error::Trivy result is missing or empty." >&2
  exit 1
fi

if ! counts="$(
  jq -ers '
    def valid_finding:
      type == "object"
      and (.Severity | IN("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"))
      and ((.FixedVersion == null) or (.FixedVersion | type) == "string");
    def valid_result:
      type == "object"
      and (.Target | type) == "string"
      and (.Target | length) > 0
      and ((.Vulnerabilities == null) or
        ((.Vulnerabilities | type) == "array" and
          all(.Vulnerabilities[]; valid_finding)));
    if length != 1 then error("Expected one Trivy report") else .[0] end |
    if type == "object" and .SchemaVersion == 2
      and (.Results | type) == "array" and (.Results | length) > 0
      and all(.Results[]; valid_result)
    then . else error("Invalid Trivy report") end |
    [.Results[] | (.Vulnerabilities // [])[]] as $findings |
    [
      ([$findings[] | select(.Severity == "HIGH" and ((.FixedVersion // "") | length > 0))] | length),
      ([$findings[] | select(.Severity == "CRITICAL" and ((.FixedVersion // "") | length > 0))] | length),
      ([$findings[] | select(.Severity == "CRITICAL" and ((.FixedVersion // "") | length == 0))] | length)
    ] | @tsv
  ' "$scan"
)"; then
  echo "::error::Trivy result is invalid; vulnerability checks could not complete." >&2
  exit 1
fi
read -r high_fixed critical_fixed critical_unfixed <<<"$counts"

if (( critical_unfixed > 0 )); then
  echo "::warning::Trivy reported $critical_unfixed CRITICAL findings without a published fix; manual risk assessment is required."
fi
if (( high_fixed > 0 || critical_fixed > 0 )); then
  echo "::error::Container has $high_fixed HIGH and $critical_fixed CRITICAL vulnerabilities with available fixes."
  exit 1
fi

echo "Container vulnerability gate passed: no fixable HIGH/CRITICAL findings."
