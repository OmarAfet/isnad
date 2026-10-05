#!/usr/bin/env python3
"""Choose the fusion rule on evidence, against the full 40,389-record index.

Four candidates, because the first two each failed in an instructive way:
  global_minmax — the best and worst score in the whole corpus set the scale, so every real
                  candidate lands in the same narrow band.
  pool_minmax   — rescales inside the candidate pool, where dense scores are nearly identical
                  (0.80-0.87), so it amplifies dense noise into large differences. Demoted a
                  rank-1 ayah to rank 2.
  zscore        — "how unusual is this score" against the corpus distribution. Robust to a
                  compressed range without amplifying it.
  rrf           — ranks only, ignoring scores entirely.

Gold is a family of records: the same report appears in several collections, so returning Nasa'i's
copy of a Bukhari hadith is correct. Ayahs are unique and stand alone.

Usage: python eval/fusion_sweep.py
"""
import json, os, sys, time
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from _arabic import normalize
from search import Isnad, _minmax, wanted_kind, CANDIDATES, KIND_BOOST

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
    ("حديث إنما بعثت لأتمم حسن الأخلاق",                   "ibnmajah:(skip)"),
]
CASES = [(q, g) for q, g in CASES if "(skip)" not in g]
CONTAIN, MIN_TOK = 0.80, 6


def families(recs):
    by = {r["id"]: r for r in recs}
    out = {}
    for gid in sorted({g for _, g in CASES}):
        if gid.startswith("quran:"):
            out[gid] = {gid}
            continue
        g = set(by[gid]["match_text"].split())
        fam = {gid}
        for r in recs:
            t = set(r["match_text"].split())
            d = min(len(g), len(t))
            if d >= MIN_TOK and len(g & t) / d >= CONTAIN:
                fam.add(r["id"])
        out[gid] = fam
    return out


def zs(x):
    m, s = float(x.mean()), float(x.std())
    return (x - m) / s if s > 0 else np.zeros_like(x)


def rrf_scores(a, b, k=60):
    out = np.zeros(len(a), dtype=np.float32)
    for arr in (a, b):
        order = np.argsort(-arr)
        out[order] += 1.0 / (k + np.arange(len(arr)) + 1)
    return out


def main():
    ix = Isnad()
    _ = ix.embed_query("warm")
    fams = families(ix.recs)
    ids = [r["id"] for r in ix.recs]

    # Cache per-query raw scores once; fusion rules are then compared on identical inputs.
    raw = []
    for q, gid in CASES:
        qn = normalize(q)
        dense = ix.E.astype(np.float32) @ ix.embed_query(q)
        lex = ix.bm25.score(qn)
        raw.append((q, gid, qn, dense, lex))

    def evaluate(rule, dw, lw, use_kind=True):
        ranks = []
        for q, gid, qn, dense, lex in raw:
            n = len(dense)
            d_top = np.argpartition(-dense, min(CANDIDATES, n - 1))[:CANDIDATES]
            nz = np.nonzero(lex)[0]
            l_top = nz[np.argsort(-lex[nz])[:CANDIDATES]] if nz.size else np.empty(0, int)
            pool = np.unique(np.concatenate([d_top, l_top])) if l_top.size else np.unique(d_top)

            if rule == "global_minmax":
                f = dw * _minmax(dense)[pool] + lw * _minmax(lex)[pool]
            elif rule == "pool_minmax":
                f = dw * _minmax(dense[pool]) + lw * _minmax(lex[pool])
            elif rule == "zscore":
                f = dw * zs(dense)[pool] + lw * zs(lex)[pool]
            elif rule == "rrf":
                f = rrf_scores(dense, lex)[pool]
            if use_kind:
                kind = wanted_kind(qn)
                if kind:
                    same = np.array([ix.recs[i]["kind"] == kind for i in pool])
                    scale = (f.max() - f.min()) or 1.0
                    f = f + np.where(same, KIND_BOOST, -KIND_BOOST) * scale
            order = pool[np.argsort(-f)]
            r = next((j + 1 for j, i in enumerate(order) if ids[i] in fams[gid]), None)
            ranks.append(r)
        h1 = sum(1 for r in ranks if r == 1)
        h3 = sum(1 for r in ranks if r and r <= 3)
        mrr = float(np.mean([1 / r if r else 0 for r in ranks]))
        return h1, h3, mrr, ranks

    print(f"cases={len(CASES)}  records={len(ix.recs)}")
    print(f"gold families: " + ", ".join(f"{g}={len(f)}" for g, f in fams.items()))
    print()
    print(f"{'rule':14s} {'dw':>4s} {'lw':>4s}  hit@1  hit@3    MRR")
    best = None
    for rule in ("global_minmax", "pool_minmax", "zscore", "rrf"):
        grid = [(0.65, 0.35)] if rule == "rrf" else [(1.0, 0.0), (0.7, 0.3), (0.5, 0.5),
                                                     (0.35, 0.65), (0.0, 1.0)]
        for dw, lw in grid:
            h1, h3, mrr, ranks = evaluate(rule, dw, lw)
            tag = f"{rule:14s} {dw:4.2f} {lw:4.2f}  {h1:2d}/{len(CASES)}  {h3:2d}/{len(CASES)}  {mrr:.3f}"
            print(tag)
            if best is None or (mrr, h1) > (best[2], best[0]):
                best = (h1, h3, mrr, rule, dw, lw, ranks)
    print()
    print(f"BEST: {best[3]} dense={best[4]} lex={best[5]}  hit@1 {best[0]}/{len(CASES)}  "
          f"hit@3 {best[1]}/{len(CASES)}  MRR {best[2]:.3f}")
    print("per-case ranks:")
    for (q, gid), r in zip(CASES, best[6]):
        print(f"   {str(r) if r else '--':>4s}  {q[:52]:52s} {gid}")


if __name__ == "__main__":
    main()
