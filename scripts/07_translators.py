#!/usr/bin/env python3
"""Translator credits for every translation surface, from the editions' own metadata.

A translation shown under a verse or hadith is somebody's published work, and the reader is owed
its author's name. The terms (clause 9) also require recording the source of every work used.

Usage: python scripts/07_translators.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (CDN, HADITH_LANG_COVERAGE, HADITH_LANG_PREFIX, QURAN_TRANSLATIONS, RAW,
                     ROOT, fetch, ran, say)


def main():
    ran("python scripts/07_translators.py")
    hp = fetch(f"{CDN}/hadith-api@1/editions.json", os.path.join(RAW, "hadith-editions.json"))
    qp = fetch(f"{CDN}/quran-api@1/editions.json", os.path.join(RAW, "quran-editions.json"))
    h = json.load(open(hp, encoding="utf-8"))
    q = json.load(open(qp, encoding="utf-8"))

    out = {"quran": {}, "hadith": {}}
    qby = {v["name"]: v for v in q.values()}
    for lang, ed in QURAN_TRANSLATIONS.items():
        v = qby.get(ed, {})
        out["quran"][lang] = {"edition": ed, "author": v.get("author") or ed,
                              "source": v.get("source") or ""}

    for lang, prefix in HADITH_LANG_PREFIX.items():
        out["hadith"][lang] = {}
        for book in HADITH_LANG_COVERAGE[lang]:
            name = f"{prefix}-{book}"
            meta = next((c for v in h.values() for c in v.get("collection", [])
                         if c.get("name") == name), {})
            out["hadith"][lang][book] = {"edition": name,
                                         "author": meta.get("author") or "",
                                         "source": meta.get("source") or ""}

    path = os.path.join(ROOT, "data", "translators.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    say(f"  wrote   data/translators.json")
    say(f"  quran en -> {out['quran']['en']['author']}")
    say(f"  hadith en bukhari -> {out['hadith']['en']['bukhari']['author']!r}")


if __name__ == "__main__":
    main()
