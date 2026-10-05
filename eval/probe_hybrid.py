#!/usr/bin/env python3
"""Compare dense, lexical, and hybrid retrieval on hand-written meaning-first queries.

Three things are being decided at once:
  * is a deployable embedding model good enough on classical Arabic;
  * does a lexical index carry the cases where the user reproduces real wording;
  * does fusing them beat either alone.

Embeds match_text, which is what the real index will hold: the simple-orthography Quran and the
matn with the sanad removed.

Usage: python eval/probe_hybrid.py <model> [slice]
"""
import json, math, os, random, sys, time
from collections import Counter, defaultdict
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _arabic import normalize

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "data", "corpus", "corpus.jsonl")

CASES = [
    ("حديث عن أن الأعمال تكون بحسب النيات",            "bukhari:1"),
    ("hadith about intentions determining deeds",        "bukhari:1"),
    ("حديث إزالة الأذى من الطريق من شعب الإيمان",       "muslim:153"),
    ("حديث الإسلام مبني على خمسة أشياء",                "bukhari:8"),
    ("the five pillars of Islam hadith",                 "bukhari:8"),
    ("الآية التي تقول إن الله لا تأخذه سنة ولا نوم",     "quran:2:255"),
    ("verse about Allah never being overtaken by sleep", "quran:2:255"),
    ("حديث عن النية في الهجرة",                          "bukhari:1"),
    ("آية الكرسي",                                       "quran:2:255"),
    ("لا إكراه في الدين",                                "quran:2:256"),
]
TARGETS = sorted({t for _, t in CASES})


class Bm25:
    """Plain BM25 over normalized tokens. Pure stdlib: it has to run on a free tier next to the
    embedding matrix, and it is the half of retrieval that nails a half-remembered quotation."""
    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.toks = [d.split() for d in docs]
        self.len = np.array([len(t) for t in self.toks], dtype=np.float32)
        self.avg = float(self.len.mean())
        self.post = defaultdict(list)
        for i, t in enumerate(self.toks):
            for w, c in Counter(t).items():
                self.post[w].append((i, c))
        self.N = len(docs)
        self.idf = {w: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5))
                    for w, p in self.post.items()}

    def score(self, query):
        s = np.zeros(self.N, dtype=np.float32)
        for w in set(query.split()):
            if w not in self.post:
                continue
            idf = self.idf[w]
            for i, c in self.post[w]:
                dl = self.len[i]
                s[i] += idf * c * (self.k1 + 1) / (c + self.k1 * (1 - self.b + self.b * dl / self.avg))
        return s


def load_slice(n):
    with open(CORPUS, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]
    by_id = {r["id"]: r for r in recs}
    random.seed(450)
    pool = [r for r in recs if r["id"] not in TARGETS]
    sl = [by_id[t] for t in TARGETS] + random.sample(pool, n - len(TARGETS))
    random.shuffle(sl)
    return sl


def rank_of(scores, ids, gold):
    order = np.argsort(-scores)
    return next((j + 1 for j, k in enumerate(order) if ids[k] == gold), None), ids[order[0]]


def rrf(*rank_lists, k=60):
    """Reciprocal rank fusion: combines rankings without needing the two score scales to agree.
    Dense cosines sit in a narrow high band and BM25 is unbounded, so adding them directly would
    let one drown the other."""
    agg = np.zeros(len(rank_lists[0]), dtype=np.float32)
    for r in rank_lists:
        order = np.argsort(-r)
        for pos, idx in enumerate(order):
            agg[idx] += 1.0 / (k + pos + 1)
    return agg


def main():
    model_name = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    is_e5 = "e5" in model_name.lower()
    from sentence_transformers import SentenceTransformer

    sl = load_slice(n)
    ids = [r["id"] for r in sl]
    docs = [r["match_text"] for r in sl]
    qp, pp = ("query: ", "passage: ") if is_e5 else ("", "")

    m = SentenceTransformer(model_name, device="mps")
    t0 = time.time()
    M = m.encode([pp + d[:700] for d in docs], batch_size=64, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
    print(f"model={model_name} dim={M.shape[1]} slice={n}")
    print(f"  embed: {time.time()-t0:.1f}s -> 40,389 in ~{40389/(n/(time.time()-t0))/60:.1f} min")
    bm = Bm25(docs)

    Q = m.encode([qp + q for q, _ in CASES], normalize_embeddings=True, convert_to_numpy=True)
    D = Q @ M.T
    res = {"dense": [], "bm25": [], "hybrid": []}
    print()
    for i, (q, gold) in enumerate(CASES):
        lex = bm.score(normalize(q))
        hyb = rrf(D[i], lex)
        rd, td = rank_of(D[i], ids, gold)
        rl, tl = rank_of(lex, ids, gold)
        rh, th = rank_of(hyb, ids, gold)
        for k, v in (("dense", rd), ("bm25", rl), ("hybrid", rh)):
            res[k].append(v)
        f = lambda r: ("  1 " if r == 1 else (f"{r:>4d}" if r else " -- "))
        print(f"  dense{f(rd)} bm25{f(rl)} hyb{f(rh)}  | {q[:40]:40s} gold={gold}")
    print()
    for k, v in res.items():
        h1 = sum(1 for r in v if r == 1)
        h5 = sum(1 for r in v if r and r <= 5)
        print(f"  {k:7s} hit@1 {h1}/{len(CASES)}   hit@5 {h5}/{len(CASES)}")


if __name__ == "__main__":
    main()
