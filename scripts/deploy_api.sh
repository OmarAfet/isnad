#!/usr/bin/env bash
# Stage the API and deploy it to Vercel production in the personal Hobby scope, then check that it
# answers. Re-run after any change to api/, src/ or scripts/_*.py.
#
# The scope is explicit on purpose: this Vercel login also belongs to a company team on a paid
# plan, and that team is the CLI's default. Isnad must run free, in omar-afet only.
#
# Usage: scripts/deploy_api.sh
set -euo pipefail
cd "$(dirname "$0")/.."
SCOPE=omar-afet
PROD=https://isnad-api.vercel.app
LOG=/tmp/isnad-api-deploy.log

echo "RAN: scripts/deploy_api.sh  (stage_api.py; vercel deploy --prod --yes --scope $SCOPE in deploy/api)"
.venv/bin/python scripts/stage_api.py
cd deploy/api
# The CLI can exit 0 on a failed deploy (2026-10-05: "deploy_failed", bundle too large), so the
# log is checked as well as the exit code.
if ! vercel deploy --prod --yes --scope "$SCOPE" >"$LOG" 2>&1 || grep -q '"status": "error"' "$LOG"; then
  tr '\r' '\n' <"$LOG" | grep -v "Uploading \[" | tail -40
  exit 1
fi
tr '\r' '\n' <"$LOG" | grep -E "build.py|Installing|Build Completed|Error|error|Aliased|Production" | tail -15
echo "health: $PROD/api/health"
curl -s -m 120 -w "\nHTTP %{http_code} in %{time_total}s\n" "$PROD/api/health"
