#!/usr/bin/env python3
"""Quoted saying or subject? One Jev Noul per description, N runs. A quoted saying must not get a
"texts on this subject" list: "الدين المعاملة" listed hadith on debts (الدَّين).
Usage: python eval/saying_probe.py [--runs 2]"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import cascade                     # noqa: E402
from decide import load_key        # noqa: E402

CASES = {   # True: a quoted saying
    "الدين المعاملة": True, "حديث الدين المعاملة": True, "اختلاف أمتي رحمة": True,
    "حب الوطن من الإيمان": True, "حديث النظافة من الإيمان": True,
    "حديث اطلبوا العلم ولو في الصين": True, "الجنة تحت أقدام الأمهات": True,
    "إنما الأعمال بالنيات": True, "الدين النصيحة": True, "تبسمك في وجه أخيك صدقة": True,
    "خير الأمور أوسطها": True, "صوموا تصحوا": True, "من تشبه بقوم فهو منهم": True,
    "الصبر": False, "بر الوالدين": False, "حديث الغضب": False, "ايه عن النوم": False,
    "حديث عن الكذب": False, "آيات عن الجنة": False, "الصلاة": False, "حديث عن الجار": False,
    "hadith about patience": False, "verses on mercy": False, "صلة الرحم": False,
    "الكذب": False, "حقوق الجار": False, "فضل الصدقة": False,
}


async def main():
    from typesafe_sdk import AsyncTypeSafeClient, Noul
    load_key()
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 2
    print(f"RAN: python eval/saying_probe.py --runs {runs}")
    client = AsyncTypeSafeClient()
    wrong = total = 0
    try:
        for desc, want in CASES.items():
            cells = []
            for _ in range(runs):
                r = await client.system_one(
                    state={"description": desc},
                    questions={"saying": Noul(instructions=cascade.SAYING_INSTRUCTIONS)},
                    model=cascade.MODEL)
                p = float(r.answers["saying"].noul)
                got = p >= cascade.SAYING_THRESHOLD
                wrong += got != want; total += 1
                cells.append(f"{p:.2f}{'' if got == want else '!'}")
            print(f"  {desc[:36]:36s} {'saying ' if want else 'subject'} " + "  ".join(cells), flush=True)
    finally:
        await client.aclose()
    print(f"wrong {wrong}/{total}  (threshold {cascade.SAYING_THRESHOLD})")

asyncio.run(main())
