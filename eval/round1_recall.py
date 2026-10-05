#!/usr/bin/env python3
"""Does round one of the full knockout find the answer? Measured on the one group that matters.

Round one's only job is that the group holding the described text picks it. Every other group
can only add false finalists, which later rounds remove. So round-one recall can be measured
by asking just the gold group's Choice - a few questions instead of eight million tokens.

Also answers two design questions at the same cost:
  * diacritics: does round one lose anything without them? (they halve the token bill)
  * language: round one shows Arabic only; can Jev match an English description to it?

Usage: python eval/round1_recall.py
"""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from _arabic import plain
from decide import load_key
from search import Isnad
import knockout as K

CASES = [
    ("حديث عن أن الأعمال بالنيات", ["bukhari:1", "bukhari:5070", "bukhari:6689", "bukhari:6953",
                                     "muslim:4927", "tirmidhi:1647", "nasai:75", "bukhari:2529"]),
    ("hadith about intentions determining deeds", ["bukhari:1", "bukhari:5070", "bukhari:6689",
                                                   "bukhari:6953", "muslim:4927", "tirmidhi:1647"]),
    ("لا إكراه في الدين", ["quran:2:256"]),
    ("الآية اللي فيها لا تأخذه سنة ولا نوم", ["quran:2:255"]),
    ("verse about Allah never being overtaken by sleep", ["quran:2:255"]),
    ("حديث إن الفقيه أشد على الشيطان من ألف عابد", ["ibnmajah:222", "tirmidhi:2681"]),
    ("the hadith about the five pillars of Islam", ["bukhari:8", "muslim:113", "muslim:114",
                                                    "muslim:116", "nasai:5001", "tirmidhi:2609"]),
    ("حديث من غش فليس مني", ["muslim:283", "muslim:284", "ibnmajah:2224", "tirmidhi:1315"]),
]


async def main():
    print("RAN: python eval/round1_recall.py")
    load_key()
    from typesafe_sdk import AsyncTypeSafeClient, Choice
    ix = Isnad()
    corpus = K.Corpus(ix)
    rec_to_item = {}
    for ii, it in enumerate(corpus.items):
        rec_to_item[ix.recs[it["rec"]]["id"]] = ii
        for c in it["copies"]:
            rec_to_item[ix.recs[c]["id"]] = ii
    pos = {item: p for p, item in enumerate(corpus.order)}

    async with AsyncTypeSafeClient() as client:
        totals = {"diacritics": 0, "plain": 0}
        for q, golds in CASES:
            gold_items = {rec_to_item[g] for g in golds if g in rec_to_item}
            # the first gold item in the fixed order, and the group of 20 it falls into
            first = min(gold_items, key=lambda i: pos[i])
            start = (pos[first] // K.GROUP) * K.GROUP
            group = corpus.order[start:start + K.GROUP]
            row = []
            for mode in ("diacritics", "plain"):
                crit, km = {}, {}
                for j, item in enumerate(group):
                    t = corpus.items[item]["text"]
                    t = t if mode == "diacritics" else plain(t)
                    crit[f"c{j}"] = K._tag(corpus.items[item]["kind"]) + t
                    km[f"c{j}"] = item
                crit[K.NO_MATCH] = K.NO_MATCH_DESC
                r = await client.system_one(state={"description": q}, model=K.MODEL, questions={
                    "g": Choice(instructions=K.ROUND1_INSTRUCTIONS, criteria=crit)})
                a = r.answers["g"]
                probs = {k: float(v) for k, v in (a.probabilities or {}).items()}
                picked = km.get(a.choice)
                runner = sorted(((k, p) for k, p in probs.items() if k not in (a.choice, K.NO_MATCH)),
                                key=lambda kp: -kp[1])
                survive = picked in gold_items or (runner and runner[0][1] >= K.RUNNER_UP
                                                   and km.get(runner[0][0]) in gold_items)
                totals[mode] += bool(survive)
                gp = max((probs.get(k, 0) for k, it in km.items() if it in gold_items), default=0)
                row.append(f"{mode[:5]}: {'OK  ' if survive else 'MISS'} p_gold={gp:.2f}")
            print(f"  {' | '.join(row)}  | {q[:46]}")
        n = len(CASES)
        print(f"\nround-one recall: diacritics {totals['diacritics']}/{n}, plain {totals['plain']}/{n}")


asyncio.run(main())
