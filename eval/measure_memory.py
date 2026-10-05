#!/usr/bin/env python3
"""Peak memory and load time of the search service on a plain CPU, the way a server runs it.

Sizes the host: the API holds the embedding model and, per language asked for, a memory-mapped
matrix plus a BM25 index. Loads the model on CPU in float32 (no MPS, no half precision), then
every language surface, and searches once in each, reporting resident memory after each step.

Usage: python eval/measure_memory.py [--langs ar,en]
"""
import os, resource, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from search import Isnad  # noqa: E402


def peak_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3   # bytes on macOS, KiB on Linux


def main():
    print(f"RAN: python eval/measure_memory.py {' '.join(sys.argv[1:])}".strip())
    t0 = time.time()
    ix = Isnad(device="cpu")
    langs = list(ix.meta["languages"])
    if "--langs" in sys.argv:
        langs = sys.argv[sys.argv.index("--langs") + 1].split(",")
    print(f"records loaded        {time.time() - t0:6.1f} s   peak {peak_mb():7.0f} MB")
    ix.embed_query("تهيئة")
    print(f"model on cpu          {time.time() - t0:6.1f} s   peak {peak_mb():7.0f} MB")
    for lg in langs:
        ix.lang_index(lg)
        print(f"surface {lg:<13} {time.time() - t0:6.1f} s   peak {peak_mb():7.0f} MB")
    for q in ("حديث إنما الأعمال بالنيات", "verse about patience", "hadis tentang niat"):
        t = time.time()
        ix.search(q)
        print(f"search {q[:20]!r:<24} {1000 * (time.time() - t):5.0f} ms  peak {peak_mb():7.0f} MB")


if __name__ == "__main__":
    main()
