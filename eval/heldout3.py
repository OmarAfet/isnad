#!/usr/bin/env python3
"""HELD-OUT SET 3: written 2026-10-06 before the general fixes for the faults that sets 1 and 2
and the battery exposed (Omar: "try the general fixes and check on a new set"). Frozen in git
before any fix is written; run once before the fixes and once after; reported as is.

It leans on the exposed fault types (verse names, short sayings that read as statements,
"what does Islam say about" and "does Islam allow" questions, judgements on groups, misquotes
with a preposition inside the quoted words) and keeps guards for everything else. No question
here appears in an earlier test file, probe, or instruction, or among the ad-hoc queries typed
during this session.

Label policy, fixed before any run: "Does Islam allow/permit X" is a ruling question in form, so
"ruling" or "question" both pass; "What does Islam say about X" passes as "question" or "topic";
a judgement on a group's fate passes as "out_of_scope" or "question".

Usage: python eval/heldout3.py --api https://isnad-api.vercel.app [--gap 2.1] [--check-only]
"""
import os, sys
os.environ.setdefault("ISNAD_ENCODER", "onnx")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
import heldout2                                   # noqa: E402  (same runner and checks)

FOUND, LIST = heldout2.FOUND, heldout2.LIST
C = []


def case(group, q, *specs, **k):
    C.append((group, q, list(specs) or [k]))


# A. Described texts (regression guard)
case("described", "الآية اللي فيها ولا تقربوا الزنا إنه كان فاحشة", verdicts=FOUND,
     has=["id:quran:17:32"])
case("described", "حديث لا يرحم الله من لا يرحم الناس", verdicts=FOUND,
     has=["text:من لا يرحم الناس"])
case("described", "hadith: when a Muslim plants a tree, whatever is eaten from it is charity",
     verdicts=FOUND, has=["text:يغرس غرسا"])
case("described", "verse: and do not walk on the earth arrogantly", verdicts=FOUND,
     has=["id:quran:17:37", "id:quran:31:18"])
case("described", "حديث الحلال بين والحرام بين", verdicts=FOUND, has=["text:الحلال بين"])
case("described", "الآية اللي تقول لئن شكرتم لأزيدنكم", verdicts=FOUND, has=["id:quran:14:7"])
case("described", "hadis tentang larangan marah", verdicts=FOUND | LIST, has=["text:لا تغضب"])
case("described", "وہ آیت جس میں سود کو حرام کیا گیا", verdicts=FOUND | LIST,
     has=["id:quran:2:275", "id:quran:2:276", "id:quran:2:278", "id:quran:2:279", "id:quran:3:130"])
case("described", "le verset : tout ce qui est sur la terre est périssable", verdicts=FOUND,
     has=["id:quran:55:26"])
case("described", "Rabbinizin rahmetinden ümit kesmeyin ayeti", verdicts=FOUND,
     has=["id:quran:39:53"])
case("described", "hadith: modesty brings nothing but good", verdicts=FOUND,
     has=["text:الحياء لا ياتي الا بخير"])
case("described", "الحديث اللي يقول المؤمن مرآة أخيه", verdicts=FOUND, has=["text:مراه"])
case("described", "хадис о том, что Рай окружён неприятным", verdicts=FOUND,
     has=["text:حفت الجنه بالمكاره"])

# B. Short sayings that are not sound hadith in the six books (some read as statements)
case("saying", "العلم نور", not_sound="العلم نور")
case("saying", "الوقت كالسيف إن لم تقطعه قطعك", not_sound="كالسيف")
case("saying", "الصبر مفتاح الفرج", not_sound="مفتاح الفرج")
case("saying", "خير الناس أنفعهم للناس", not_sound="انفعهم للناس")
case("saying", "حديث النية مطية العمل", not_sound="مطيه العمل")
case("saying", "القناعة كنز لا يفنى", not_sound="كنز لا يفني")
case("saying", "حديث العقل السليم في الجسم السليم", not_sound="الجسم السليم")
case("saying", "الدنيا مزرعة الآخرة", not_sound="مزرعه الاخره")

# C. Verses known by a name (no name here is in any code)
case("named", "آية التطهير", verdicts=FOUND, has=["id:quran:33:33"])
case("named", "آية الحجاب", verdicts=FOUND | LIST,
     has=["id:quran:33:53", "id:quran:33:59", "id:quran:24:31"])
case("named", "آية السيف", verdicts=FOUND | LIST,
     has=["id:quran:9:5", "id:quran:9:29", "id:quran:9:36"])
case("named", "آيات الصيام", verdicts=FOUND | LIST,
     has=["id:quran:2:183", "id:quran:2:184", "id:quran:2:185", "id:quran:2:187"])
case("named", "آية الوضوء", verdicts=FOUND, has=["id:quran:5:6"])
case("named", "آية المباهلة", verdicts=FOUND, has=["id:quran:3:61"])
case("named", "آخر آية في سورة البقرة", verdicts=FOUND, has=["id:quran:2:286"])
case("named", "the Light Verse", verdicts=FOUND, has=["id:quran:24:35"])
case("named", "ayat kursi", verdicts=FOUND, has=["id:quran:2:255"])

# D. Questions about Islam
case("question", "What does Islam say about kindness to neighbors?", verdicts={"question", "topic"})
case("question", "Does Islam permit lying to non-Muslims?", verdicts={"question", "ruling"})
case("question", "لماذا يصوم المسلمون شهر رمضان؟", verdicts={"question", "ruling", "topic"})
case("question", "من هو النبي محمد صلى الله عليه وسلم؟", verdicts={"question", "topic"})
case("question", "Is Islam against science?", verdicts={"question"})
case("question", "ما الفرق بين الإسلام والإيمان؟", *(
    {"verdicts": {"question", "topic"}},
    {"verdicts": FOUND, "has": ["text:وتومن بالقدر"]}))
case("question", "Why do Muslim men grow beards?", verdicts={"question", "ruling"})
case("question", "هل الإسلام يحترم المرأة؟", verdicts={"question", "topic"})

# E. Judging people or groups
case("people", "هل الإباضية من أهل السنة؟", verdicts={"out_of_scope"})
case("people", "Is Ibn Arabi a heretic?", verdicts={"out_of_scope"})
case("people", "هل الحوثيون مسلمون؟", verdicts={"out_of_scope"})
case("people", "Are Christians going to hell?", verdicts={"out_of_scope", "question"})
case("people", "هل عمرو خالد مبتدع؟", verdicts={"out_of_scope"})

# F. Ruling questions
case("ruling", "ما حكم الاحتفال بالمولد النبوي", verdicts={"ruling"})
case("ruling", "هل يجوز الصلاة في البيت بدل المسجد", verdicts={"ruling"})
case("ruling", "أخذت مال من أبوي بدون علمهم وش علي؟", verdicts={"ruling"})
case("ruling", "Is it permissible to pray sitting on a chair?", verdicts={"ruling"})

# G. Misquotes, some with a preposition inside the quoted words
case("misquote", "وتعاونوا على البر والتقوى ولا تعاونوا على المعصية والعدوان", verdicts=FOUND,
     has=["id:quran:5:2"], wording=["المعصية"])
case("misquote", "يا أيها الذين آمنوا اصبروا وصابروا واتقوا الله لعلكم تفوزون", verdicts=FOUND,
     has=["id:quran:3:200"], wording=["تفوزون"])
case("misquote", "وقل ربي زدني فهما", verdicts=FOUND, has=["id:quran:20:114"], wording=["فهما"])
case("misquote", "إن الله يحب المحسنون", verdicts=FOUND,
     has=["id:quran:2:195", "id:quran:3:134", "id:quran:3:148", "id:quran:5:13", "id:quran:5:93"],
     wording=["المحسنون"])
case("misquote", "ولا تطع من أغفلنا قلبه عن ذكرنا واتبع شهوته", verdicts=FOUND,
     has=["id:quran:18:28"], wording=["شهوته"])

# H. Citations
case("cite", "الأنعام 151", verdicts={"confident"}, has=["id:quran:6:151"])
case("cite", "Bukhari 2320", verdicts={"confident"}, has=["text:يغرس غرسا"])
case("cite", "سنن أبي داود 4918", verdicts={"confident"}, has=["text:مراه"])

# I. Subjects
case("subject", "أحاديث عن الحياء", verdicts=LIST | FOUND, kind="hadith")
case("subject", "verses about charity", verdicts=LIST, kind="ayah")
case("subject", "hadits tentang sedekah", verdicts=LIST | FOUND, kind="hadith")
case("subject", "آيات عن خلق الإنسان", verdicts=LIST, kind="ayah")


if __name__ == "__main__":
    heldout2.C[:] = C                     # run set 3 with set 2's runner and checks
    heldout2.main()
