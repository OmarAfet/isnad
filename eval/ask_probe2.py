#!/usr/bin/env python3
"""Can Jev tell five requests apart? find_text, general_ruling, personal_case, question (belief,
meaning, history, objection) and judge_people. Candidate options are passed in, so a wording can
be measured before it reaches cascade.py. Prints P per class per run and the class the rule picks.

Usage: python eval/ask_probe2.py [--runs 2] [--only <substring>]
"""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import cascade                     # noqa: E402
from decide import load_key        # noqa: E402

CASES = {
    # the core job
    "ايه عن النوم": "find_text", "ايه عن بر الوالدين": "find_text", "آية عن الصبر": "find_text",
    "حديث عن الغضب": "find_text", "حديث عن الكذب": "find_text", "verse about sleep": "find_text",
    "ما حكم حديث إن الفقيه أشد على الشيطان من ألف عابد": "find_text",
    "الدين المعاملة": "find_text", "حديث الدين المعاملة": "find_text",
    "اختلاف أمتي رحمة": "find_text", "حب الوطن من الإيمان": "find_text",
    "الجنة تحت أقدام الأمهات": "find_text", "إنما الأعمال بالنيات": "find_text",
    "اكتب لي خطبة جمعة عن الصبر": "find_text",
    "فسر لي آية الكرسي": "find_text",
    "the best of you are those who are best to their wives": "find_text",
    "Paradise lies under the feet of mothers": "find_text",
    "hadith Aisha married at six years old": "find_text",
    "verse about fighting the unbelievers wherever you find them": "find_text",
    "آخر آية نزلت": "find_text",
    # rulings
    "ماحكم الزنا": "general_ruling", "ما حكم الربا": "general_ruling",
    "what is the ruling on interest in Islam": "general_ruling", "ما حكم الكذب": "general_ruling",
    "ما حكم الموسيقى": "general_ruling", "هل الدخان حرام": "general_ruling",
    "is it haram to eat pork": "general_ruling", "ما حكم ترك الصلاة": "general_ruling",
    "هل يجوز لي الجمع بين الصلاتين في السفر؟": "personal_case",
    "طلقت زوجتي ثلاث مرات وش الحكم": "personal_case",
    "أنا في ألمانيا، هل يجوز لي أن أتزوج زواجا مدنيا فقط؟": "personal_case",
    "هل يجوز أفطر في رمضان إذا كنت مسافر؟": "personal_case",
    # questions about belief, meaning, history, objections (Reference Framework test cases)
    "لماذا يعبد المسلمون الكعبة؟": "question", "هل القرآن من تأليف محمد ﷺ؟": "question",
    "هل الإسلام انتشر بالسيف؟": "question", "لماذا توجد أحكام مختلفة بين العلماء؟": "question",
    "ما معنى التوحيد لشخص لم يسمع بالمصطلح من قبل؟": "question",
    "ترجم كلمة التوحيد إلى الإنجليزية": "question",
    "لماذا يمنع الإسلام الخمر؟ دين متخلف": "question",
    "هل كل المسلمين يتفقون على حكم الموسيقى؟": "question",
    "is islam a religion of violence": "question", "Why do Muslims believe in jihad?": "question",
    "what does Islam say about tawhid": "question", "ما رأيك في الإسلام": "question",
    # judging people or groups: out of scope
    "هل الشيعة كفار": "judge_people", "هل ابن تيمية مبتدع": "judge_people",
    "is the Pope going to hell": "judge_people", "هل الصوفية في النار": "judge_people",
    # unrelated to Islam: "not found", never a referral
    "what is the capital of France": "unrelated", "who won the world cup in 2022": "unrelated",
    "ما هو أفضل جوال في 2026": "unrelated", "اكتب لي قصيدة عن البحر": "unrelated",
    "write me a poem about the sea": "unrelated",
    # Islamic subjects that must not read as unrelated
    "verse about bees": "find_text", "ايه عن النحل": "find_text", "hadith about cats": "find_text",
    "حديث عن السواك": "find_text", "حديث الذبابة": "find_text",
}

OPTIONS = dict(cascade.ASK_OPTIONS)
OPTIONS.setdefault("question", (
    "A question about Islam itself: a belief, the meaning of a term or concept, an event in its "
    "history, the reason behind a teaching, or an objection or misconception (for example 'لماذا "
    "يعبد المسلمون الكعبة', 'هل القرآن من تأليف محمد', 'what is tawhid', 'did Islam spread by "
    "the sword'). Not a ruling on whether an act is permitted, and not a search for a text."))
OPTIONS.setdefault("judge_people", (
    "A judgement on a specific person, sect or group of people: whether they are believers, "
    "disbelievers, innovators, astray, or bound for Paradise or Hell (for example 'هل فلان "
    "كافر', 'هل الطائفة الفلانية في النار')."))


def pick(p, islamic):
    """The decision rule cascade.py applies (kept in step with it). "unrelated" here is the
    find_text path ending in "not found"; the probe cannot run the pick round."""
    if p.get("judge_people", 0) >= 0.5:
        return "judge_people"
    ruling = p.get("general_ruling", 0) + p.get("personal_case", 0)
    if ruling + p.get("question", 0) < cascade.RULING_THRESHOLD:
        return "find_text"
    if p.get("question", 0) > ruling:
        return "question" if islamic >= cascade.ISLAMIC_THRESHOLD else "unrelated"
    return "personal_case" if p.get("personal_case", 0) >= p.get("general_ruling", 0) else "general_ruling"


async def main():
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul
    load_key()
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 2
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    print(f"RAN: python eval/ask_probe2.py --runs {runs}" + (f" --only {only}" if only else ""))
    client = AsyncTypeSafeClient()
    wrong = total = 0
    keys = list(OPTIONS)
    try:
        for desc, want in CASES.items():
            if only and only not in desc and only != want:
                continue
            cells = []
            for _ in range(runs):
                r = await client.system_one(
                    state={"description": desc},
                    questions={"ask": Choice(instructions=cascade.ASK_INSTRUCTIONS, criteria=OPTIONS),
                               "islamic": Noul(instructions=cascade.ISLAMIC_INSTRUCTIONS)},
                    model=cascade.MODEL)
                p = {k: float(v) for k, v in (r.answers["ask"].probabilities or {}).items()}
                isl = float(r.answers["islamic"].noul)
                got = pick(p, isl)
                # an unrelated request that ends on the find_text path is answered "not found" there
                ok = got == want or (want == "unrelated" and got == "find_text")
                wrong += not ok; total += 1
                cells.append("/".join(f"{p.get(k, 0):.2f}" for k in keys) + f" i{isl:.2f}" + ("" if ok else f"!{got}"))
            print(f"  {desc[:40]:40s} {want:14s} " + "  ".join(cells), flush=True)
    finally:
        await client.aclose()
    print(f"misclassified {wrong}/{total}   columns: {'/'.join(keys)}")

asyncio.run(main())
