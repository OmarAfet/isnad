#!/usr/bin/env python3
"""A HELD-OUT test: questions written after the code was frozen (commit f7fed9f, 2026-10-06), never
used to tune anything. eval/battery.py guided the fixes, so its 76/76 is in-sample; this is the
number that says how Isnad does on questions it was not shaped by. Run once, reported as is.

The same checks as the battery (verdicts / has / not_sound), and the same baselines as
eval/baseline.py: keyword search, meaning search, both, against Isnad.

Usage: python eval/heldout.py --api https://isnad-api.vercel.app [--gap 2.1] [--check-only]
       --check-only: confirm every expected text exists in the corpus, without any search
"""
import os, sqlite3, sys, time
os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import battery                                    # noqa: E402
from baseline import ENGINES, has_ok             # noqa: E402
from _arabic import normalize                     # noqa: E402

FOUND = battery.FOUND
LIST = battery.LIST
C = []


def case(group, q, **k):
    C.append((group, q, k))


# Described texts: paraphrase, partial memory, dialect, other languages
case("described", "الحديث اللي فيه إن الله رفيق يحب الرفق", verdicts=FOUND, has=["text:رفيق يحب الرفق"])
case("described", "حديث لا يدخل الجنة قاطع", verdicts=FOUND, has=["text:لا يدخل الجنه قاطع"])
case("described", "حديث المسلم من سلم المسلمون من لسانه ويده", verdicts=FOUND, has=["text:من لسانه ويده"])
case("described", "آية وتعاونوا على البر والتقوى", verdicts=FOUND, has=["id:quran:5:2"])
case("described", "الآية اللي تقول لا يكلف الله نفسا إلا وسعها", verdicts=FOUND, has=["id:quran:2:286"])
case("described", "hadith: the most beloved deeds to Allah are the most consistent even if small",
     verdicts=FOUND, has=["text:ادومها"])
case("described", "verse: We have not sent you except as a mercy to the worlds", verdicts=FOUND,
     has=["id:quran:21:107"])
case("described", "حديث كلكم راع وكلكم مسؤول عن رعيته", verdicts=FOUND, has=["text:كلكم راع"])
case("described", "حديث اتقوا النار ولو بشق تمرة", verdicts=FOUND, has=["text:بشق تمره"])
case("described", "آية الذين ينفقون أموالهم بالليل والنهار سرا وعلانية", verdicts=FOUND,
     has=["id:quran:2:274"])
case("described", "verse about Allah being closer to man than his jugular vein", verdicts=FOUND,
     has=["id:quran:50:16"])
case("described", "hadith: whoever builds a mosque, Allah builds for him a house in Paradise",
     verdicts=FOUND, has=["text:بني الله له"])
case("described", "حديث لا تحقرن من المعروف شيئا ولو أن تلقى أخاك بوجه طلق", verdicts=FOUND,
     has=["text:بوجه طلق"])
case("described", "الآية اللي تقول فاذكروني أذكركم", verdicts=FOUND, has=["id:quran:2:152"])
case("described", "حديث البر حسن الخلق والإثم ما حاك في صدرك", verdicts=FOUND, has=["text:حاك في"])
case("described", "hadis tentang menuntut ilmu adalah jalan menuju surga", verdicts=FOUND,
     has=["text:طريقا الي الجنه"])
case("described", "وہ آیت جس میں ہے کہ ہر جان کو موت کا مزہ چکھنا ہے", verdicts=FOUND,
     has=["id:quran:3:185", "id:quran:21:35", "id:quran:29:57"])
case("described", "le verset : Allah ne change pas l'état d'un peuple tant qu'il ne change pas ce qui "
     "est en lui-même", verdicts=FOUND, has=["id:quran:13:11"])
case("described", "аят о том, что Аллах не возлагает на душу больше, чем она может", verdicts=FOUND,
     has=["id:quran:2:286"])
case("described", "hadith: whoever believes in Allah and the Last Day should honour his guest",
     verdicts=FOUND, has=["text:فليكرم ضيفه"])
case("described", "وش الحديث اللي يقول ازهد في الدنيا يحبك الله", verdicts=FOUND,
     has=["text:ازهد في الدنيا"])
case("described", "حديث من حسن إسلام المرء تركه ما لا يعنيه", verdicts=FOUND, has=["text:ما لا يعنيه"])
case("described", "الحديث القدسي أنا عند ظن عبدي بي", verdicts=FOUND, has=["text:ظن عبدي بي"])
case("described", "الآية اللي فيها وجعلنا من الماء كل شيء حي", verdicts=FOUND, has=["id:quran:21:30"])
case("described", "حديث عن فضل إطعام الطعام وإفشاء السلام", verdicts=FOUND | LIST,
     has=["text:تطعم الطعام"])
case("described", "verse telling believing women to lower their gaze", verdicts=FOUND,
     has=["id:quran:24:31"])
case("described", "حديث الدنيا سجن المؤمن وجنة الكافر", verdicts=FOUND, has=["text:سجن المومن"])
case("described", "الآية اللي تقول ومن يتق الله يجعل له مخرجا", verdicts=FOUND, has=["id:quran:65:2"])
case("described", "hadith about the seven whom Allah will shade on the day there is no shade but His",
     verdicts=FOUND, has=["text:سبعه يظلهم الله"])
case("described", "حديث يسروا ولا تعسروا وبشروا ولا تنفروا", verdicts=FOUND, has=["text:يسروا ولا تعسروا"])

# Sayings that are not sound hadith in the six books
case("saying", "تهادوا تحابوا", not_sound="تهادوا")
case("saying", "الساكت عن الحق شيطان أخرس", not_sound="شيطان اخرس")
case("saying", "حديث العلم في الصغر كالنقش على الحجر", not_sound="كالنقش")
case("saying", "خير الكلام ما قل ودل", not_sound="ما قل ودل")
case("saying", "المعدة بيت الداء والحمية رأس الدواء", not_sound="بيت الداء")
case("saying", "حديث عليكم بدين العجائز", not_sound="دين العجايز")
case("saying", "حب الدنيا رأس كل خطيئة", not_sound="راس كل خطيئه")
case("saying", "الأقربون أولى بالمعروف", not_sound="اولي بالمعروف")


def check_only():
    """Every expected id exists and every expected phrase occurs in some text; every saying's own
    words occur in no sound text (else the case is wrong, not the system)."""
    db = sqlite3.connect(os.path.join(HERE, "..", "data", "index", "display.db"))
    rows = [(i, normalize(m or ""), normalize(t or "")) for i, m, t in
            db.execute("SELECT id, matn, text FROM display")]
    ids = {i for i, _, _ in rows}
    bad = 0
    for g, q, k in C:
        for h in k.get("has", []):
            kind, val = h.split(":", 1)
            ok = val in ids if kind == "id" else any(normalize(val) in m for _, m, _ in rows)
            if not ok:
                bad += 1
                print(f"  MISSING {h}  for  {q}")
        if "not_sound" in k:
            hits = [i for i, m, _ in rows if normalize(k["not_sound"]) in m]
            print(f"  saying {q[:30]:30s} occurs in: {hits[:6]}")
    print(f"{len(C)} cases, {bad} expectations not in the corpus")


def main():
    a = sys.argv
    if "--check-only" in a:
        return check_only()
    from search import Isnad
    api = a[a.index("--api") + 1] if "--api" in a else "http://127.0.0.1:8000"
    gap = float(a[a.index("--gap") + 1]) if "--gap" in a else 2.1
    print(f"RAN: python eval/heldout.py --api {api} --gap {gap}")
    ix = Isnad()
    groups = {"described": {e: 0 for e in list(ENGINES) + ["Isnad"]},
              "saying": {e: 0 for e in list(ENGINES) + ["Isnad"]}}
    fails = []
    for g, q, k in C:
        cells = []
        for e, (dw, lw) in ENGINES.items():
            top = (ix.search(q, k=1, dense_w=dw, lex_w=lw) or [{}])[0]
            if g == "described":
                ok = has_ok(top, k)
            else:
                ok = normalize(k["not_sound"]) in normalize(top.get("matn") or "") or \
                    top.get("severity") in ("mawdu", "daif")
            groups[g][e] += bool(ok)
            cells.append("+" if ok else ".")
        d, _ = battery.call(api, q)
        why = battery.check(d, k)
        groups[g]["Isnad"] += not why
        cells.append("+" if not why else ".")
        r = d.get("result") or {}
        top = (f"{r.get('ref')} [{r.get('grade')}]" if r else
               f"{len(d.get('topic') or [])} listed" if d.get("topic") else "-")
        print(f"  {' '.join(cells)}  {str(d.get('verdict')):10s} {top[:30]:30s} {q[:52]}"
              + ("" if not why else "\n             -> " + "; ".join(why)), flush=True)
        if why:
            fails.append(q)
        time.sleep(gap)
    for g, sc in groups.items():
        n = sum(1 for x in C if x[0] == g)
        print(f"\n{g} ({n}): " + ", ".join(f"{e} {v}/{n}" for e, v in sc.items()))


if __name__ == "__main__":
    main()
