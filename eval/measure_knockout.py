#!/usr/bin/env python3
"""Measure what a full-corpus Jev knockout would cost, before building one.

A knockout over all 40,389 texts in groups of 12 needs about 3,366 Choice questions in its
first round alone. Rather than guess its cost, this sends ONE real request carrying G groups of
12, times it, reads the token usage the API reports, and extrapolates.

Usage: python eval/measure_knockout.py [groups]
"""
import json, os, random, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from decide import load_key
from cascade import PICK_INSTRUCTIONS, NO_MATCH_DESC, MAX_CAND_CHARS
import sqlite3

G = int(sys.argv[1]) if len(sys.argv) > 1 else 50
TOTAL = 40389


def main():
    print(f"RAN: python eval/measure_knockout.py {G}")
    load_key()
    from typesafe_sdk import Choice, TypeSafeClient
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "data", "index", "display.db"))
    rows = db.execute("select id, matn from display").fetchall()
    random.seed(450)
    pick = random.sample(rows, G * 12)

    questions = {}
    for g in range(G):
        crit = {f"c{i}": (m or "")[:MAX_CAND_CHARS] for i, (_, m) in enumerate(pick[g*12:(g+1)*12])}
        crit["no_match"] = NO_MATCH_DESC
        questions[f"g{g}"] = Choice(instructions=PICK_INSTRUCTIONS, criteria=crit)

    with TypeSafeClient() as c:
        t = time.time()
        r = c.system_one(state={"description": "حديث عن أن الأعمال بالنيات"},
                         questions=questions, model="jev-latest")
        dt = time.time() - t

    usage = getattr(r, "usage", None)
    print(f"\none request: {G} groups x 12 = {G*12} texts judged in {dt:.1f}s")
    print(f"usage reported by the API: {usage}")
    no_match = sum(1 for g in range(G) if r.answers[f"g{g}"].choice == "no_match")
    print(f"groups answering no_match: {no_match}/{G}")

    q_round1 = -(-TOTAL // 12)
    q_all = q_round1 + -(-q_round1 // 12) + -(-q_round1 // 144) + 3
    calls = -(-q_round1 // G)
    print(f"\nfull knockout of {TOTAL:,} texts:")
    print(f"  round-1 questions: {q_round1:,}   all rounds: ~{q_all:,}")
    print(f"  round-1 requests of this size: {calls}")
    print(f"  if all {calls} ran fully in parallel: ~{dt:.1f}s for round 1 (best case)")
    print(f"  if run {4} at a time: ~{dt*calls/4/60:.1f} min for round 1")
    if usage is not None:
        try:
            tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None) \
                or (usage.get("input_tokens") if isinstance(usage, dict) else None)
            if tok:
                print(f"  tokens per search, round 1 alone: ~{tok * calls:,}  "
                      f"(vs the current tournament: one request of 10 groups)")
        except Exception:
            pass


if __name__ == "__main__":
    main()
