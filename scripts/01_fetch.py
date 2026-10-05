#!/usr/bin/env python3
"""Download the Isnad source corpora into data/raw/.

Sources are the open jsDelivr mirrors of fawazahmed0's quran-api and hadith-api: no API key, no
rate limit, and reachable from free hosting. The Quran edition chosen is the King Fahd Complex
Uthmani text, which is the edition the challenge Reference Framework names; dorar.net, the
framework's platform for gradings, sits behind Cloudflare and refuses automated fetches, so the
gradings come instead from the named-muhaddith rulings carried inside the Sunan editions.

Usage: python3 scripts/01_fetch.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CDN, HADITH_BOOKS, QURAN_EDITION, RAW, fetch, ran, say


def main():
    ran("python3 scripts/01_fetch.py")
    say(f"\nQuran — {QURAN_EDITION} (King Fahd Complex Uthmani)")
    fetch(f"{CDN}/quran-api@1/editions/{QURAN_EDITION}.json",
          os.path.join(RAW, f"quran-{QURAN_EDITION}.json"))
    # Surah names and per-surah verse counts. The counts are an integrity check on the text above,
    # not decoration: 02_normalize.py refuses to build a corpus that disagrees with them.
    fetch("https://api.quran.com/api/v4/chapters?language=ar",
          os.path.join(RAW, "quran-chapters.json"))

    say(f"\nHadith — {len(HADITH_BOOKS)} collections")
    for key in HADITH_BOOKS:
        fetch(f"{CDN}/hadith-api@1/editions/ara-{key}.json",
              os.path.join(RAW, f"hadith-{key}.json"))

    total = sum(os.path.getsize(os.path.join(RAW, f)) for f in os.listdir(RAW))
    say(f"\nraw corpus: {total/1e6:.1f} MB in {RAW}")
    say("next: python3 scripts/02_normalize.py")


if __name__ == "__main__":
    main()
