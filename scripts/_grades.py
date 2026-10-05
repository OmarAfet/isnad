"""Hadith grading: Arabic label, severity class, and scope.

The upstream editions state rulings in transliterated English ("Sahih", "Daif Isnaad",
"Hasan Lighairihi", ...) with a long tail of 1,658 distinct strings. Translating whole phrases
would miss the tail, so terms are mapped individually and recombined; measured coverage of the
term map is reported by 03_report.py.

Three outputs, kept separate on purpose:
  * label    — Arabic rendering, for display next to the text;
  * severity — sahih / hasan / daif / mawdu / unknown, the one signal a user acts on;
  * scope    — whether the ruling is about the hadith or only about its chain (isnaad).

Isnad never derives a ruling. If a term is unknown it is passed through verbatim, and the original
English string is always kept in the record so the claim stays checkable.
"""
import re

TERMS = {
    "sahih": "صحيح", "daif": "ضعيف", "hasan": "حسن", "mawdu": "موضوع",
    "shadh": "شاذ", "munkar": "منكر", "matruk": "متروك", "batil": "باطل",
    "maqtu": "مقطوع", "mauquf": "موقوف", "muquf": "موقوف", "mutawatir": "متواتر",
    "mursal": "مرسل", "munqati": "منقطع", "mudallas": "مدلّس", "muallaq": "معلّق",
    "isnaad": "الإسناد", "sanad": "السند", "hadith": "الحديث",
    "lighairihi": "لغيره", "very": "شديد", "agreed": "متفق", "upon": "عليه",
    "bukhari": "البخاري", "muslim": "مسلم", "muttafaq": "متفق عليه", "and": "و", "ghairihi": "غيره",
}

# Term-by-term recombination reads badly for a handful of frequent compounds ("Very Daif" became
# "شديد ضعيف"), so those are rendered as phrases. Everything else falls through to TERMS.
PHRASES = {
    "very daif": "ضعيف جدًا",
    "sahih agreed upon": "صحيح متفق عليه",
    "sahih bukhari and muslim": "صحيح متفق عليه (البخاري ومسلم)",
    "sahih muslim": "صحيح (أخرجه مسلم)",
    "sahih bukhari": "صحيح (أخرجه البخاري)",
    "sahih isnaad": "صحيح الإسناد",
    "isnaad sahih": "صحيح الإسناد",
    "hasan isnaad": "حسن الإسناد",
    "isnaad hasan": "حسن الإسناد",
    "daif isnaad": "ضعيف الإسناد",
    "isnaad daif": "ضعيف الإسناد",
    "sanad daif": "ضعيف السند",
    "hasan sahih": "حسن صحيح",
    "sahih lighairihi": "صحيح لغيره",
    "hasan lighairihi": "حسن لغيره",
    "sahih hadith": "حديث صحيح",
    "sahih mutawatir": "صحيح متواتر",
    "sahih muquf": "صحيح موقوف",
    "sahih mauquf": "صحيح موقوف",
    "sahih maqtu": "صحيح مقطوع",
}

# Severity is decided by the worst term present, because "Sahih Isnaad" with a Daif note must not
# read as simply sound.
_MAWDU = {"mawdu", "batil"}
_DAIF = {"daif", "shadh", "munkar", "matruk", "munqati", "mursal", "muallaq"}
_SAHIH = {"sahih", "mutawatir"}
_HASAN = {"hasan"}
_SCOPE = {"isnaad", "sanad"}

_SPLIT = re.compile(r"[^a-zA-Z]+")


def _terms(grade):
    return [t.lower() for t in _SPLIT.split(grade or "") if t]


def severity(grade):
    ts = set(_terms(grade))
    if ts & _MAWDU:
        return "mawdu"
    if ts & _DAIF:
        return "daif"
    if ts & _SAHIH:
        return "sahih"
    if ts & _HASAN:
        return "hasan"
    return "unknown"


def scope(grade):
    """"isnaad" when the ruling judges the chain rather than the report itself."""
    return "isnaad" if set(_terms(grade)) & _SCOPE else "hadith"


def label(grade):
    """Arabic rendering. Unknown terms pass through untouched rather than being dropped."""
    g = (grade or "").strip()
    if not g or g == "-":
        return None
    key = " ".join(_terms(g))
    if key in PHRASES:
        return PHRASES[key]
    parts, unknown = [], 0
    for t in _SPLIT.split(g):
        if not t:
            continue
        key = t.lower()
        if key in TERMS:
            parts.append(TERMS[key])
        else:
            parts.append(t)
            unknown += 1
    return " ".join(parts) if parts else None


def coverage(grades):
    """Share of terms the map recognises, for the quality report."""
    known = total = 0
    for g in grades:
        for t in _terms(g):
            total += 1
            known += t in TERMS
    return known, total


SEVERITY_AR = {
    "sahih": "صحيح", "hasan": "حسن", "daif": "ضعيف",
    "mawdu": "موضوع", "unknown": "غير محدد",
}

# What the interface must do with each class. The whole point of Isnad is that a weak or fabricated
# text is never handed over as if it were sound.
SEVERITY_ACTION = {
    "sahih": "safe_to_cite",
    "hasan": "safe_to_cite",
    "daif": "warn_do_not_cite",
    "mawdu": "warn_fabricated",
    "unknown": "warn_unverified",
}


# The eight graders present in these editions, in Arabic. A ruling shown as "حكم Al-Albani" inside
# an Arabic interface reads as an untranslated string, and the grader's name is part of the
# citation the user is meant to be able to check.
GRADERS_AR = {
    "Al-Albani": "الألباني",
    "Zubair Ali Zai": "زبير علي زئي",
    "Shuaib Al Arnaut": "شعيب الأرناؤوط",
    "Abu Ghuddah": "عبد الفتاح أبو غدة",
    "Muhammad Muhyi Al-Din Abdul Hamid": "محمد محيي الدين عبد الحميد",
    "Muhammad Fouad Abd al-Baqi": "محمد فؤاد عبد الباقي",
    "Ahmad Muhammad Shakir": "أحمد محمد شاكر",
    "Bashar Awad Maarouf": "بشار عواد معروف",
}


def grader_ar(name):
    return GRADERS_AR.get(name, name)
