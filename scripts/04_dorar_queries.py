#!/usr/bin/env python3
"""Generate dorar.net lookup queries for two purposes.

dorar.net is the platform the challenge Reference Framework names for hadith grading, but it
refuses automated requests (HTTP 403, Cloudflare), so queries are run through a real browser
session and the answers cached in the repository. Two sets:

  ungraded — the hadiths our corpus could not grade. dorar may carry a ruling for them.
  sample   — a random sample of hadiths we DID grade, so the two sources can be compared and an
             agreement rate reported. A reliability claim with a number behind it is worth more
             than an assurance.

Usage: python3 scripts/04_dorar_queries.py [sample_size]
"""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _arabic import plain
from _common import CORPUS, ROOT, dump, ran, say

SEED = 450            # team number, so the sample is reproducible
WORDS = 7             # query length: long enough to be distinctive, short enough to match


def query_from(matn_norm):
    """Take a window from the middle of the matn. The opening words are often a formula shared by
    many reports, so a mid-text window discriminates better."""
    w = matn_norm.split()
    if len(w) <= WORDS:
        return " ".join(w)
    start = max(0, (len(w) - WORDS) // 2)
    return " ".join(w[start:start + WORDS])


def main():
    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    ran(f"python3 scripts/04_dorar_queries.py {n_sample}")

    with open(os.path.join(CORPUS, "corpus.jsonl"), encoding="utf-8") as f:
        had = [json.loads(l) for l in f]
    had = [r for r in had if r["kind"] == "hadith"]

    # Fractional ids (tirmidhi:815.2) are the compiler's own commentary attached to a hadith,
    # not a report in its own right, which is why they carry no grading. Kept separate so the
    # coverage number is not quietly flattered.
    ungraded = [r for r in had if not r.get("grade")]
    commentary = [r for r in ungraded if "." in str(r.get("number", ""))]
    say(f"  of the ungraded, {len(commentary)} are commentary blocks (fractional numbering)")
    graded = [r for r in had if r.get("grade")]
    random.seed(SEED)
    sample = random.sample(graded, min(n_sample, len(graded)))

    def pack(rows, purpose):
        out = []
        for r in rows:
            # plain(), not match_text: the folded form corrupts spelling for anything
            # sent to an external search.
            q = query_from(plain(r["matn"]))
            if len(q.split()) < 3:
                continue
            out.append({"id": r["id"], "purpose": purpose, "skey": q,
                        "our_grade": r.get("grade"), "our_grade_raw": r.get("grade_raw"),
                        "our_severity": r.get("severity"), "ref": r["ref"]})
        return out

    # Commentary blocks are excluded: they are not reports, so dorar has nothing to rule on and
    # querying them would only spend requests on someone else's public service.
    real_ungraded = [r for r in ungraded if "." not in str(r.get("number", ""))]
    queries = pack(real_ungraded, "ungraded") + pack(sample, "sample")
    say(f"  querying {len(real_ungraded)} real ungraded hadiths, skipping {len(commentary)} commentary")
    say(f"  ungraded: {len(ungraded)} hadiths with no ruling in our data")
    say(f"  sample  : {len(sample)} graded hadiths (seed {SEED})")
    say(f"  queries : {len(queries)}")
    dump(queries, os.path.join(ROOT, "data", "dorar", "queries.json"))
    say("  feed these through the browser session; answers land in data/dorar/")


if __name__ == "__main__":
    main()
