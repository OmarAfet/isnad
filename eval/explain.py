#!/usr/bin/env python3
"""Why did Isnad answer this? Trace one query through stage one, without spending Jev calls.

Prints the language and kind cue search saw, the shortlist Jev would receive (ids, kinds, fused
scores, first words), how many of it are Qur'an verses, where any expected ids rank, and which
texts topic mode would judge. Use it before changing retrieval, and after, on the same query.

Usage: python eval/explain.py "<query>" [--expect quran:2:255,quran:25:47] [--top 30]
       ISNAD_ENCODER=onnx (default here, as deployed)
"""
import os, sys

os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import cascade                                   # noqa: E402
from search import Isnad, wanted_kind            # noqa: E402
from _lang import detect                         # noqa: E402
from _surfaces import surface_text               # noqa: E402


def main():
    args = [a for a in sys.argv[1:]]
    expect = []
    top = 30
    if "--expect" in args:
        i = args.index("--expect"); expect = args[i + 1].split(","); del args[i:i + 2]
    if "--top" in args:
        i = args.index("--top"); top = int(args[i + 1]); del args[i:i + 2]
    q = " ".join(args)
    print(f'RAN: python eval/explain.py "{q}"' + (f" --expect {','.join(expect)}" if expect else ""))
    ix = Isnad()
    lang = detect(q)
    toks = set(surface_text("ar" if lang in ("ar", "ur") else lang, q).split())
    print(f"language {lang}   tokens {sorted(toks)}   kind cue {wanted_kind(toks)}   encoder {ix.encoder}")
    cands = ix.search(q, k=cascade.NET)
    ayahs = [i for i, c in enumerate(cands) if c["kind"] == "ayah"]
    print(f"shortlist {len(cands)}: {len(ayahs)} verses, {len(cands) - len(ayahs)} hadith; "
          f"first verse at rank {ayahs[0] + 1 if ayahs else '-'}")
    for i, c in enumerate(cands[:top]):
        print(f"  {i + 1:3d} {c['score']:6.2f} {c['kind']:6s} {c['id']:16s} {(c.get('matn') or '')[:60]}")
    pool = cascade._topic_pool(cands)
    print(f"topic pool ({len(pool)} judged if broad): "
          f"{sum(1 for c in pool if c['kind'] == 'ayah')} verses")
    for gid in expect:
        rank = next((i + 1 for i, c in enumerate(cands)
                     if c["id"] == gid or any(v["id"] == gid for v in c.get("variants") or [])),
                    None)
        print(f"expect {gid:16s} rank {rank if rank else 'NOT IN SHORTLIST'}"
              f"{'' if not rank else ('  in topic pool' if any(c['id'] == gid for c in pool) else '  outside topic pool')}")


if __name__ == "__main__":
    main()
