"""Language surfaces: the texts a query can be matched against.

One record, many surfaces. bukhari:1 is a single record with one Arabic text and up to eight
published translations. A query in Urdu is matched against the Urdu surface and still answers with
the Arabic record, because the Arabic is the text and the translation is only a way of finding it.

Coverage is uneven and is left that way. French has no Tirmidhi, Russian covers three collections,
Tamil two, and some individual hadiths are blank in an edition that otherwise exists. A record
with no translation in a language simply has no surface in that language, which costs recall for
that language and nothing else. Filling the gaps with our own translation is the one thing that is
not allowed here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _arabic import normalize
from _common import (HADITH_LANG_COVERAGE, LANGS, QURAN_TRANSLATIONS, RAW, load, say)

MIN_SURFACE_CHARS = 8     # below this an edition's entry is effectively empty


def normalize_latin(s):
    """Lowercase and strip punctuation. Arabic normalize() would mangle Latin and Cyrillic, and
    folding is meaningless outside the Arabic script."""
    out = []
    for ch in (s or ""):
        if ch.isalnum() or ch.isspace():
            out.append(ch.lower())
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def surface_text(lang, raw_text):
    """Normalize for matching. Urdu is Arabic script, so it uses the Arabic normalizer."""
    if lang in ("ar", "ur"):
        return normalize(raw_text)
    return normalize_latin(raw_text)


def load_quran_surfaces():
    """{lang: {(chapter, verse): (match_text, display_text)}}"""
    out = {}
    for lang, ed in QURAN_TRANSLATIONS.items():
        path = os.path.join(RAW, f"quran-{lang}-{ed}.json")
        if not os.path.isfile(path):
            say(f"    quran {lang}: edition {ed} absent, no surface")
            continue
        try:
            rows = load(path)["quran"]
        except Exception as e:
            say(f"    quran {lang}: unreadable ({type(e).__name__}), no surface")
            continue
        m = {}
        for r in rows:
            t = (r.get("text") or "").strip()
            if len(t) >= MIN_SURFACE_CHARS:
                m[(r["chapter"], r["verse"])] = (surface_text(lang, t), t)
        out[lang] = m
        say(f"    quran {lang}: {len(m)} ayahs ({ed})")
    return out


def load_hadith_surfaces():
    """{lang: {(book_key, hadithnumber): (match_text, display_text)}}"""
    out = {}
    for lang in LANGS:
        m = {}
        missing = []
        for book in HADITH_LANG_COVERAGE.get(lang, []):
            path = os.path.join(RAW, f"hadith-{lang}-{book}.json")
            if not os.path.isfile(path):
                missing.append(book)
                continue
            try:
                rows = load(path)["hadiths"]
            except Exception:
                missing.append(book)
                continue
            for h in rows:
                t = (h.get("text") or "").strip()
                if len(t) >= MIN_SURFACE_CHARS:
                    m[(book, h.get("hadithnumber"))] = (surface_text(lang, t), t)
        if m:
            out[lang] = m
        note = f" (missing: {', '.join(missing)})" if missing else ""
        say(f"    hadith {lang}: {len(m)} entries{note}")
    return out
