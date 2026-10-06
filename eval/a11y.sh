#!/usr/bin/env bash
# Automated accessibility check: axe-core (WCAG 2.0 A/AA, 2.1 AA, 2.2 AA rule sets) on four pages
# of the live site, in an isolated headless Chromium (agent-browser --auto-connect false), so the
# user's own browser is never touched. Automated rules are a subset of WCAG; keyboard and screen
# reader use were checked by hand in the judge-style tests.
#
# Usage: eval/a11y.sh [base-url]        (default https://isnad-app.vercel.app)
set -euo pipefail
BASE=${1:-https://isnad-app.vercel.app}
AXE=/tmp/axe-4.10.2.min.js
AB=(agent-browser --auto-connect false --session isnad-a11y)
echo "RAN: eval/a11y.sh $BASE  (axe-core 4.10.2 via ${AB[*]})"
[ -s "$AXE" ] || curl -s -m 30 -o "$AXE" https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js
enc() { python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1"; }
for path in "/" "/?q=$(enc 'الجنة تحت أقدام الأمهات')" "/?q=$(enc 'ايه عن الصبر')" "/method"; do
  "${AB[@]}" open "$BASE$path" >/dev/null 2>&1
  "${AB[@]}" wait 6000 >/dev/null 2>&1
  "${AB[@]}" eval "$(cat "$AXE"); 0" >/dev/null 2>&1
  printf '%-14s ' "${path:0:14}"
  "${AB[@]}" eval "axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}).then(r=>'passes '+r.passes.length+', violations '+r.violations.length+' '+JSON.stringify(r.violations.map(v=>v.id)))" 2>/dev/null | tail -1
done
"${AB[@]}" close >/dev/null 2>&1 || true
