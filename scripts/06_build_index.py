#!/usr/bin/env python3
"""Build the runtime index: per-language embedding matrices, lexical surfaces, and a display store.

Three problems solved by the layout, not by hoping:

1. ONE RECORD, MANY SURFACES. bukhari:1 is one record with an Arabic text and up to eight
   published translations. Each surface gets its own embedding row; every row points back to the
   same record. A query in Urdu matches the Urdu surface and still answers with the Arabic.

2. MEMORY. All languages in one matrix is ~400 MB, which does not fit the free tier the challenge
   suggests. Each language gets its own file, memory-mapped and opened only when a query is
   actually in that language. Arabic plus one other is the working set.

3. DISPLAY TEXT. The previous records.jsonl reached 95 MB because it carried every text inline,
   and loading that as Python objects costs several hundred megabytes. Display text now lives in
   SQLite and is read by id for the handful of records actually shown.

Usage: python scripts/06_build_index.py [--limit N] [--langs ar,en,ur]
"""
import json, os, sqlite3, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CORPUS, LANG_NAME_AR, ROOT, ran, say

INDEX = os.path.join(ROOT, "data", "index")
MODEL = "intfloat/multilingual-e5-base"
DOC_PREFIX = "passage: "
QUERY_PREFIX = "query: "
MAX_CHARS = 700

# Kept in memory at query time: small, and enough to rank and to explain a ranking.
SLIM = ("id", "kind", "collection", "collection_key", "ref", "grade", "grade_raw", "grade_basis",
        "grade_note", "severity", "severity_ar", "action", "scope", "section", "number",
        "surah_name", "ayah", "split_rule")


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    only = (sys.argv[sys.argv.index("--langs") + 1].split(",")
            if "--langs" in sys.argv else None)
    ran("python scripts/06_build_index.py" + (f" --limit {limit}" if limit else "")
        + (f" --langs {','.join(only)}" if only else ""))

    with open(os.path.join(CORPUS, "corpus.jsonl"), encoding="utf-8") as f:
        recs = [json.loads(l) for l in f]
    if limit:
        recs = recs[:limit]
    recs = [r for r in recs if r["match_text"].strip()]
    say(f"\n  records: {len(recs)}")

    # Which languages actually have surfaces, and how many.
    langs = {"ar": len(recs)}
    for r in recs:
        for lg in r.get("surfaces", {}):
            langs[lg] = langs.get(lg, 0) + 1
    if only:
        langs = {k: v for k, v in langs.items() if k in only}
    say("  surfaces per language:")
    for lg, n in sorted(langs.items(), key=lambda kv: -kv[1]):
        say(f"    {lg}  {n:6d}  {LANG_NAME_AR.get(lg, lg)}")

    os.makedirs(INDEX, exist_ok=True)

    # --- slim records, in corpus order; row -> record index is what the matrices store ---
    # Row indices in every rows_*.npy point into THIS file, so it must be rebuilt whenever the
    # corpus changes. It is cheap, so it always is.
    with open(os.path.join(INDEX, "records.jsonl"), "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps({k: r.get(k) for k in SLIM}, ensure_ascii=False) + "\n")
    say(f"\n  wrote   records.jsonl "
        f"({os.path.getsize(os.path.join(INDEX,'records.jsonl'))/1e6:.1f} MB)")

    # --- display store ---
    db = os.path.join(INDEX, "display.db")
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE display (
        id TEXT PRIMARY KEY, text TEXT, matn TEXT, sanad TEXT,
        graders TEXT, translations TEXT)""")
    con.executemany("INSERT INTO display VALUES (?,?,?,?,?,?)", [
        (r["id"], r.get("text"), r.get("matn"), r.get("sanad"),
         json.dumps(r.get("graders") or [], ensure_ascii=False),
         json.dumps(r.get("translations") or {}, ensure_ascii=False)) for r in recs])
    con.commit()
    con.execute("VACUUM")
    con.close()
    say(f"  wrote   display.db ({os.path.getsize(db)/1e6:.1f} MB)")

    # --- lexical surfaces + embeddings, per language ---
    from sentence_transformers import SentenceTransformer
    import torch
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    say(f"  model: {MODEL} on {dev}\n")
    m = SentenceTransformer(MODEL, device=dev)
    dim = m.get_embedding_dimension() if hasattr(m, "get_embedding_dimension") \
        else m.get_sentence_embedding_dimension()

    built = {}
    force = "--force" in sys.argv
    for lg in sorted(langs, key=lambda k: (k != "ar", k)):
        if not force and os.path.exists(os.path.join(INDEX, f"emb_{lg}.f16.npy")) \
                and os.path.exists(os.path.join(INDEX, f"rows_{lg}.npy")):
            n = len(np.load(os.path.join(INDEX, f"rows_{lg}.npy")))
            built[lg] = n
            say(f"    {lg}: {n:6d} rows  already embedded, skipped (--force to redo)")
            continue
        rows, texts = [], []
        for i, r in enumerate(recs):
            t = r["match_text"] if lg == "ar" else (r.get("surfaces") or {}).get(lg)
            if t and t.strip():
                rows.append(i)
                texts.append(t)
        if not rows:
            continue
        with open(os.path.join(INDEX, f"surface_{lg}.jsonl"), "w", encoding="utf-8") as f:
            for i, t in zip(rows, texts):
                f.write(json.dumps({"i": i, "t": t}, ensure_ascii=False) + "\n")
        t0 = time.time()
        M = m.encode([DOC_PREFIX + t[:MAX_CHARS] for t in texts], batch_size=64,
                     normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
        np.save(os.path.join(INDEX, f"emb_{lg}.f16.npy"), M.astype(np.float16))
        np.save(os.path.join(INDEX, f"rows_{lg}.npy"), np.array(rows, dtype=np.int32))
        mb = os.path.getsize(os.path.join(INDEX, f"emb_{lg}.f16.npy")) / 1e6
        built[lg] = len(rows)
        say(f"    {lg}: {len(rows):6d} rows  {time.time()-t0:5.0f}s  {mb:5.1f} MB")

    json.dump({"model": MODEL, "dim": dim, "records": len(recs),
               "doc_prefix": DOC_PREFIX, "query_prefix": QUERY_PREFIX,
               "max_chars": MAX_CHARS, "dtype": "float16", "device": dev,
               "languages": {lg: int(len(np.load(os.path.join(INDEX, f)))) for f in
                             sorted(os.listdir(INDEX)) if f.startswith("rows_")
                             for lg in [f[5:-4]]},
               "lang_name_ar": LANG_NAME_AR,
               "built": time.strftime("%Y-%m-%dT%H:%M:%S")},
              open(os.path.join(INDEX, "meta.json"), "w"), ensure_ascii=False, indent=1)
    total = sum(os.path.getsize(os.path.join(INDEX, f)) for f in os.listdir(INDEX))
    say(f"\n  index total: {total/1e6:.0f} MB across {len(built)} languages")
    say("  wrote   meta.json")


if __name__ == "__main__":
    main()
