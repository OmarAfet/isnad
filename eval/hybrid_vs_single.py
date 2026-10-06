#!/usr/bin/env python3
"""Does hybrid search beat each half alone? Stage one only (no Jev), on the 13 labelled queries
of eval/fusion_sweep.py, with the search code and encoder as deployed. A hit is the gold record
or any copy search merged into it (the same report in another collection).

Replaces eval/fusion_sweep.py for this number: that script imports a function search.py no
longer has. /method and the README quote the hit@1 line this prints.

Usage: python eval/hybrid_vs_single.py        (ISNAD_ENCODER=onnx by default, as deployed)
"""
import os, sys
os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import cascade                         # noqa: E402
from search import Isnad, DENSE_W, LEX_W   # noqa: E402

CASES = [
    ("حديث عن أن الأعمال تكون بحسب النيات", "bukhari:1"),
    ("hadith about intentions determining deeds", "bukhari:1"),
    ("حديث عن النية في الهجرة", "bukhari:1"),
    ("حديث إزالة الأذى من الطريق من شعب الإيمان", "muslim:153"),
    ("الإيمان شعب كثيرة أعلاها التوحيد وأدناها إماطة الأذى", "muslim:153"),
    ("حديث الإسلام مبني على خمسة أشياء", "bukhari:8"),
    ("the five pillars of Islam hadith", "bukhari:8"),
    ("حديث من غش فليس مني", "muslim:283"),
    ("الآية التي تقول إن الله لا تأخذه سنة ولا نوم", "quran:2:255"),
    ("verse about Allah never being overtaken by sleep", "quran:2:255"),
    ("لا إكراه في الدين", "quran:2:256"),
    ("الآية التي فيها أن الله خلق الموت والحياة ليبتلينا", "quran:67:2"),
    ("آية عن الصبر والصلاة", "quran:2:153"),
]
MODES = {"hybrid": (DENSE_W, LEX_W), "dense only": (1.0, 0.0), "lexical only": (0.0, 1.0)}


def rank(results, gold):
    for i, r in enumerate(results):
        if r["id"] == gold or any(v["id"] == gold for v in r.get("variants") or []):
            return i + 1
    return None


def main():
    print("RAN: python eval/hybrid_vs_single.py")
    ix = Isnad()
    table = {m: [] for m in MODES}
    for q, gold in CASES:
        cells = []
        for m, (dw, lw) in MODES.items():
            r = rank(ix.search(q, k=cascade.NET, dense_w=dw, lex_w=lw), gold)
            table[m].append(r)
            cells.append(f"{m}={r if r else '-':>4}")
        print(f"  {q[:44]:44s} {gold:12s} " + "  ".join(cells), flush=True)
    n = len(CASES)
    for m, rs in table.items():
        h1 = sum(1 for r in rs if r == 1)
        h120 = sum(1 for r in rs if r)
        print(f"{m:13s} hit@1 {h1}/{n}   hit@{cascade.NET} {h120}/{n}")


if __name__ == "__main__":
    main()
