#!/usr/bin/env python3
"""Compare embedding models for Isnad retrieval, using sentence-transformers on the Apple GPU.

Shows the rank of the intended record AND the top hit's own text, because several records can be
legitimately correct: the five-pillars hadith appears in four collections, so a "wrong" top-1 may
be the right answer in a different book. A rank number alone would mislead.

Usage: python eval/probe_st.py <model> [slice] [--e5]
"""
import json, os, random, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _arabic import plain

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
]
TARGETS = sorted({t for _, t in CASES})


def load_slice(n):
    with open(CORPUS, encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]
    by_id = {r["id"]: r for r in recs}
    random.seed(450)
    pool = [r for r in recs if r["id"] not in TARGETS]
    sl = [by_id[t] for t in TARGETS] + random.sample(pool, n - len(TARGETS))
    random.shuffle(sl)
    return sl


def main():
    model_name = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else 3000
    is_e5 = "--e5" in sys.argv or "e5" in model_name.lower()
    from sentence_transformers import SentenceTransformer

    sl = load_slice(n)
    qp, pp = ("query: ", "passage: ") if is_e5 else ("", "")
    print(f"model={model_name}  slice={len(sl)}  e5_prefix={is_e5}")

    t0 = time.time()
    m = SentenceTransformer(model_name, device="mps")
    print(f"  load {time.time()-t0:.1f}s  dim={m.get_sentence_embedding_dimension()}")

    texts = [pp + plain(r["matn"])[:700] for r in sl]
    t0 = time.time()
    M = m.encode(texts, batch_size=64, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False)
    dt = time.time() - t0
    print(f"  embed {len(texts)}: {dt:.1f}s ({len(texts)/dt:.0f}/s) "
          f"-> 40,389 in ~{40389/(len(texts)/dt)/60:.1f} min")

    ids = [r["id"] for r in sl]
    Q = m.encode([qp + q for q, _ in CASES], normalize_embeddings=True, convert_to_numpy=True)
    t0 = time.time()
    S = Q @ M.T
    print(f"  search: {1000*(time.time()-t0):.1f}ms for {len(CASES)} queries\n")

    hit1 = hit5 = 0
    for i, (q, gold) in enumerate(CASES):
        order = np.argsort(-S[i])
        rank = next((j + 1 for j, k in enumerate(order) if ids[k] == gold), None)
        if rank == 1: hit1 += 1
        if rank and rank <= 5: hit5 += 1
        top = sl[order[0]]
        flag = "OK  " if rank == 1 else (f"r{rank:<3d}" if rank else "MISS")
        print(f"  [{flag}] {q[:44]:44s} gold={gold}")
        print(f"         top1={top['id']:14s} sim={S[i][order[0]]:.3f}  {plain(top['matn'])[:95]}")
    print(f"\n  hit@1 {hit1}/{len(CASES)}   hit@5 {hit5}/{len(CASES)}")


if __name__ == "__main__":
    main()
