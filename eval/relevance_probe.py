#!/usr/bin/env python3
"""Which wording of topic mode's relevance question lets the right texts in and keeps the wrong
ones out? Asks Jev each wording over fixed texts with known answers; prints P(yes) per text.
Questions carry their text, as in production (cascade._judge).

Usage: python eval/relevance_probe.py      (spends one Jev request per wording per description)
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import cascade                              # noqa: E402
from decide import load_key                 # noqa: E402
from search import Isnad                    # noqa: E402

PROBES = {   # description: [(record id, should be listed)]
    "ايه عن النوم": [("quran:2:255", 1), ("quran:25:47", 1), ("quran:78:9", 1), ("quran:30:23", 1),
                     ("quran:84:17", 0), ("quran:53:54", 0), ("quran:55:10", 0), ("quran:78:2", 0)],
    "حديث عن الصدق": [("tirmidhi:1971", 1), ("muslim:6638", 1), ("nasai:2582", 0),
                      ("muslim:2355", 0), ("bukhari:2644", 0)],
    "ايه عن بر الوالدين": [("quran:17:23", 1), ("quran:31:14", 1), ("quran:78:2", 0),
                           ("quran:36:6", 0)],
    "حديث عن اختراع الطائرة والسفر إلى القمر": [("bukhari:3638", 0), ("quran:54:1", 0)],
}
# Production style (cascade._judge): each question carries its own text, no index into a list.
WORDINGS = {
    "says something": (
        "The user remembers a text by something it says and describes it in `description`. Here "
        "is a {kind}: \"{text}\". Does this text say something about that subject: state it, "
        "describe it, command or forbid it, or deny it of someone? Answer no if the text only "
        "shares a word with the description, or says nothing about the subject."),
    "same sense (live)": cascade.RELEVANCE_INSTRUCTIONS,
}


async def main():
    from typesafe_sdk import AsyncTypeSafeClient, Noul
    load_key()
    print("RAN: python eval/relevance_probe.py")
    ix = Isnad()
    by_id = {r["id"]: i for i, r in enumerate(ix.recs)}
    client = AsyncTypeSafeClient()
    try:
        for name, wording in WORDINGS.items():
            ok = total = 0
            for desc, items in PROBES.items():
                recs = []
                for rid, _ in items:
                    rec = dict(ix.recs[by_id[rid]]); rec.update(ix.display(rid)); recs.append(rec)
                qs = {f"t{i}": Noul(instructions=cascade._judge(wording, rec))
                      for i, rec in enumerate(recs)}
                r = await client.system_one(state={"description": desc}, questions=qs,
                                            model=cascade.MODEL)
                cells = []
                for i, (rid, want) in enumerate(items):
                    p = float(r.answers[f"t{i}"].noul)
                    good = (p >= cascade.TOPIC_MIN_REL) == bool(want)
                    ok += good; total += 1
                    cells.append(f"{rid.split(':', 1)[1]}={p:.2f}{'' if good else '!'}")
                print(f"  {name:20s} {desc[:22]:22s} " + " ".join(cells))
            print(f"{name:20s} correct {ok}/{total}  (! = wrong side of {cascade.TOPIC_MIN_REL})")
    finally:
        await client.aclose()

asyncio.run(main())
