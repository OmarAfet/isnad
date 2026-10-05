#!/usr/bin/env python3
"""Does stage one hand topic mode the right texts? Measures one retrieval variant, no Jev calls.

Topic queries ("ايه عن النوم") have several right answers; what matters is whether they reach the
24 texts topic mode judges. Labelled single-text queries guard against regressions: the right
text should still rank first, and stay inside Jev's 120.

  base    session-1 retrieval: literal match on every query word, whole tokens
  clean   request words ("ايه", "حديث", "عن", "verse", "about") dropped from the literal match
  stem    light10 Arabic stemming in the literal match
  both    clean + stem                      (all variants judge only the asked-for kind in
                                             topic mode, except base)
  stemcue stem + only the kind words dropped (ايه، حديث، verse...), function words kept

Usage: python eval/topic_recall.py --variant both
"""
import os, sys

os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import cascade                                  # noqa: E402
import search                                   # noqa: E402
from _arabic import normalize                   # noqa: E402
from compare_encoders import CASES              # noqa: E402  13 labelled single-text queries

SLEEP = "quran:2:255 quran:25:47 quran:78:9 quran:30:23 quran:39:42 quran:8:11 quran:6:60"
TOPICS = [
    ("ايه عن النوم", SLEEP),
    ("verse about sleep", SLEEP),
    ("آية عن الصبر", "quran:2:153 quran:2:45 quran:2:155 quran:3:200 quran:39:10 quran:103:3 quran:16:127"),
    ("ايه عن بر الوالدين", "quran:17:23 quran:31:14 quran:46:15 quran:4:36 quran:2:83 quran:29:8 quran:6:151"),
    ("ايه عن الموت", "quran:3:185 quran:21:35 quran:29:57 quran:62:8 quran:4:78 quran:67:2 quran:50:19"),
    ("ايه عن الربا", "quran:2:275 quran:2:276 quran:2:278 quran:3:130 quran:30:39 quran:4:161"),
    ("حديث عن الصدق", "text:الصدق يهدي"),
    ("حديث عن الغضب", "text:لا تغضب"),
    ("حديث عن الرحمة", "text:الراحمون"),
    ("حديث عن الكذب", "text:الكذب"),
]


def hits(cands, want):
    """Positions (1-based) of the wanted texts in cands: ids, or a phrase in the matn."""
    out = []
    for w in want.split(" ") if not want.startswith("text:") else [want]:
        for i, c in enumerate(cands):
            ids = {c["id"]} | {v["id"] for v in c.get("variants") or []}
            if (w.startswith("text:") and normalize(w[5:]) in normalize(c.get("matn") or "")) \
                    or w in ids:
                out.append(i + 1)
                if not w.startswith("text:"):
                    break
    return out


def main():
    variant = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "both"
    search.LEX_CLEAN = variant in ("clean", "both", "stemcue")
    search.STEM_AR = variant in ("stem", "both", "stemcue")
    if variant == "stemcue":     # drop only the kind words; function words keep their low weight
        search.REQUEST_WORDS = (search.AYAH_CUES | search.HADITH_CUES) - {"سنه", "السنه"} | {"ءايه", "آيه"}
    if variant == "base":
        cascade.TOPIC_KIND_MIN = 10 ** 9
    print(f"RAN: python eval/topic_recall.py --variant {variant}")
    ix = search.Isnad()
    total_in_pool = total_wanted = 0
    for q, want in TOPICS:
        cands = ix.search(q, k=cascade.NET)
        pool = cascade._topic_pool(cands)
        in_short, in_pool = hits(cands, want), hits(pool, want)
        n = 1 if want.startswith("text:") else len(want.split())
        got = min(len(in_pool), n)
        total_in_pool += got
        total_wanted += n
        verses = sum(1 for c in pool if c["kind"] == "ayah")
        print(f"  pool {got}/{n}  first in shortlist {min(in_short) if in_short else '-':>4}"
              f"  pool verses {verses:2d}/{len(pool)}  | {q}")
    h1 = h3 = h120 = 0
    for q, gid in CASES:
        r = hits(ix.search(q, k=cascade.NET), gid)
        h1 += bool(r and r[0] == 1); h3 += bool(r and r[0] <= 3); h120 += bool(r)
    print(f"{variant:5s} topic texts reaching topic mode {total_in_pool}/{total_wanted}"
          f"   labelled hit@1 {h1}/{len(CASES)} hit@3 {h3}/{len(CASES)} hit@120 {h120}/{len(CASES)}")


if __name__ == "__main__":
    main()
