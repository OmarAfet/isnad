#!/usr/bin/env python3
"""Is the Qur'an shown word for word as published? Compares every verse Isnad displays with
quran.com's Uthmani text, word boundaries and letters only (the two encode marks differently:
U+08F0 vs U+064B for tanween, U+06E1 vs U+0652 for sukun), and counts any split tanween left.

Usage: python eval/check_quran_text.py [--chapters 1-114]     (one quran.com request per surah)
"""
import json, os, re, ssl, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts")]
from search import Isnad                      # noqa: E402
try:
    import certifi; CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = None
LETTERS = re.compile(r"[^ء-غف-يٱ ]")
SPLIT = re.compile(r"[\u08F0-\u08F2] [\u0627\u0649][\u064B-\u065F\u0670\u06D6-\u06ED]*(?=\s|$)")


FOLD = str.maketrans({"ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا",
                      "ؤ": "و", "ئ": "ي", "ى": "ي"})


def skeleton(s):
    """Letters and spaces only, hamza seats and alif forms folded (one edition writes "إ", the
    other alif plus a hamza mark): the word boundaries and the consonants."""
    s = LETTERS.sub("", s.translate(FOLD)).translate(FOLD)
    return " ".join(s.split())


def main():
    a, b = 1, 114
    if "--chapters" in sys.argv:
        a, b = map(int, sys.argv[sys.argv.index("--chapters") + 1].split("-"))
    print(f"RAN: python eval/check_quran_text.py --chapters {a}-{b}")
    ix = Isnad()
    verses = diff = split = 0
    examples = []
    for ch in range(a, b + 1):
        url = f"https://api.quran.com/api/v4/quran/verses/uthmani?chapter_number={ch}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (isnad text check)"})
        ref = json.load(urllib.request.urlopen(req, timeout=60, context=CTX))["verses"]
        for v in ref:
            mine = ix.display(f"quran:{v['verse_key']}").get("matn") or ""
            verses += 1
            split += len(SPLIT.findall(mine))
            if skeleton(mine) != skeleton(v["text_uthmani"]):
                diff += 1
                if len(examples) < 5:
                    examples.append((v["verse_key"], skeleton(mine)[:70], skeleton(v["text_uthmani"])[:70]))
    print(f"verses {verses}   split tanween left {split}   word/letter differences {diff}")
    for k, m, r in examples:
        print(f"  {k}\n    isnad    {m}\n    quran.com {r}")


if __name__ == "__main__":
    main()
