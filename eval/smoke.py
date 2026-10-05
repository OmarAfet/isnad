#!/usr/bin/env python3
"""Behavioural regression suite for the running Isnad API.

Each case states what Isnad must DO, not a score: return this text, list texts on a subject,
refer a fatwa request, or decline. Checks match on the text itself rather than on one record id,
because the same report sits in several collections and any copy is a correct answer.

Usage: python eval/smoke.py [--api http://127.0.0.1:8000] [--wait 120]
"""
import json, os, ssl, sys, time, urllib.request
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(
    __import__("os").path.abspath(__file__)), "..", "scripts"))
from _arabic import normalize

API = "http://127.0.0.1:8000"
# python.org builds on macOS ship without root certificates; certifi's bundle makes HTTPS work
# against the deployed service (without it every request failed CERTIFICATE_VERIFY_FAILED, and
# the health wait reported the API as unreachable).
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = None
for i, a in enumerate(sys.argv):
    if a == "--api":
        API = sys.argv[i + 1]
WAIT = int(sys.argv[sys.argv.index("--wait") + 1]) if "--wait" in sys.argv else 120
# Full-corpus mode reads every text: ~40 s alone, longer when searches share the organisation's
# token limit (a topic query ran 108 s beside a browser search). The first run used 60 s and
# failed a query the app had answered correctly.
TIMEOUT = int(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 300
GAP = float(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else 0.0

# (query, allowed verdicts, words the chosen text must contain, extra check)
CASES = [
    ("حديث عن الكذب", {"topic"}, None, "topic>=3"),
    ("حديث عن أن الأعمال بالنيات", {"confident", "tentative"}, ["الاعمال", "بالني"], None),
    ("hadith about intentions determining deeds", {"confident", "tentative"},
     ["الاعمال", "بالني"], None),
    ("لا إكراه في الدين", {"confident"}, None, "id=quran:2:256"),
    ("الآية اللي فيها لا تأخذه سنة ولا نوم", {"confident"}, None, "id=quran:2:255"),
    ("verse about Allah never being overtaken by sleep", {"confident", "tentative"}, None,
     "id=quran:2:255"),
    ("حديث إن الفقيه أشد على الشيطان من ألف عابد", {"confident"}, ["فقيه", "عابد"],
     "severity=mawdu"),
    ("the hadith about the five pillars of Islam", {"confident", "tentative"}, ["خمس"], None),
    # Ruling questions: the texts on the matter and a referral, never a ruling and never silence.
    # A personal case is Reference Framework level (د); asking a hadith's GRADE is not a ruling
    # question at all, it is Isnad's core job.
    ("هل يجوز لي الجمع بين الصلاتين في السفر؟", {"ruling"}, None, "ruling=personal"),
    ("ماحكم الزنا", {"ruling"}, None, "ruling=general;topic>=1"),
    ("ما حكم حديث إن الفقيه أشد على الشيطان من ألف عابد", {"confident", "tentative"},
     ["فقيه", "عابد"], "severity=mawdu"),
    ("حديث عن اختراع الطائرة والسفر إلى القمر", {"no_match", "topic"}, None, "topic==0"),
    # A subject with the kind named: verses only, and the verse the reader most likely means.
    ("ايه عن النوم", {"topic"}, None, "has=quran:2:255;kind=ayah"),
    ("ايه عن بر الوالدين", {"topic"}, None, "has=quran:17:23;kind=ayah"),
]


def call(q):
    headers = {"Content-Type": "application/json"}
    if os.environ.get("ISNAD_PROXY_SECRET"):       # a deployed service serves only its proxy
        headers["x-isnad-proxy"] = os.environ["ISNAD_PROXY_SECRET"]
    req = urllib.request.Request(f"{API}/api/search", data=json.dumps({"q": q}).encode(),
                                 headers=headers)
    for attempt in range(4):
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
                return json.load(r), (time.time() - t) * 1000
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
            time.sleep(20)      # the service allows 30 searches a minute per reader


def main():
    print(f"RAN: python eval/smoke.py --api {API}")
    t0 = time.time()
    while True:
        try:
            urllib.request.urlopen(f"{API}/api/health", timeout=30, context=CTX)
            break
        except Exception:
            if time.time() - t0 > WAIT:
                print(f"API not reachable at {API} after {WAIT}s")
                sys.exit(2)
            time.sleep(2)

    passed, lat = 0, []
    for q, verdicts, words, extra in CASES:
        time.sleep(GAP)
        try:
            d, ms = call(q)
        except Exception as e:
            print(f"  FAIL  {q[:44]:44s}  request error: {e}")
            continue
        lat.append(ms)
        v = d.get("verdict")
        r = d.get("result") or {}
        topic = d.get("topic") or []
        why = []
        if v not in verdicts:
            why.append(f"verdict {v} not in {sorted(verdicts)}")
        if words and r:
            m = normalize(r.get("matn") or "")
            miss = [w for w in words if normalize(w) not in m]
            if miss:
                why.append(f"text lacks {miss}")
        elif words and not r:
            why.append("no text returned")
        for extra in (extra or "").split(";"):
            if not extra:
                continue
            if extra.startswith("ruling=") and (d.get("ruling") or {}).get("kind") != extra[7:]:
                why.append(f"ruling kind {(d.get('ruling') or {}).get('kind')} != {extra[7:]}")
            if extra.startswith("has=") and extra[4:] not in {t.get("id") for t in topic} | {r.get("id")}:
                why.append(f"{extra[4:]} not listed")
            if extra.startswith("kind=") and any(t.get("kind") != extra[5:] for t in topic):
                why.append(f"listed a text that is not a {extra[5:]}")
            if extra.startswith("id=") and r.get("id") != extra[3:]:
                why.append(f"id {r.get('id')} != {extra[3:]}")
            if extra.startswith("severity=") and r.get("severity") != extra[9:]:
                why.append(f"severity {r.get('severity')} != {extra[9:]}")
            if extra.startswith("topic>=") and len(topic) < int(extra[7:]):
                why.append(f"only {len(topic)} topic texts")
            if extra == "topic==0" and topic:
                why.append(f"listed {len(topic)} texts for a subject the sources do not cover")
        ok = not why
        passed += ok
        shown = r.get("ref") or (f"{len(topic)} texts" if topic else "-")
        conf = d.get("confidence")
        print(f"  {'PASS' if ok else 'FAIL'}  {ms:5.0f}ms  {str(v):14s} "
              f"{('%.2f' % conf) if conf is not None else '  - ':5s} {shown[:24]:24s} | {q[:42]}"
              + ("" if ok else f"\n        -> {'; '.join(why)}"))
    lat.sort()
    print(f"\n{passed}/{len(CASES)} passed   latency median {lat[len(lat)//2]:.0f}ms "
          f"max {lat[-1]:.0f}ms (cached answers excluded only if the API was just restarted)")
    sys.exit(0 if passed == len(CASES) else 1)


if __name__ == "__main__":
    main()
