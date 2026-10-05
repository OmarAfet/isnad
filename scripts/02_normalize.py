#!/usr/bin/env python3
"""Build the unified Isnad corpus from data/raw/ into data/corpus/corpus.jsonl.

One record per ayah or hadith. Every record carries its source reference and, for hadith, the
grading exactly as the data states it, with the grader named. Where the data holds no grading the
record says so instead of inferring one: the challenge Reference Framework forbids attributing a
hadith without a source and an approved ruling.

Usage: python3 scripts/02_normalize.py
"""
import json, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _arabic import clean_display, normalize, split_sanad_matn
from _grades import (SEVERITY_ACTION, SEVERITY_AR, grader_ar, label as grade_label,
                     scope as grade_scope, severity as grade_severity)
from _common import (CORPUS, HADITH_BOOKS, QURAN_EDITION, QURAN_MATCH_EDITION, RAW,
                     muslim_citation,
                     dump, load, ran, say)
from _surahs import surah_name, verses_count
from _surfaces import load_hadith_surfaces, load_quran_surfaces

# Al-Albani's rulings are the most widely cited in these editions, so his is used as the display
# label when present. Every other named ruling is kept and shown alongside it.
PREFERRED_GRADER = "Al-Albani"


def build_quran(qsurf):
    ayahs = load(os.path.join(RAW, f"quran-{QURAN_EDITION}.json"))["quran"]
    simple = load(os.path.join(RAW, f"quran-{QURAN_MATCH_EDITION}.json"))["quran"]
    if len(ayahs) != len(simple) or any(
            a["chapter"] != b["chapter"] or a["verse"] != b["verse"]
            for a, b in zip(ayahs, simple)):
        raise SystemExit("the two Quran editions are not ayah-aligned; refusing to build")
    seen = Counter()
    out = []
    for a, b in zip(ayahs, simple):
        s, v, text = a["chapter"], a["verse"], a["text"]
        match_src = b["text"]
        seen[s] += 1
        name = surah_name(s)
        out.append({
            "id": f"quran:{s}:{v}",
            "kind": "ayah",
            "collection": "القرآن الكريم",
            "collection_key": "quran",
            "surah": s, "surah_name": name, "ayah": v,
            "ref": f"{name}: {v}",
            "text": clean_display(text),
            "matn": clean_display(text),
            # Display from the Uthmani edition, matching from the simple one.
            "match_text": normalize(match_src),
            "match_source": QURAN_MATCH_EDITION,
            "surfaces": {lg: m[(s, v)][0] for lg, m in qsurf.items() if (s, v) in m},
            "translations": {lg: m[(s, v)][1] for lg, m in qsurf.items() if (s, v) in m},
            "grade": "قرآن كريم",
            "grade_raw": None,
            "grade_basis": "quran",
            "severity": "quran",
            "severity_ar": "قرآن كريم",
            "action": "safe_to_cite",
            "scope": "ayah",
            "grade_note": f"نص قرآني — {name}: {v}",
            "graders": [],
            "edition": QURAN_EDITION,
        })

    # Integrity check against independent metadata. A silent off-by-one in scripture is not
    # acceptable, so this fails the build rather than warning.
    bad = [(s, seen[s], verses_count(s)) for s in range(1, 115) if seen[s] != verses_count(s)]
    if bad:
        for s, got, want in bad[:10]:
            say(f"  MISMATCH surah {s} ({surah_name(s)}): {got} ayahs, expected {want}")
        raise SystemExit(f"quran integrity check failed for {len(bad)} surahs")
    say(f"  quran: {len(out)} ayahs, all 114 surahs match expected verse counts")
    return out


def pick_grade(graders):
    """Return (raw, arabic, note, basis, severity, scope). Never invents a ruling."""
    usable = [g for g in graders if grade_label(g.get("grade"))]
    if not usable:
        return None, None, "الدرجة غير متوفرة في البيانات", "none", "unknown", "hadith"
    chosen = next((g for g in usable if g.get("name") == PREFERRED_GRADER), usable[0])
    raw = chosen.get("grade")
    return (raw, grade_label(raw), f"حكم {grader_ar(chosen.get('name'))}", "cited",
            grade_severity(raw), grade_scope(raw))


def build_hadith(key, hsurf):
    meta = HADITH_BOOKS[key]
    raw = load(os.path.join(RAW, f"hadith-{key}.json"))
    sections = (raw.get("metadata") or {}).get("sections") or {}
    out, rules = [], Counter()
    dropped = 0
    for h in raw["hadiths"]:
        text = h.get("text") or ""
        sanad, matn, rule = split_sanad_matn(text)
        rules[rule] += 1
        if rule == "empty" or not normalize(matn):
            # The upstream edition carries no text for this number. Keeping it would let a query
            # match an empty record, so it is excluded and counted instead.
            dropped += 1
            continue
        num = h.get("hadithnumber")
        ref_obj = h.get("reference") or {}
        book_no = ref_obj.get("book")
        graders = [{"grader": g.get("name"), "grade": g.get("grade")}
                   for g in (h.get("grades") or []) if g.get("grade")]

        ref = f"{meta['ar']} ({num})"
        intro = False
        if key == "muslim":
            ref, intro = muslim_citation(num, h.get("arabicnumber"))
        if intro:
            grade_raw, grade_ar, note = "", "", "في مقدمة صحيح مسلم، وليست من أصل الصحيح"
            basis, sev, scp = "none", "unknown", "hadith"
        elif meta["grade_basis"] == "inherent":
            grade_raw, grade_ar = "Sahih", "صحيح"
            note = f"أخرجه {meta['short']} في صحيحه"
            basis, sev, scp = "inherent", "sahih", "hadith"
        else:
            grade_raw, grade_ar, note, basis, sev, scp = pick_grade(
                [{"name": g["grader"], "grade": g["grade"]} for g in graders])

        out.append({
            "id": f"{key}:{num}",
            "kind": "hadith",
            "collection": meta["ar"],
            "collection_key": key,
            "number": num,
            "arabic_number": h.get("arabicnumber"),
            "book": book_no,
            "section": sections.get(str(book_no)) or None,
            "ref": ref,
            "text": clean_display(text),
            "sanad": clean_display(sanad),
            "matn": clean_display(matn),
            "match_text": normalize(matn),
            "grade": grade_ar,
            "grade_raw": grade_raw,
            "grade_basis": basis,
            "grade_note": note,
            "severity": sev,
            "severity_ar": SEVERITY_AR.get(sev),
            "action": SEVERITY_ACTION.get(sev),
            "scope": scp,
            "graders": [dict(g, grade_ar=grade_label(g["grade"]),
                             grader_ar=grader_ar(g["grader"])) for g in graders],
            "surfaces": {lg: m[(key, num)][0] for lg, m in hsurf.items() if (key, num) in m},
            "translations": {lg: m[(key, num)][1] for lg, m in hsurf.items() if (key, num) in m},
            "split_rule": rule,
        })
    say(f"  {key:9s}: {len(out):5d} records (dropped {dropped} empty) | "
        + ", ".join(f"{k}={v}" for k, v in rules.most_common()))
    return out, rules


def main():
    ran("python3 scripts/02_normalize.py")
    say("\nTranslation surfaces (matching only; the answer is always the Arabic)")
    qsurf = load_quran_surfaces()
    hsurf = load_hadith_surfaces()

    say("\nQuran")
    records = build_quran(qsurf)

    say("\nHadith")
    all_rules = Counter()
    for key in HADITH_BOOKS:
        recs, rules = build_hadith(key, hsurf)
        records += recs
        all_rules += rules

    path = os.path.join(CORPUS, "corpus.jsonl")
    os.makedirs(CORPUS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    say(f"\n  wrote   data/corpus/corpus.jsonl "
        f"({len(records)} records, {os.path.getsize(path)/1e6:.1f} MB)")

    stats = {
        "built": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "records": len(records),
        "by_kind": dict(Counter(r["kind"] for r in records)),
        "by_collection": dict(Counter(r["collection_key"] for r in records)),
        "split_rules": dict(all_rules),
        "grade_basis": dict(Counter(r["grade_basis"] for r in records)),
        "quran_edition": QURAN_EDITION,
        "surface_coverage": {
            lg: sum(1 for r in records if lg in r.get("surfaces", {}))
            for lg in sorted({k for r in records for k in r.get("surfaces", {})})
        },
    }
    dump(stats, os.path.join(CORPUS, "stats.json"))
    say("next: python3 scripts/03_report.py")


if __name__ == "__main__":
    main()
