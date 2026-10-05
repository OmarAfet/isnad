#!/usr/bin/env bash
# Deploy the web app to Vercel production in the personal Hobby scope, then check that the home
# page and a search through the web tier answer. Re-run after any change in web/.
#
# The scope is explicit for the same reason as in deploy_api.sh: the CLI's default team is a
# company team on a paid plan.
#
# Usage: scripts/deploy_web.sh
set -euo pipefail
cd "$(dirname "$0")/../web"
SCOPE=omar-afet
PROD=https://isnad-app.vercel.app
LOG=/tmp/isnad-web-deploy.log

echo "RAN: scripts/deploy_web.sh  (vercel deploy --prod --yes --scope $SCOPE in web/)"
rm -f .env.local                       # written by `vercel link`; never needed here
if ! vercel deploy --prod --yes --scope "$SCOPE" >"$LOG" 2>&1 || grep -q '"status": "error"' "$LOG"; then
  tr '\r' '\n' <"$LOG" | grep -v "Uploading \[" | tail -40
  exit 1
fi
tr '\r' '\n' <"$LOG" | grep -E "Build Completed|Aliased|rror" | tail -5
curl -s -o /dev/null -m 60 -w "home: HTTP %{http_code} in %{time_total}s\n" "$PROD/"
curl -s -o /dev/null -m 120 -w "search via web: HTTP %{http_code} in %{time_total}s\n" \
  -X POST "$PROD/api/search" -H 'Content-Type: application/json' -d '{"q":"لا إكراه في الدين"}'
