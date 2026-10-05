#!/usr/bin/env python3
"""Embed every language surface with bounded memory.

06_build_index.py loaded the whole 486 MB corpus as Python objects, several gigabytes, and on a
9 GB machine macOS killed it mid-language without a word of output. This does the same work in
two streaming passes so peak memory is the model plus one chunk:

  pass 1  read corpus.jsonl line by line; append (record index, surface text) to one file per
          language. Nothing is held beyond the current line.
  pass 2  per language, load only that language's strings, encode them in chunks, and write each
          chunk straight into a memory-mapped float16 matrix on disk.

Resumable: a language whose matrix and row file already exist is skipped.

Usage: python scripts/06b_embed_surfaces.py [--langs en,ur] [--force]
"""
import json, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CORPUS, LANG_NAME_AR, ROOT, ran, say

INDEX = os.path.join(ROOT, "data", "index")
MODEL = "intfloat/multilingual-e5-base"
DOC_PREFIX = "passage: "
MAX_CHARS = 700
CHUNK = 2048


def pass_one(langs):
    """Write surface_<lang>.jsonl for every language that lacks one."""
    need = [lg for lg in langs if not os.path.exists(os.path.join(INDEX, f"surface_{lg}.jsonl"))]
    if not need:
        say("  pass 1: all surface files present")
        return
    say(f"  pass 1: streaming corpus for {', '.join(need)}")
    files = {lg: open(os.path.join(INDEX, f"surface_{lg}.jsonl"), "w", encoding="utf-8")
             for lg in need}
    counts = dict.fromkeys(need, 0)
    i = 0
    with open(os.path.join(CORPUS, "corpus.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not r["match_text"].strip():
                continue
            for lg in need:
                t = r["match_text"] if lg == "ar" else (r.get("surfaces") or {}).get(lg)
                if t and t.strip():
                    files[lg].write(json.dumps({"i": i, "t": t}, ensure_ascii=False) + "\n")
                    counts[lg] += 1
            i += 1
    for fh in files.values():
        fh.close()
    for lg in need:
        say(f"    {lg}: {counts[lg]} surfaces")


def pass_two(langs, force):
    from sentence_transformers import SentenceTransformer
    import torch
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = None
    for lg in langs:
        emb = os.path.join(INDEX, f"emb_{lg}.f16.npy")
        rows_p = os.path.join(INDEX, f"rows_{lg}.npy")
        if not force and os.path.exists(emb) and os.path.exists(rows_p):
            say(f"    {lg}: already embedded, skipped")
            continue
        rows, texts = [], []
        with open(os.path.join(INDEX, f"surface_{lg}.jsonl"), encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                rows.append(d["i"])
                texts.append(DOC_PREFIX + d["t"][:MAX_CHARS])
        if model is None:
            model = SentenceTransformer(MODEL, device=dev)
            # Half precision on the GPU roughly doubles throughput and halves memory, which on a
            # 9 GB machine is the difference between finishing and being swapped to a crawl
            # (measured: 39 rows/s in float32 under memory pressure). Scores are compared within
            # each language after z-scoring, so fp16 rounding (~1e-3) cannot shift a ranking.
            if dev != "cpu":
                model.half()
            # Translations of a hadith run 150 to 180 tokens; 256 covers them without paying for
            # e5's 512-token default on every padded batch.
            model.max_seq_length = 256
            dim = (model.get_embedding_dimension() if hasattr(model, "get_embedding_dimension")
                   else model.get_sentence_embedding_dimension())
        tmp = emb + ".part"
        M = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float16, shape=(len(texts), dim))
        t0 = time.time()
        for s in range(0, len(texts), CHUNK):
            chunk = model.encode(texts[s:s + CHUNK], batch_size=64, normalize_embeddings=True,
                                 convert_to_numpy=True, show_progress_bar=False)
            M[s:s + len(chunk)] = chunk.astype(np.float16)
            done = s + len(chunk)
            rate = done / max(time.time() - t0, 1e-6)
            print(f"      {lg} {done}/{len(texts)}  {rate:.0f}/s  "
                  f"eta {(len(texts)-done)/max(rate,1e-6)/60:.1f} min", flush=True)
        M.flush()
        del M
        os.replace(tmp, emb)                     # only a finished matrix gets the real name
        np.save(rows_p, np.array(rows, dtype=np.int32))
        say(f"    {lg}: {len(rows)} rows in {(time.time()-t0)/60:.1f} min "
            f"({os.path.getsize(emb)/1e6:.0f} MB)")
        del texts, rows


def main():
    langs = (sys.argv[sys.argv.index("--langs") + 1].split(",") if "--langs" in sys.argv
             else ["ar", "en", "ur", "id", "tr", "bn", "fr", "ru", "ta"])
    force = "--force" in sys.argv
    ran("python scripts/06b_embed_surfaces.py" + (" --force" if force else ""))
    pass_one(langs)
    pass_two(langs, force)

    meta_p = os.path.join(INDEX, "meta.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    meta["languages"] = {f[5:-4]: int(len(np.load(os.path.join(INDEX, f))))
                         for f in sorted(os.listdir(INDEX)) if f.startswith("rows_")}
    meta["lang_name_ar"] = LANG_NAME_AR
    json.dump(meta, open(meta_p, "w"), ensure_ascii=False, indent=1)
    say(f"  meta.json languages: {meta['languages']}")


if __name__ == "__main__":
    main()
