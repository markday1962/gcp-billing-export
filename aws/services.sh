#!/usr/bin/env bash
# AWS Cost Explorer: cost by service for the current calendar month to date
# (UTC), across all services in the given account. Excludes RECORD_TYPE
# "Tax", to match the GCP queries' exclusion of tax/adjustment rows.
#
# Usage: aws/services.sh [profile]
#   profile defaults to AdministratorAccess-102369858221.
#
# Prints the raw `aws ce get-cost-and-usage` JSON response to stdout — shape
# it (top N, sort, sum) with jq downstream, same pattern as piping bq's JSON
# output through jq. See README.md for the jq pipelines used by the
# billing-dashboard skill.
set -euo pipefail

PROFILE="${1:-AdministratorAccess-102369858221}"
START="$(date -u +%Y-%m-01)"
END="$(date -u -v+1d +%Y-%m-%d 2>/dev/null || date -u -d '+1 day' +%Y-%m-%d)"

aws ce get-cost-and-usage \
  --profile "$PROFILE" \
  --time-period Start="$START",End="$END" \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --filter '{"Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Tax"]}}}' \
  --group-by Type=DIMENSION,Key=SERVICE \
  --output json
