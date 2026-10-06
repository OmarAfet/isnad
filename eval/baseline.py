#!/usr/bin/env python3
"""Isnad against the alternatives a reader has today, on the judge battery's own questions.

  keyword search   BM25 over the same books, the way site search works (here with Arabic light
                   stemming and translated surfaces, so it is a strong keyword search)
  meaning search   multilingual-e5 embeddings alone (retrieval without a decision model)
  hybrid search    both, Isnad's stage one without Jev
  Isnad            stage one + Jev, the deployed service (--api)

Two kinds of question, taken from eval/battery.py:
  described texts  quote / memory / lang groups: is the right text the FIRST answer?
  not in the books sayings that are not hadith (fabricated group with no expected text): a search
                   engine always returns its top hit, so it "answers" with a text that does not
                   contain the saying; Isnad must say "not found" or show the fabricated grade.

Usage: python eval/baseline.py --api https://isnad-api.vercel.app [--gap 2.1]
       (ISNAD_PROXY_SECRET in the environment for the deployed API)
"""
import os, sys, time
os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import battery                                    # noqa: E402  (cases, check, call)
from search import Isnad, DENSE_W, LEX_W          # noqa: E402
from _arabic import normalize                     # noqa: E402

ENGINES = {"keyword search": (0.0, 1.0), "meaning search": (1.0, 0.0), "hybrid search": (DENSE_W, LEX_W)}


def has_ok(top, k):
    for h in k.get("has", []):
        kind, val = h.split(":", 1)
        ids = {top.get("id")} | {v.get("id") for v in top.get("variants") or []}
        if (kind == "id" and val in ids) or \
                (kind == "text" and normalize(val) in normalize(top.get("matn") or "")):
            return True
    return False


def main():
    a = sys.argv
    api = a[a.index("--api") + 1] if "--api" in a else "http://127.0.0.1:8000"
    gap = float(a[a.index("--gap") + 1]) if "--gap" in a else 2.1
    print(f"RAN: python eval/baseline.py --api {api} --gap {gap}")
    described = [(g, q, k) for g, q, k in battery.C if g in ("quote", "memory", "lang") and "has" in k]
    sayings = [(g, q, k) for g, q, k in battery.C if g == "fabricated" and "has" not in k]
    ix = Isnad()
    score = {e: 0 for e in list(ENGINES) + ["Isnad"]}
    for g, q, k in described:
        cells = []
        for e, (dw, lw) in ENGINES.items():
            top = (ix.search(q, k=1, dense_w=dw, lex_w=lw) or [{}])[0]
            ok = has_ok(top, k)
            score[e] += ok
            cells.append("+" if ok else ".")
        d, _ = battery.call(api, q)
        ok = not battery.check(d, k)
        score["Isnad"] += ok
        cells.append("+" if ok else ".")
        print(f"  {' '.join(cells)}  {q[:60]}", flush=True)
        time.sleep(gap)
    n = len(described)
    print(f"\nDescribed texts ({n}), right text first   (+ = yes; columns: "
          + ", ".join(score) + ")")
    for e, v in score.items():
        print(f"  {e:15s} {v}/{n}")

    honest = {e: 0 for e in list(ENGINES) + ["Isnad"]}
    for g, q, k in sayings:
        for e, (dw, lw) in ENGINES.items():
            top = (ix.search(q, k=1, dense_w=dw, lex_w=lw) or [{}])[0]
            # A search engine has no "not found": its first hit is its answer. It is honest only
            # if that text actually contains the saying, or is graded fabricated or weak.
            phrase = k.get("not_sound")
            contains = phrase and normalize(phrase) in normalize(top.get("matn") or "")
            honest[e] += bool(contains or top.get("severity") in ("mawdu", "daif"))
        d, _ = battery.call(api, q)
        honest["Isnad"] += not battery.check(d, k)
        time.sleep(gap)
    m = len(sayings)
    print(f"\nSayings that are not sound hadith in these books ({m}): answered honestly "
          "(not found, or the saying's own text with its weak or fabricated grade)")
    for e, v in honest.items():
        print(f"  {e:15s} {v}/{m}")


if __name__ == "__main__":
    main()
