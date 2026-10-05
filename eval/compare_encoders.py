#!/usr/bin/env python3
"""Does the int8 ONNX query encoder hand Jev the same shortlist as the PyTorch one?

Isnad's index was embedded in PyTorch. The free host cannot hold PyTorch and the float32 model,
so serving would encode queries with the author's int8 ONNX export instead. This measures what
that changes, on the shortlist Jev actually receives (ix.search(q, k=cascade.NET)):

  cosine      similarity of the two query vectors
  overlap     share of the PyTorch shortlist that the ONNX shortlist also contains
  rank        position of the labelled answer under each encoder (fusion_sweep.py's cases)

Usage: python eval/compare_encoders.py
"""
import os, sys, time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import cascade                      # noqa: E402
from search import Isnad            # noqa: E402

# Labelled (query, record id): the cases of eval/fusion_sweep.py, copied because that script no
# longer imports (it asks search.py for _minmax, which was removed).
CASES = [
    ("حديث عن أن الأعمال تكون بحسب النيات",              "bukhari:1"),
    ("hadith about intentions determining deeds",          "bukhari:1"),
    ("حديث عن النية في الهجرة",                            "bukhari:1"),
    ("حديث إزالة الأذى من الطريق من شعب الإيمان",         "muslim:153"),
    ("الإيمان شعب كثيرة أعلاها التوحيد وأدناها إماطة الأذى", "muslim:153"),
    ("حديث الإسلام مبني على خمسة أشياء",                  "bukhari:8"),
    ("the five pillars of Islam hadith",                   "bukhari:8"),
    ("حديث من غش فليس مني",                               "muslim:283"),
    ("الآية التي تقول إن الله لا تأخذه سنة ولا نوم",       "quran:2:255"),
    ("verse about Allah never being overtaken by sleep",   "quran:2:255"),
    ("لا إكراه في الدين",                                  "quran:2:256"),
    ("الآية التي فيها أن الله خلق الموت والحياة ليبتلينا",  "quran:67:2"),
    ("آية عن الصبر والصلاة",                               "quran:2:153"),
]

# Unlabelled: every smoke case, and one description per translated surface, so the languages
# that only the dense half can reach are covered too.
EXTRA = [
    "حديث عن الكذب",
    "الآية اللي فيها لا تأخذه سنة ولا نوم",
    "حديث إن الفقيه أشد على الشيطان من ألف عابد",
    "هل يجوز لي الجمع بين الصلاتين في السفر؟",
    "حديث عن اختراع الطائرة والسفر إلى القمر",
    "ماحكم الزنا",
    "hadis tentang niat",
    "niyet hakkında hadis",
    "hadith sur l'intention",
    "хадис о намерении",
    "نیت کے بارے میں حدیث",
    "নিয়ত সম্পর্কে হাদিস",
]


def ids(results):
    return [r["id"] for r in results]


def rank(results, gid):
    for i, r in enumerate(results):
        if r["id"] == gid or any(v["id"] == gid for v in r.get("variants") or []):
            return i + 1
    return None


def main():
    print("RAN: python eval/compare_encoders.py")
    ix = Isnad(device="cpu", encoder="torch")
    rows = []
    for q, gid in [(q, g) for q, g in CASES] + [(q, None) for q in EXTRA]:
        ix.encoder = "torch"
        vt = ix.embed_query(q)
        rt = ix.search(q, k=cascade.NET)
        ix.encoder = "onnx"
        vo = ix.embed_query(q)
        t_onnx = time.time()
        ro = ix.search(q, k=cascade.NET)
        t_onnx = (time.time() - t_onnx) * 1000
        cos = float(np.dot(vt, vo))
        a, b = set(ids(rt)), set(ids(ro))
        overlap = len(a & b) / max(1, len(a))
        rows.append((q, gid, cos, overlap, rank(rt, gid) if gid else None,
                     rank(ro, gid) if gid else None, t_onnx))
        print(f"cos {cos:.4f}  overlap {overlap:5.1%}  rank torch {str(rank(rt, gid) if gid else '-'):>4}"
              f"  onnx {str(rank(ro, gid) if gid else '-'):>4}  {t_onnx:5.0f} ms  {q[:50]}")

    cos = np.array([r[2] for r in rows])
    ov = np.array([r[3] for r in rows])
    lab = [r for r in rows if r[1]]
    def hits(col, k):
        return sum(1 for r in lab if r[col] is not None and r[col] <= k)
    print(f"\nqueries {len(rows)}  cosine min {cos.min():.4f} median {np.median(cos):.4f}"
          f"  shortlist overlap min {ov.min():.1%} median {np.median(ov):.1%}")
    for k in (1, 3, cascade.NET):
        print(f"labelled {len(lab)}  hit@{k:<3} torch {hits(4, k):2d}  onnx {hits(5, k):2d}")


if __name__ == "__main__":
    main()
