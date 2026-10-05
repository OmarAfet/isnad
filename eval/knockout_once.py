#!/usr/bin/env python3
"""Run one full-corpus knockout search end to end and report time, rounds and the answer.
Usage: python eval/knockout_once.py "<query>"
"""
import asyncio, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from decide import load_key
from search import Isnad
import knockout as K

q = sys.argv[1]
print(f'RAN: python eval/knockout_once.py "{q}"')
load_key()
ix = Isnad(); corpus = K.Corpus(ix)
print(f"corpus: {len(corpus.items):,} unique texts; round one ~{corpus.round1_tokens:,} tokens")
last = {"t": 0}
def progress(stage, done, total):
    if time.time() - last["t"] > 5 or done == total:
        last["t"] = time.time()
        print(f"  {stage}: {done}/{total} groups  ({time.time()-t0:.0f}s)", flush=True)

async def main():
    from typesafe_sdk import AsyncTypeSafeClient
    async with AsyncTypeSafeClient() as c:
        return await K.run(q, ix, corpus, c, progress=progress)

t0 = time.time()
d = asyncio.run(main())
r = d.get("record") or {}
print(f"\nverdict={d['verdict']} p={d.get('confidence')} rounds={d['jev_rounds']} "
      f"texts_read={d.get('texts_read')} elapsed={d.get('elapsed_s')}s")
if r:
    print(f"answer: {r.get('ref')} | {r.get('grade')} | {(r.get('matn') or '')[:80]}")
for t in (d.get("topic") or [])[:8]:
    print(f"  topic: {t['record']['ref']} | {t['record'].get('grade')} | rel={t['relevance']:.2f}")
