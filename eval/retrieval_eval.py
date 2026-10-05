#!/usr/bin/env python3
"""Isnad retrieval evaluation.

GOLD FAMILIES. A hadith is reported in several collections with near-identical wording:
"إنما الأعمال بالنيات" sits at eleven places in this corpus. Returning Nasa'i's copy when the
query was written against Bukhari's is a correct answer, so correctness is defined over the family
of records carrying the same report, found by token containment. Ayahs are the exception: each is
unique, and a query about "لا تأخذه سنة ولا نوم" wants 2:255 and not 3:2, which merely shares a
phrase. So ayah gold is the exact id.

Scoring a different copy as a miss made every model look broken in the first pass.

Usage: python eval/retrieval_eval.py <model> [slice]
"""
import json, math, os, random, sys, time
from collections import Counter, defaultdict
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _arabic import normalize

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "data", "corpus", "corpus.jsonl")

# Meaning-first queries, Arabic and English. "آية الكرسي" is excluded from the core metric: it is
# the verse's NAME, not its wording, and no amount of semantic similarity recovers a name. That
# needs an alias index, tracked separately.
CASES = [
    ("حديث عن أن الأعمال تكون بحسب النيات",            "bukhari:1"),
    ("hadith about intentions determining deeds",        "bukhari:1"),
    ("حديث عن النية في الهجرة",                          "bukhari:1"),
    ("حديث إزالة الأذى من الطريق من شعب الإيمان",       "muslim:153"),
    ("الإيمان شعب كثيرة أعلاها التوحيد",                "muslim:153"),
    ("حديث الإسلام مبني على خمسة أشياء",                "bukhari:8"),
    ("the five pillars of Islam hadith",                 "bukhari:8"),
    ("حديث من غش فليس منا",                             "muslim:(any)"),
    ("الآية التي تقول إن الله لا تأخذه سنة ولا نوم",     "quran:2:255"),
    ("verse about Allah never being overtaken by sleep", "quran:2:255"),
    ("لا إكراه في الدين",                                "quran:2:256"),
    ("الآية التي فيها أن الله خلق الموت والحياة ليبتلينا", "quran:67:2"),
]
CASES = [(q, g) for q, g in CASES if not g.endswith("(any)")]
TARGETS = sorted({g for _, g in CASES})

CONTAIN = 0.80
MIN_TOK = 6


def gold_family(recs, by_id, gid):
    """All records carrying the same report. Ayahs are unique, so they stand alone."""
    if gid.startswith("quran:"):
        return {gid}
    g = set(by_id[gid]["match_text"].split())
    fam = {gid}
    for r in recs:
        t = set(r["match_text"].split())
        d = min(len(g), len(t))
        if d >= MIN_TOK and len(g & t) / d >= CONTAIN:
            fam.add(r["id"])
    return fam


class Bm25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        toks = [d.split() for d in docs]
        self.len = np.array([len(t) for t in toks], dtype=np.float32)
        self.avg = float(self.len.mean()) or 1.0
        self.post = defaultdict(list)
        for i, t in enumerate(toks):
            for w, c in Counter(t).items():
                self.post[w].append((i, c))
        self.N = len(docs)
        self.idf = {w: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5))
                    for w, p in self.post.items()}

    def score(self, query):
        s = np.zeros(self.N, dtype=np.float32)
        for w in set(query.split()):
            p = self.post.get(w)
            if not p:
                continue
            idf = self.idf[w]
            for i, c in p:
                s[i] += idf * c * (self.k1 + 1) / (
                    c + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return s


def minmax(x):
    lo, hi = float(x.min()), float(x.max())
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def rank_of(scores, ids, fam):
    for j, k in enumerate(np.argsort(-scores)):
        if ids[k] in fam:
            return j + 1
    return None


def main():
    model_name = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    is_e5 = "e5" in model_name.lower()
    from sentence_transformers import SentenceTransformer

    with open(CORPUS, encoding="utf-8") as f:
        allrecs = [json.loads(l) for l in f]
    by_id = {r["id"]: r for r in allrecs}
    fams = {g: gold_family(allrecs, by_id, g) for g in TARGETS}

    random.seed(450)
    keep = set().union(*fams.values())
    pool = [r for r in allrecs if r["id"] not in keep]
    sl = [by_id[i] for i in keep if i in by_id] + random.sample(pool, n - len(keep))
    random.shuffle(sl)
    ids = [r["id"] for r in sl]
    docs = [r["match_text"] for r in sl]

    qp, pp = ("query: ", "passage: ") if is_e5 else ("", "")
    m = SentenceTransformer(model_name, device="mps")
    t0 = time.time()
    M = m.encode([pp + d[:700] for d in docs], batch_size=64, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
    emb_s = time.time() - t0
    bm = Bm25(docs)
    Q = m.encode([qp + q for q, _ in CASES], normalize_embeddings=True, convert_to_numpy=True)
    D = Q @ M.T

    print(f"model={model_name} dim={M.shape[1]} slice={n}")
    print(f"  embed {n} in {emb_s:.0f}s -> 40,389 in ~{40389/(n/emb_s)/60:.1f} min")
    print(f"  gold family sizes: " + ", ".join(f"{g}={len(f)}" for g, f in fams.items()))
    print()

    res = defaultdict(list)
    for i, (q, gid) in enumerate(CASES):
        fam = fams[gid]
        lex = bm.score(normalize(q))
        # Weighted sum on min-max normalized scores. RRF was tried first and hurt: it let an
        # uninformative BM25 ranking drag a correct dense rank-1 down to rank 7.
        hyb = 0.65 * minmax(D[i]) + 0.35 * minmax(lex)
        rd, rl, rh = (rank_of(D[i], ids, fam), rank_of(lex, ids, fam), rank_of(hyb, ids, fam))
        res["dense"].append(rd); res["bm25"].append(rl); res["hybrid"].append(rh)
        f = lambda r: ("  1 " if r == 1 else (f"{r:>4d}" if r else " -- "))
        print(f"  d{f(rd)} b{f(rl)} h{f(rh)} | {q[:46]:46s} {gid}")

    print()
    for k in ("dense", "bm25", "hybrid"):
        v = res[k]
        print(f"  {k:7s} hit@1 {sum(1 for r in v if r==1):2d}/{len(v)}  "
              f"hit@3 {sum(1 for r in v if r and r<=3):2d}/{len(v)}  "
              f"hit@10 {sum(1 for r in v if r and r<=10):2d}/{len(v)}  "
              f"MRR {np.mean([1/r if r else 0 for r in v]):.3f}")


if __name__ == "__main__":
    main()
