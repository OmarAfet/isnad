#!/usr/bin/env python3
"""Apply the Sahih Muslim citation rule (_common.muslim_citation) to the built index records
without rebuilding the index: Abd al-Baqi numbers in "ref", and the Introduction cited as such
with no automatic grade. Idempotent; scripts/02_normalize.py applies the same rule on a rebuild.

Usage: python scripts/08_cite_muslim.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _common import RAW, muslim_citation   # noqa: E402

RECORDS = os.path.join(HERE, "..", "data", "index", "records.jsonl")


def main():
    print("RAN: python scripts/08_cite_muslim.py")
    raw = {str(h["hadithnumber"]): h.get("arabicnumber") for h in
           json.load(open(os.path.join(RAW, "hadith-muslim.json"), encoding="utf-8"))["hadiths"]}
    recs = [json.loads(l) for l in open(RECORDS, encoding="utf-8")]
    changed = intro = 0
    for r in recs:
        if r.get("collection_key") != "muslim":
            continue
        ref, in_intro = muslim_citation(r["number"], raw.get(str(r["number"])))
        if in_intro:
            intro += 1
            r.update({"grade": "", "grade_raw": "", "grade_basis": "none", "severity": "unknown",
                      "grade_note": "في مقدمة صحيح مسلم، وليست من أصل الصحيح"})
        if r["ref"] != ref:
            r["ref"] = ref
            changed += 1
    with open(RECORDS + ".tmp", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(RECORDS + ".tmp", RECORDS)
    print(f"Muslim refs changed {changed}; Introduction narrations {intro} (no automatic grade)")


if __name__ == "__main__":
    main()
