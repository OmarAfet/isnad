#!/usr/bin/env python3
"""Is the request classifier stable? Asks Jev the round-one "what is asked" Choice N times per
description and prints P(find_text) / P(general_ruling) / P(personal_case) per run.

Usage: python eval/ask_probe.py [--runs 3]       (one Jev request per run, all descriptions)
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import cascade                     # noqa: E402
from decide import load_key        # noqa: E402

DESCRIPTIONS = {   # description: the right class
    "ايه عن النوم": "find_text", "ايه عن بر الوالدين": "find_text", "آية عن الصبر": "find_text",
    "حديث عن الغضب": "find_text", "حديث عن الكذب": "find_text", "verse about sleep": "find_text",
    "ما حكم حديث إن الفقيه أشد على الشيطان من ألف عابد": "find_text",
    "ماحكم الزنا": "general_ruling", "ما حكم الربا": "general_ruling",
    "هل يجوز لي الجمع بين الصلاتين في السفر؟": "personal_case",
    "what is the ruling on interest in Islam": "general_ruling",
    "ما حكم الكذب": "general_ruling",
}


async def main():
    from typesafe_sdk import AsyncTypeSafeClient, Choice
    load_key()
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3
    print(f"RAN: python eval/ask_probe.py --runs {runs}")
    client = AsyncTypeSafeClient()
    wrong = total = 0
    try:
        for desc, want in DESCRIPTIONS.items():
            cells = []
            for _ in range(runs):
                r = await client.system_one(
                    state={"description": desc},
                    questions={"ask": Choice(instructions=cascade.ASK_INSTRUCTIONS,
                                             criteria=cascade.ASK_OPTIONS)},
                    model=cascade.MODEL)
                p = {k: float(v) for k, v in (r.answers["ask"].probabilities or {}).items()}
                ruling = p.get("general_ruling", 0) + p.get("personal_case", 0)
                got = ("find_text" if ruling < cascade.RULING_THRESHOLD else
                       "personal_case" if p.get("personal_case", 0) >= p.get("general_ruling", 0)
                       else "general_ruling")
                wrong += got != want; total += 1
                cells.append(f"{p.get('find_text', 0):.2f}/{p.get('general_ruling', 0):.2f}/"
                             f"{p.get('personal_case', 0):.2f}{'' if got == want else '!'}")
            print(f"  {desc[:34]:34s} want {want:14s} " + "  ".join(cells))
    finally:
        await client.aclose()
    print(f"misclassified {wrong}/{total}  (find/general/personal; ! = wrong class)")

asyncio.run(main())
