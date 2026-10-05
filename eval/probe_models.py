#!/usr/bin/env python3
"""Decide the embedding model before committing to embedding 40,389 records.

The product promise is "any language, any phrasing", which only a multilingual semantic model can
keep. The risk is that a model small enough to deploy on a free tier cannot retrieve classical
Arabic from a modern paraphrase. That is worth two minutes to find out and hours to assume.

Runs a handful of hand-written realistic queries against a slice of the corpus that is guaranteed
to contain their answers, and reports the rank of the correct record.

Usage: python eval/probe_models.py <model-name> [slice_size]
"""
import json, os, random, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _arabic import plain

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "..", "data", "corpus", "corpus.jsonl")

# Hand-written, meaning-first queries: what someone actually types when they remember the sense
# and not the wording. Mixed Arabic and English on purpose.
CASES = [
    ("حديث عن أن الأعمال تكون بحسب النيات",            "bukhari:1"),
    ("hadith about intentions determining deeds",        "bukhari:1"),
    ("حديث إزالة الأذى من الطريق من شعب الإيمان",       "muslim:153"),
    ("حديث الإسلام مبني على خمسة أشياء",                "bukhari:8"),
    ("the five pillars of Islam hadith",                 "bukhari:8"),
    ("الآية التي تقول إن الله لا تأخذه سنة ولا نوم",     "quran:2:255"),
    ("verse about Allah never being overtaken by sleep", "quran:2:255"),
    ("حديث عن النية في الهجرة",                          "bukhari:1"),
]
TARGETS = sorted({t for _, t in CASES})


def load_slice(n):
    with open(CORPUS, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]
    by_id = {r["id"]: r for r in recs}
    missing = [t for t in TARGETS if t not in by_id]
    if missing:
        raise SystemExit(f"targets absent from corpus: {missing}")
    random.seed(450)
    pool = [r for r in recs if r["id"] not in TARGETS]
    sl = [by_id[t] for t in TARGETS] + random.sample(pool, n - len(TARGETS))
    random.shuffle(sl)
    return sl


def main():
    model_name = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    from fastembed import TextEmbedding

    sl = load_slice(n)
    # e5-family models are trained with these prefixes and lose accuracy without them.
    is_e5 = "e5" in model_name.lower()
    qp, pp = ("query: ", "passage: ") if is_e5 else ("", "")

    print(f"model={model_name}  slice={len(sl)}  e5_prefix={is_e5}")
    t0 = time.time()
    emb = TextEmbedding(model_name=model_name)
    print(f"  load: {time.time()-t0:.1f}s")

    texts = [pp + plain(r["matn"])[:800] for r in sl]
    t0 = time.time()
    M = np.array(list(emb.embed(texts)), dtype=np.float32)
    dt = time.time() - t0
    M /= np.linalg.norm(M, axis=1, keepdims=True) + 1e-9
    print(f"  embed {len(texts)} docs: {dt:.1f}s  ({len(texts)/dt:.0f}/s)  dim={M.shape[1]}")
    print(f"  projected for 40,389 docs: {40389/(len(texts)/dt)/60:.1f} min")

    ids = [r["id"] for r in sl]
    Q = np.array(list(emb.query_embed([qp + q for q, _ in CASES])
                      if is_e5 else emb.embed([q for q, _ in CASES])), dtype=np.float32)
    Q /= np.linalg.norm(Q, axis=1, keepdims=True) + 1e-9

    t0 = time.time()
    S = Q @ M.T
    print(f"  search {len(CASES)} queries x {len(sl)} docs: {1000*(time.time()-t0):.1f}ms total\n")

    ranks = []
    for i, (q, gold) in enumerate(CASES):
        order = np.argsort(-S[i])
        rank = next((j + 1 for j, k in enumerate(order) if ids[k] == gold), None)
        ranks.append(rank)
        top = ids[order[0]]
        flag = "OK " if rank == 1 else ("r%-3d" % rank if rank else "MISS")
        print(f"  [{flag}] {q[:46]:46s} gold={gold:12s} top1={top:14s} sim={S[i][order[0]]:.3f}")
    hit1 = sum(1 for r in ranks if r == 1)
    hit5 = sum(1 for r in ranks if r and r <= 5)
    print(f"\n  hit@1 {hit1}/{len(CASES)}   hit@5 {hit5}/{len(CASES)}")


if __name__ == "__main__":
    main()
