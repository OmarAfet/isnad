#!/usr/bin/env python3
"""Cross-check our gradings against dorar.net, the platform the Reference Framework names.

Method, stated plainly because the number is only worth what the method is worth:

 1. For each sampled hadith we take a seven-word window from the middle of its matn and search
    dorar. dorar's search is lexical and loose, so its top hit is often a DIFFERENT but adjacent
    report. Comparing against it blindly would produce a meaningless agreement rate.
 2. So a dorar result counts as the same hadith only when its source names our collection AND its
    page/number equals our hadith number. That is an identity match, not a similarity guess.
 3. Only matched pairs are compared, and they are compared at the level of severity class
    (sahih / hasan / daif / mawdu), not raw wording: "إسناده صحيح على شرط الشيخين" and "صحيح" are
    the same decision for a user even though the strings differ.
 4. Unmatched rows are reported as "not located", never as agreement or disagreement.

Usage: python3 scripts/05_dorar_crosscheck.py
"""
import glob, json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _arabic import normalize
from _common import HADITH_BOOKS, ROOT, ran, say

DORAR = os.path.join(ROOT, "data", "dorar")

# Tokens that identify our collection inside a dorar source title. dorar cites both the original
# Sunan and al-Albani's volumes on them ("سنن الترمذي", "صحيح الترمذي", "ضعيف الترمذي"), so the
# distinguishing name is matched rather than the full title.
COLLECTION_TOKENS = {
    "bukhari": ["البخاري"], "muslim": ["مسلم"],
    "abudawud": ["ابي داود", "ابو داود"], "tirmidhi": ["الترمذي"],
    "nasai": ["النسايي", "النساي"], "ibnmajah": ["ابن ماجه"],
}

# "سكت عنه" is Abu Dawud declining to rule, not a grade. The bracketed gloss that his silence
# implies acceptability is an inference by later scholars, so it is treated as no ruling stated
# and the pair is excluded. Counting an absent ruling as disagreement would inflate the
# disagreement rate with nothing.
NON_RULING = ["سكت عنه", "لم يحكم عليه", "لم يذكر حكمه"]

_NEG = ["لا يصح", "ليس بصحيح", "غير صحيح", "لم يصح", "لا يثبت", "غير ثابت"]
_MAWDU = ["موضوع", "باطل", "مكذوب", "لا اصل له"]
_DAIF = ["ضعيف", "منكر", "شاذ", "متروك", "واه", "مستور", "مدرج", "معلول", "منقطع", "مرسل"]
_SAHIH = ["صحيح", "ثابت", "علي شرط", "متفق عليه"]
_HASAN = ["حسن"]


def severity_of_ruling(ruling):
    """Classify a free-text Arabic ruling. Negations are checked first: "ليس بصحيح" contains
    "صحيح" and must not read as sound. A declined ruling returns "none"."""
    t = normalize(ruling or "")
    if not t:
        return "unknown"
    if any(normalize(p) in t for p in NON_RULING):
        return "none"
    if any(p in t for p in _MAWDU):
        return "mawdu"
    if any(normalize(p) in t for p in _NEG):
        return "daif"
    if any(p in t for p in _DAIF):
        return "daif"
    if any(p in t for p in _SAHIH):
        return "sahih"
    if any(p in t for p in _HASAN):
        return "hasan"
    return "unknown"


def same_hadith(row, hit):
    """True when the dorar hit is our hadith: our collection, our number."""
    key = row["id"].split(":")[0]
    src = normalize(hit.get("source") or "")
    if not any(normalize(tok) in src for tok in COLLECTION_TOKENS.get(key, [])):
        return False
    page = (hit.get("page") or "").strip()
    num = str(row["id"].split(":", 1)[1])
    return page == num or re.search(rf"(^|\D){re.escape(num)}($|\D)", page) is not None


def load_rows():
    rows, seen = [], set()
    for p in sorted(glob.glob(os.path.join(DORAR, "s-*.json"))) + \
             sorted(glob.glob(os.path.join(DORAR, "legacy-*.json"))):
        for r in json.load(open(p, encoding="utf-8")):
            if r["id"] in seen:
                continue
            seen.add(r["id"])
            rows.append(r)
    return rows


def main():
    ran("python3 scripts/05_dorar_crosscheck.py")
    rows = load_rows()
    sample = [r for r in rows if r["purpose"] == "sample"]
    ungraded = [r for r in rows if r["purpose"] == "ungraded"]
    say(f"\nharvested rows: {len(rows)} ({len(sample)} sample, {len(ungraded)} ungraded)")

    matched, unmatched, no_ruling, agree, disagree = [], [], [], [], []
    for r in sample:
        # All hits that identify this same hadith, not just the first. dorar cites the original
        # Sunan and al-Albani's volume on it under different titles; prefer whichever actually
        # states a ruling.
        hits = [h for h in (r.get("dorar") or []) if same_hadith(r, h)]
        if not hits:
            unmatched.append(r)
            continue
        usable = [(h, severity_of_ruling(h.get("ruling"))) for h in hits]
        pick = next(((h, sv) for h, sv in usable if sv not in ("none", "unknown")), None)
        if pick is None:
            no_ruling.append({**r, "dorar_hit": hits[0],
                              "dorar_severity": severity_of_ruling(hits[0].get("ruling"))})
            continue
        hit, theirs = pick
        ours = r.get("our_severity")
        rec = {**r, "dorar_hit": hit, "dorar_severity": theirs}
        matched.append(rec)
        (agree if ours == theirs else disagree).append(rec)

    L = []
    def out(s=""):
        say(s); L.append(s)

    out("# Cross-check against dorar.net\n")
    out(f"- sampled hadiths queried: **{len(sample)}** (reproducible, seed 450)")
    out(f"- located in dorar by source and number: **{len(matched)}** "
        f"({100*len(matched)/max(1,len(sample)):.0f}%)")
    out(f"- not located: {len(unmatched)} — dorar's search is lexical, so a mid-matn window does "
        f"not always surface the same report; these are excluded rather than counted")
    out(f"- located but no ruling stated: {len(no_ruling)} — dorar's entry for these is "
        f"\"سكت عنه\", Abu Dawud declining to rule. Also excluded.")
    if matched:
        out(f"\n**Severity agreement on located pairs: {len(agree)}/{len(matched)} = "
            f"{100*len(agree)/len(matched):.1f}%.**")
    out(f"\nSource of our ruling vs dorar's: ours comes from the collection's own edition, "
        f"dorar's from its named muhaddith. Agreement is therefore a check on our pipeline, not "
        f"proof of a hadith's status.")

    if disagree:
        out(f"\n## Disagreements ({len(disagree)})\n")
        out("| id | ref | ours | dorar | dorar muhaddith | dorar ruling |")
        out("|---|---|---|---|---|---|")
        for r in disagree:
            h = r["dorar_hit"]
            out(f"| `{r['id']}` | {r['ref']} | {r['our_grade']} ({r['our_severity']}) | "
                f"{r['dorar_severity']} | {h.get('muhaddith')} | {h.get('ruling')} |")

    if matched:
        out(f"\n## Agreement by class\n")
        out("| our class | pairs | agreed |")
        out("|---|---|---|")
        byc = Counter(r["our_severity"] for r in matched)
        bya = Counter(r["our_severity"] for r in agree)
        for k, v in byc.most_common():
            out(f"| {k} | {v} | {bya.get(k,0)} |")

    if ungraded:
        out(f"\n## Hadiths our data could not grade ({len(ungraded)})\n")
        for r in ungraded:
            hit = next((h for h in r.get("dorar") or [] if same_hadith(r, h)), None)
            if hit:
                out(f"- `{r['id']}` — dorar: **{hit.get('ruling')}** "
                    f"({hit.get('muhaddith')}, {hit.get('source')} {hit.get('page')})")
            else:
                out(f"- `{r['id']}` — not located in dorar by source and number")

    path = os.path.join(DORAR, "crosscheck.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    json.dump({"sample": len(sample), "compared": len(matched), "agree": len(agree),
               "disagree": len(disagree), "unmatched": len(unmatched),
               "no_ruling_stated": len(no_ruling)},
              open(os.path.join(DORAR, "crosscheck.json"), "w"), ensure_ascii=False, indent=1)
    say(f"\n  wrote   data/dorar/crosscheck.md")


if __name__ == "__main__":
    main()
