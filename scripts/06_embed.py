#!/usr/bin/env python3
"""Embed the corpus and write the runtime index to data/index/.

Model: intfloat/multilingual-e5-base. Chosen on measurement, not reputation — against BAAI/bge-m3
on the same slice it tied or won on every metric (hybrid hit@1 8/11, MRR 0.776 vs 0.745) while
embedding 3.6x faster at 768 dimensions instead of 1024. eval/retrieval_eval.py reproduces it.

e5 requires its prefixes: documents are embedded as "passage: …" and queries as "query: …".
Dropping them costs real accuracy, so the prefix lives in _common.py where both sides read it.

Outputs:
  data/index/embeddings.f16.npy — (N, 768) float16, L2-normalized, row i matches records.jsonl i
  data/index/records.jsonl      — the fields the interface needs, nothing more
  data/index/meta.json          — model, dimensions, counts, build time

Usage: python scripts/06_embed.py [--limit N]
"""
import json, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CORPUS, ROOT, ran, say

INDEX = os.path.join(ROOT, "data", "index")
MODEL = "intfloat/multilingual-e5-base"
DOC_PREFIX = "passage: "
MAX_CHARS = 700          # p95 of matn length is 468 normalized chars; 700 covers nearly all

# Only what the interface and the citation need. corpus.jsonl keeps everything else.
KEEP = ("id", "kind", "collection", "collection_key", "ref", "text", "matn", "match_text",
        "grade", "grade_raw", "grade_basis", "grade_note", "severity", "severity_ar", "action",
        "scope", "graders", "section", "surah", "surah_name", "ayah", "number", "split_rule")


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    ran(f"python scripts/06_embed.py{' --limit ' + str(limit) if limit else ''}")

    with open(os.path.join(CORPUS, "corpus.jsonl"), encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]
    if limit:
        recs = recs[:limit]
    recs = [r for r in recs if r["match_text"].strip()]
    say(f"\n  records: {len(recs)}")

    from sentence_transformers import SentenceTransformer
    import torch
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    say(f"  model: {MODEL} on {dev}")
    m = SentenceTransformer(MODEL, device=dev)
    dim = m.get_sentence_embedding_dimension()

    texts = [DOC_PREFIX + r["match_text"][:MAX_CHARS] for r in recs]
    t0 = time.time()
    M = m.encode(texts, batch_size=64, normalize_embeddings=True, convert_to_numpy=True,
                 show_progress_bar=True)
    dt = time.time() - t0
    say(f"  embedded in {dt/60:.1f} min ({len(texts)/dt:.0f}/s)")

    os.makedirs(INDEX, exist_ok=True)
    # float16 halves the file with no measurable retrieval cost: cosine scores agree to ~1e-3,
    # far below the gaps that decide a ranking.
    Mh = M.astype(np.float16)
    np.save(os.path.join(INDEX, "embeddings.f16.npy"), Mh)
    say(f"  wrote   data/index/embeddings.f16.npy  "
        f"({os.path.getsize(os.path.join(INDEX,'embeddings.f16.npy'))/1e6:.1f} MB)")

    with open(os.path.join(INDEX, "records.jsonl"), "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps({k: r[k] for k in KEEP if k in r}, ensure_ascii=False) + "\n")
    say(f"  wrote   data/index/records.jsonl  "
        f"({os.path.getsize(os.path.join(INDEX,'records.jsonl'))/1e6:.1f} MB)")

    # Round-trip check: float16 must not have moved any score enough to matter.
    probe = M[:256] @ M[:256].T
    probe16 = Mh[:256].astype(np.float32) @ Mh[:256].astype(np.float32).T
    err = float(np.abs(probe - probe16).max())
    say(f"  float16 max cosine error on a 256x256 probe: {err:.2e}")

    json.dump({"model": MODEL, "dim": dim, "records": len(recs), "doc_prefix": DOC_PREFIX,
               "query_prefix": "query: ", "max_chars": MAX_CHARS, "dtype": "float16",
               "f16_max_cosine_error": err, "device": dev,
               "built": time.strftime("%Y-%m-%dT%H:%M:%S")},
              open(os.path.join(INDEX, "meta.json"), "w"), ensure_ascii=False, indent=1)
    say("  wrote   data/index/meta.json")
    say("\nnext: python scripts/07_search_smoke.py")


if __name__ == "__main__":
    main()
