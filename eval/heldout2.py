#!/usr/bin/env python3
"""HELD-OUT SET 2: every kind of request, none of it seen before.

Written 2026-10-06 before the instructions to Jev were cleaned of test phrases and before the
hand-written verse-name tables were removed (Omar: "remove them and re-measure honestly"). No
question here appears in eval/battery.py, eval/smoke.py, eval/heldout.py, the probes, or any
instruction to Jev. It is run once before the cleanup and once after, and reported as is; nothing
is tuned on it.

Groups: described texts, sayings that are not sound hadith in the six books, questions about
Islam, judging people, ruling questions, verses known by a name, citations, misquotes, subjects.
A case passes if it passes any of its `any_of` specs (same checks as eval/battery.py).

Usage: python eval/heldout2.py --api https://isnad-api.vercel.app [--gap 2.1] [--check-only]
"""
import os, sqlite3, sys, time
os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import battery                                    # noqa: E402
from baseline import ENGINES, has_ok             # noqa: E402
from _arabic import normalize                     # noqa: E402

FOUND, LIST = battery.FOUND, battery.LIST
C = []


def case(group, q, *specs, **k):
    C.append((group, q, list(specs) or [k]))


def any_of(*specs):
    return specs


# A. Described texts, by meaning or part of the wording, in several languages and dialect
case("described", "الآية اللي تقول إن الحسنات يذهبن السيئات", verdicts=FOUND, has=["id:quran:11:114"])
case("described", "حديث الراحمون يرحمهم الرحمن", verdicts=FOUND, has=["text:الراحمون يرحمهم الرحمن"])
case("described", "الحديث اللي يقول المؤمن القوي خير وأحب إلى الله من المؤمن الضعيف",
     verdicts=FOUND, has=["text:المومن القوي خير"])
case("described", "آية ولا تزر وازرة وزر أخرى", verdicts=FOUND,
     has=["id:quran:6:164", "id:quran:17:15", "id:quran:35:18", "id:quran:39:7", "id:quran:53:38"])
case("described", "hadith: a believer is not stung from the same hole twice", verdicts=FOUND,
     has=["text:من جحر واحد"])
case("described", "verse: and speak good words to people", verdicts=FOUND, has=["id:quran:2:83"])
case("described", "الحديث اللي فيه إن الدين يسر ولن يشاد الدين أحد إلا غلبه", verdicts=FOUND,
     has=["text:ان الدين يسر"])
case("described", "حديث من صلى البردين دخل الجنة", verdicts=FOUND, has=["text:البردين"])
case("described", "verse about the mountains passing like clouds", verdicts=FOUND,
     has=["id:quran:27:88"])
case("described", "hadis tentang tangan di atas lebih baik dari tangan di bawah", verdicts=FOUND,
     has=["text:اليد العليا"])
case("described", "وہ حدیث جس میں ہے کہ مسلمان مسلمان کا بھائی ہے", verdicts=FOUND | LIST,
     has=["text:المسلم اخو المسلم"])
case("described", "le hadith : celui qui ne remercie pas les gens ne remercie pas Allah",
     verdicts=FOUND, has=["text:لا يشكر الناس"])
case("described", "аят: Мы сотворили человека в наилучшем облике", verdicts=FOUND,
     has=["id:quran:95:4"])
case("described", "zulüm kıyamet günü karanlıklardır hadisi", verdicts=FOUND,
     has=["text:ظلمات يوم القيامه"])
case("described", "hadith: deeds are judged by their endings", verdicts=FOUND, has=["text:بالخواتيم"])
case("described", "وش الحديث اللي يقول ما نقصت صدقة من مال", verdicts=FOUND,
     has=["text:ما نقصت صدقه من مال"])
case("described", "الآية اللي تقول كل نفس بما كسبت رهينة", verdicts=FOUND, has=["id:quran:74:38"])
case("described", "hadith: whoever relieves a believer of a hardship, Allah will relieve him of a "
     "hardship on the Day of Resurrection", verdicts=FOUND, has=["text:كربه من كرب"])

# B. Sayings that are not sound hadith in the six books
case("saying", "اطلبوا العلم من المهد إلى اللحد", not_sound="من المهد")
case("saying", "الجار قبل الدار", not_sound="قبل الدار")
case("saying", "حديث استعينوا على قضاء حوائجكم بالكتمان", not_sound="بالكتمان")
case("saying", "علموا أولادكم السباحة والرماية وركوب الخيل", not_sound="السباحه")
case("saying", "كما تكونوا يولى عليكم", not_sound="يولي عليكم")
case("saying", "من كثر كلامه كثر سقطه", not_sound="كثر سقطه")
case("saying", "حديث الصلاة عماد الدين", not_sound="عماد الدين")
case("saying", "خير الأسماء ما حمد وعبد", not_sound="ما حمد وعبد")

# C. Questions about Islam: the texts that speak to it and a referral, or a fitting list or text;
#    never a fatwa frame and never a single unrelated text
case("question", "Why do Muslims pray five times a day?", verdicts={"question", "ruling", "topic"})
case("question", "هل يؤمن المسلمون بالمسيح عليه السلام؟", verdicts={"question", "topic"})
case("question", "ما هي أركان الإيمان؟", *any_of(
    {"verdicts": {"question", "topic"}},
    {"verdicts": FOUND, "has": ["text:وتومن بالقدر"]}))
case("question", "Does Islam allow forcing someone to convert?", *any_of(
    {"verdicts": {"question", "topic"}},
    {"verdicts": FOUND, "has": ["id:quran:2:256"]}))
case("question", "لماذا حرم الإسلام لحم الخنزير؟", verdicts={"question", "ruling"})
case("question", "What does Islam say about honoring parents?", verdicts={"question", "topic"})
case("question", "متى ولد النبي صلى الله عليه وسلم؟", verdicts={"question", "no_match"})
case("question", "ما معنى كلمة الإحسان في الإسلام؟", *any_of(
    {"verdicts": {"question", "topic"}},
    {"verdicts": FOUND, "has": ["text:ان تعبد الله كانك تراه"]}))
case("question", "Is the Quran protected from being changed?", *any_of(
    {"verdicts": {"question", "topic"}},
    {"verdicts": FOUND, "has": ["id:quran:15:9"]}))
case("question", "هل يدخل غير المسلمين الجنة؟", verdicts={"question", "out_of_scope"})

# D. Judging people or groups: outside Isnad's work
case("people", "هل الأشاعرة من أهل السنة؟", verdicts={"out_of_scope"})
case("people", "Is Rumi a disbeliever?", verdicts={"out_of_scope"})
case("people", "هل المعتزلة كفار", verdicts={"out_of_scope"})

# E. Ruling questions: texts on the matter and a referral, never a ruling
case("ruling", "ما حكم صيام يوم الجمعة منفردا", verdicts={"ruling"})
case("ruling", "هل يجوز للمرأة السفر بدون محرم", verdicts={"ruling"})
case("ruling", "عندي قرض من البنك بفائدة، وش أسوي؟", verdicts={"ruling"})
case("ruling", "is it allowed to celebrate birthdays in Islam", verdicts={"ruling"})

# F. Verses known by a name (none of these names was ever in a table)
case("named", "آية القصاص", verdicts=FOUND | LIST, has=["id:quran:2:178", "id:quran:2:179"])
case("named", "آية الكلالة", verdicts=FOUND | LIST, has=["id:quran:4:176", "id:quran:4:12"])
case("named", "آيات المواريث", verdicts=FOUND | LIST,
     has=["id:quran:4:11", "id:quran:4:12", "id:quran:4:176"])
case("named", "Ayatul Kursi", verdicts=FOUND, has=["id:quran:2:255"])

# G. Citations
case("cite", "النساء 1", verdicts={"confident"}, has=["id:quran:4:1"])
case("cite", "صحيح مسلم 2699", verdicts=FOUND | LIST, has=["text:من نفس عن مومن"])
case("cite", "Tirmidhi 2516", verdicts={"confident"}, has=["text:احفظ الله يحفظك"])

# H. Misquotes: the right text, the reader's wrong word marked
case("misquote", "إن الله لا يغير ما بقوم حتى يغيروا ما في قلوبهم", verdicts=FOUND,
     has=["id:quran:13:11"], wording=["قلوبهم"])
case("misquote", "ادعوني أستجب لكم إن الذين يستكبرون عن طاعتي", verdicts=FOUND,
     has=["id:quran:40:60"], wording=["طاعتي"])
case("misquote", "حديث إنما الأعمال بالنوايا", verdicts=FOUND, has=["text:انما الاعمال بالنيات"],
     wording=["بالنوايا"])

# I. Subjects
case("subject", "حديث عن بر الأم", verdicts=LIST | FOUND, kind="hadith")
case("subject", "آيات عن التوبة", verdicts=LIST, kind="ayah")
case("subject", "hadith about kindness to animals", verdicts=LIST | FOUND, kind="hadith")
case("subject", "ayat tentang sabar", verdicts=LIST, kind="ayah")


def passes(d, specs):
    return any(not battery.check(d, s) for s in specs)


def check_only():
    db = sqlite3.connect(os.path.join(HERE, "..", "data", "index", "display.db"))
    rows = [(i, normalize(m or "")) for i, m in db.execute("SELECT id, matn FROM display")]
    ids = {i for i, _ in rows}
    bad = 0
    for g, q, specs in C:
        for s in specs:
            for h in s.get("has", []):
                kind, val = h.split(":", 1)
                ok = val in ids if kind == "id" else any(normalize(val) in m for _, m in rows)
                if not ok:
                    bad += 1
                    print(f"  MISSING {h}  for  {q}")
            if "not_sound" in s:
                hits = [i for i, m in rows if normalize(s["not_sound"]) in m]
                print(f"  saying {q[:34]:34s} occurs in: {hits[:6]}")
    print(f"{len(C)} cases, {bad} expectations not in the corpus")


def main():
    a = sys.argv
    if "--check-only" in a:
        return check_only()
    from search import Isnad
    api = a[a.index("--api") + 1] if "--api" in a else "http://127.0.0.1:8000"
    gap = float(a[a.index("--gap") + 1]) if "--gap" in a else 2.1
    print(f"RAN: python eval/heldout2.py --api {api} --gap {gap}")
    ix = Isnad()
    groups = {}
    engines = {}
    for g, q, specs in C:
        cells = []
        if g in ("described", "saying"):
            sc = engines.setdefault(g, {e: 0 for e in ENGINES})
            for e, (dw, lw) in ENGINES.items():
                top = (ix.search(q, k=1, dense_w=dw, lex_w=lw) or [{}])[0]
                s0 = specs[0]
                ok = has_ok(top, s0) if g == "described" else (
                    normalize(s0["not_sound"]) in normalize(top.get("matn") or "") or
                    top.get("severity") in ("mawdu", "daif"))
                sc[e] += bool(ok)
                cells.append("+" if ok else ".")
        d, _ = battery.call(api, q)
        ok = passes(d, specs)
        gr = groups.setdefault(g, [0, 0])
        gr[0] += ok
        gr[1] += 1
        r = d.get("result") or {}
        top = (f"{r.get('ref')} [{r.get('grade')}]" if r else
               f"{len(d.get('topic') or [])} listed" if d.get("topic") else "-")
        why = "" if ok else " -> " + "; ".join(battery.check(d, specs[0]))
        print(f"  {'ok  ' if ok else 'FAIL'} {g:9s} {' '.join(cells):7s} {str(d.get('verdict')):12s} "
              f"{top[:28]:28s} {q[:50]}{why}", flush=True)
        time.sleep(gap)
    total = sum(v[0] for v in groups.values())
    n = sum(v[1] for v in groups.values())
    print(f"\nIsnad: {total}/{n}   " + "   ".join(f"{g} {v[0]}/{v[1]}" for g, v in groups.items()))
    for g, sc in engines.items():
        m = groups[g][1]
        print(f"  baselines, {g} ({m}): " + ", ".join(f"{e} {v}/{m}" for e, v in sc.items()))


if __name__ == "__main__":
    main()
