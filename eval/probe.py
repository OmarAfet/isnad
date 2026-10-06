#!/usr/bin/env python3
"""Judge probe: send queries to the Isnad API and print a compact view of each full answer
(verdict, scores, the text or list, graders, translation, referral, scope, citation lookup).
Used for every judge-style pass in session 3. The deployed API needs ISNAD_PROXY_SECRET.

Usage: python eval/probe.py [--api URL] [--gap s] "query" ... | -f file (one query per line)"""
import json, os, ssl, sys, time, urllib.error, urllib.request
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = None
a = sys.argv[1:]
api = "https://isnad-api.vercel.app"; gap = 2.1; qs = []
while a:
    x = a.pop(0)
    if x == "--api": api = a.pop(0)
    elif x == "--gap": gap = float(a.pop(0))
    elif x == "-f": qs += [l.strip() for l in open(a.pop(0)) if l.strip() and not l.startswith("#")]
    else: qs.append(x)
print(f"RAN: python {sys.argv[0]} --api {api} --gap {gap} ({len(qs)} queries)", flush=True)
H = {"Content-Type": "application/json", "x-isnad-proxy": os.environ.get("ISNAD_PROXY_SECRET", "")}
def call(q):
    req = urllib.request.Request(f"{api}/api/search", data=json.dumps({"q": q}).encode(), headers=H)
    for i in range(4):
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180, context=CTX) as r:
                return json.load(r), time.time() - t
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < 3: time.sleep(20); continue
            return {"verdict": f"HTTP {e.code}", "body": e.read().decode()[:300]}, time.time() - t
def item(t, ind="   "):
    g = "; ".join(f"{x['grader']}: {x['grade']}" for x in t.get("graders") or [])
    tr = (t.get("translation") or {})
    s = (f"{ind}{t.get('id')} | {t.get('ref')} | grade={t.get('grade')} sev={t.get('severity')} "
         f"basis={t.get('grade_basis')} action={t.get('action')}\n{ind}  matn: {(t.get('matn') or '')[:160]}")
    if g: s += f"\n{ind}  graders: {g[:200]}"
    if tr: s += f"\n{ind}  translation: {json.dumps(tr, ensure_ascii=False)[:200]}"
    if t.get("relevance") is not None: s += f"\n{ind}  relevance: {t.get('relevance')}"
    if t.get("variants"): s += f"\n{ind}  variants: {[v.get('id') for v in t['variants']]}"
    return s
for q in qs:
    d, sec = call(q)
    print(f"\n### {q}\n  verdict={d.get('verdict')} conf={d.get('confidence')} spec={d.get('specific_enough')} "
          f"lang={d.get('query_language')} fatwa={d.get('fatwa_request')} surah={d.get('surah')} {sec:.1f}s")
    if d.get("ruling"): print("  ruling:", json.dumps(d["ruling"], ensure_ascii=False)[:300])
    for k in ("refer", "scope", "lookup"):
        if d.get(k): print(f"  {k}:", json.dumps(d[k], ensure_ascii=False)[:300])
    if d.get("body"): print("  body:", d["body"])
    if d.get("result"): print(item(d["result"]))
    for t in d.get("alternatives") or []: print("  ALT" + item(t)[3:])
    for t in d.get("topic") or []: print("  TOPIC" + item(t)[3:])
    sys.stdout.flush(); time.sleep(gap)
