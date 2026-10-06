#!/usr/bin/env python3
"""Which approved reference answers a question? One Jev Choice per question, N runs.
Usage: python eval/refer_probe.py [--runs 1]"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import cascade                     # noqa: E402
from decide import load_key        # noqa: E402

CASES = {
    "لماذا يعبد المسلمون الكعبة؟": "objection", "هل القرآن من تأليف محمد ﷺ؟": "objection",
    "هل الإسلام انتشر بالسيف؟": "objection", "لماذا توجد أحكام مختلفة بين العلماء؟": "fiqh",
    "ما معنى التوحيد لشخص لم يسمع بالمصطلح من قبل؟": "term",
    "ترجم كلمة التوحيد إلى الإنجليزية": "term", "لماذا يمنع الإسلام الخمر؟ دين متخلف": "objection",
    "is islam a religion of violence": "objection", "Why do Muslims believe in jihad?": "objection",
    "what does Islam say about tawhid": "creed", "ما رأيك في الإسلام": "objection",
    "ما هي أركان الإيمان": "creed", "متى ولد النبي صلى الله عليه وسلم": "history",
    "ماذا حدث في غزوة بدر": "history", "ما معنى الإحسان": "term", "هل الله في السماء": "creed",
    "why do Muslim women wear hijab": "objection", "what is the meaning of sunnah": "term",
}


async def main():
    from typesafe_sdk import AsyncTypeSafeClient, Choice
    load_key()
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 1
    print(f"RAN: python eval/refer_probe.py --runs {runs}")
    client = AsyncTypeSafeClient()
    wrong = total = 0
    keys = list(cascade.REFER_OPTIONS)
    try:
        for desc, want in CASES.items():
            cells = []
            for _ in range(runs):
                r = await client.system_one(
                    state={"description": desc},
                    questions={"refer": Choice(instructions=cascade.REFER_INSTRUCTIONS,
                                               criteria=cascade.REFER_OPTIONS)},
                    model=cascade.MODEL)
                a = r.answers["refer"]
                p = {k: float(v) for k, v in (a.probabilities or {}).items()}
                wrong += a.choice != want; total += 1
                cells.append("/".join(f"{p.get(k, 0):.2f}" for k in keys) + ("" if a.choice == want else f"!{a.choice}"))
            print(f"  {desc[:40]:40s} {want:10s} " + "  ".join(cells), flush=True)
    finally:
        await client.aclose()
    print(f"misrouted {wrong}/{total}   columns: {'/'.join(keys)}")

asyncio.run(main())
