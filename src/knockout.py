"""Isnad stage two, full-corpus mode: Jev reads every text.

Chosen by the team lead over every narrowing option, on the principle that in this domain a
missed text costs more than a slow answer. No search shortlist decides what Jev may see: all
40,389 texts enter round one.

    preliminary  one tiny request: is this a fatwa request; does it name one text or a subject
    round 1      every unique text, in fixed random groups of GROUP, one Choice per group, with
                 no_match - so the text described competes with unrelated texts, not with its
                 lookalikes, and is easy to recognise
    rounds 2+    Choice over the winners, until at most FINAL remain
    final        one Choice, with the family-of-copies merge; for a subject, a relevance Noul
                 over every round-one winner

COST, measured on 2026-10-05, not estimated:
    one request holds about 240 texts before the API answers 400 max_tokens_exceeded;
    diacritised Arabic costs about 1.06 input tokens per character;
    the full corpus is about 8 million input tokens per search;
    the organisation's limit is 100,000 input tokens per second,
so a search takes at least ~80 seconds. The pacer below keeps every request inside that limit
so a search never fails with 429 - it is slow, never broken.

NOTHING DROPPED. Exact duplicates (2,761, e.g. the 31 verses of Ar-Rahman that read
"فبأي آلاء ربكما تكذبان") are judged once and listed with the answer. The compiler's commentary is
split off before judging (7.6% of the characters): it is not the hadith.
"""
import asyncio
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from _arabic import join_open_tanween, normalize, plain, split_commentary  # noqa: E402
from _dorar import verify_url                              # noqa: E402
from cascade import (FATWA_INSTRUCTIONS, FATWA_THRESHOLD, HIGH, LOW, MAX_CAND_CHARS,  # noqa: E402
                     NO_MATCH, NO_MATCH_DESC, PICK_INSTRUCTIONS, RELEVANCE_INSTRUCTIONS,
                     SPECIFIC_INSTRUCTIONS, TOPIC_MAX, TOPIC_MIN_REL, TOPIC_SPECIFIC,
                     _GRADE_ORDER, _dedupe, _result, _same_report)

MODEL = "jev-latest"
GROUP = 20                 # texts per round-one Choice; overhead per question amortised wider
GROUP_LATER = 12           # texts per Choice in later rounds, where candidates resemble each other
FINAL = 12                 # at most this many reach the final Choice
RUNNER_UP = 0.25           # a second text from one group also advances above this probability
REQUEST_TOKENS = 45_000    # per request, under the measured ~52k ceiling with margin
TOKENS_PER_SEC = 90_000    # under the organisation's 100,000/s
REQUESTS_PER_SEC = 60      # under the organisation's 80/s
SEED = 450                 # fixed grouping, so the same query gives the same answer
TOKENS_PER_CHAR = 1.06     # measured, diacritised: 240 texts -> 52,349 input tokens
# Round one reads plain text. Measured on the group holding each test case's answer: recall 8/8
# with diacritics and 8/8 without, the answer winning at 0.97-1.00 both ways - in round one it is
# up against unrelated texts, and the marks do not decide it. They do decide between lookalikes,
# where they raised confidence 0.49 -> 0.74, so later rounds and the final keep them. Plain text
# costs 2.3x fewer tokens (21,155 vs ~48,546 for the same 220 texts): ~40 s instead of ~86 s.
PLAIN_TOKENS_PER_CHAR = 0.70   # measured 0.687
QUESTION_OVERHEAD = 140    # instructions and the no_match option, per Choice

ROUND1_INSTRUCTIONS = (
    "A user is describing, from memory and in their own words, one Qur'anic verse or hadith. "
    "Is the text they describe among these options? Pick it if it is here; choose no_match if "
    "it is not. Judge by meaning, not shared words."
)


class Pacer:
    """Token-bucket pacing across concurrent requests: tokens per second and requests per
    second, both under the organisation's limits."""

    def __init__(self, tps=TOKENS_PER_SEC, rps=REQUESTS_PER_SEC):
        self.tps, self.rps = tps, rps
        self.tokens = float(tps)
        self.reqs = float(rps)
        self.t = time.monotonic()
        self.lock = asyncio.Lock()

    async def take(self, n_tokens):
        n_tokens = min(n_tokens, self.tps)
        while True:
            async with self.lock:
                now = time.monotonic()
                dt = now - self.t
                self.t = now
                self.tokens = min(self.tps, self.tokens + dt * self.tps)
                self.reqs = min(self.rps, self.reqs + dt * self.rps)
                if self.tokens >= n_tokens and self.reqs >= 1:
                    self.tokens -= n_tokens
                    self.reqs -= 1
                    return
                wait = max((n_tokens - self.tokens) / self.tps, (1 - self.reqs) / self.rps)
            await asyncio.sleep(max(wait, 0.01))


class Corpus:
    """Every unique text once, with its copies, and a fixed random order for grouping."""

    def __init__(self, ix):
        self.ix = ix
        recs = ix.recs
        matn = {row[0]: (join_open_tanween(row[1]) if row[0].startswith("quran:") else row[1])
                for row in ix.db.execute("SELECT id, matn FROM display")}
        seen = {}
        self.items = []
        for ri, r in enumerate(recs):
            m = matn.get(r["id"]) or ""
            if r["kind"] == "hadith":
                m = split_commentary(m)[0]
            key = (r["kind"], normalize(m))
            if not key[1]:
                continue
            if key in seen:
                self.items[seen[key]]["copies"].append(ri)
                continue
            seen[key] = len(self.items)
            text = m[:MAX_CAND_CHARS]
            ptext = plain(text)
            self.items.append({"rec": ri, "copies": [], "kind": r["kind"], "text": text,
                               "tok": int(len(text) * TOKENS_PER_CHAR) + 2,
                               "plain": ptext,
                               "ptok": int((len(ptext) + 16) * PLAIN_TOKENS_PER_CHAR) + 2})
        self.order = list(range(len(self.items)))
        random.Random(SEED).shuffle(self.order)
        self.total_tokens = sum(it["tok"] for it in self.items)
        self.round1_tokens = sum(it["ptok"] for it in self.items)

    def candidate(self, item_index):
        """The record a front end and the final decision need, built only for survivors."""
        it = self.items[item_index]
        ix = self.ix
        r = dict(ix.recs[it["rec"]])
        r.update(ix.display(r["id"]))
        if r["kind"] == "hadith":
            r["matn"], r["commentary"] = split_commentary(r.get("matn") or "")
        r["variants"] = [{"id": ix.recs[c]["id"], "ref": ix.recs[c]["ref"],
                          "grade": ix.recs[c].get("grade")} for c in it["copies"]]
        r["verify_url"] = (verify_url(plain(r.get("matn") or ""))
                           if r["kind"] == "hadith" else None)
        r["_item"] = item_index
        return r


def _tag(kind):
    return "[Qur'an verse] " if kind == "ayah" else "[Hadith] "


def _pack(groups, item_tok):
    """Pack groups into requests without crossing the per-request token budget."""
    reqs, cur, cur_tok = [], [], 0
    for g in groups:
        t = sum(item_tok(i) for i in g) + QUESTION_OVERHEAD
        if cur and cur_tok + t > REQUEST_TOKENS:
            reqs.append(cur)
            cur, cur_tok = [], 0
        cur.append(g)
        cur_tok += t
    if cur:
        reqs.append(cur)
    return reqs


async def _knockout_round(client, pacer, state, groups, text_of, tok_of, instructions,
                          progress=None, label="round"):
    """One round: every group answered by one Choice; returns surviving item indices with the
    probability each won by."""
    from typesafe_sdk import Choice

    requests = _pack(groups, tok_of)
    done = {"groups": 0}
    winners = []

    async def send(batch):
        questions, keymaps = {}, {}
        for gi, g in enumerate(batch):
            crit, km = {}, {}
            for j, item in enumerate(g):
                k = f"c{j}"
                km[k] = item
                crit[k] = text_of(item)
            crit[NO_MATCH] = NO_MATCH_DESC
            questions[f"g{gi}"] = Choice(instructions=instructions, criteria=crit)
            keymaps[f"g{gi}"] = km
        est = sum(sum(tok_of(i) for i in g) + QUESTION_OVERHEAD for g in batch)
        await pacer.take(est)
        resp = await client.system_one(state=state, questions=questions, model=MODEL)
        out = []
        for gi in range(len(batch)):
            a = resp.answers[f"g{gi}"]
            probs = {k: float(v) for k, v in (a.probabilities or {}).items()}
            ranked = sorted(((k, p) for k, p in probs.items() if k != NO_MATCH),
                            key=lambda kp: -kp[1])
            if a.choice != NO_MATCH and a.choice in keymaps[f"g{gi}"]:
                out.append((keymaps[f"g{gi}"][a.choice], probs.get(a.choice, 0.0)))
                # A group can hold two relevant texts, say two hadiths about lying; a Choice
                # keeps one, so a strong runner-up advances too rather than being lost here.
                for k, p in ranked:
                    if k != a.choice and p >= RUNNER_UP:
                        out.append((keymaps[f"g{gi}"][k], p))
                        break
        done["groups"] += len(batch)
        if progress:
            progress(label, done["groups"], len(groups))
        return out

    for res in await asyncio.gather(*(send(b) for b in requests)):
        winners.extend(res)
    return winners


async def run(query, ix, corpus, client, pacer=None, progress=None):
    """Full-corpus knockout. Returns the same shape as cascade.run."""
    from typesafe_sdk import Choice, Noul

    pacer = pacer or Pacer()
    state = {"description": query}
    t0 = time.time()

    # Preliminary: a fatwa request is answered with a referral before eight million tokens are
    # spent reading texts it will never show.
    await pacer.take(400)
    pre = await client.system_one(state=state, model=MODEL, questions={
        "fatwa_request": Noul(instructions=FATWA_INSTRUCTIONS),
        "specific_enough": Noul(instructions=SPECIFIC_INSTRUCTIONS),
    })
    fatwa = float(pre.answers["fatwa_request"].noul)
    specific = float(pre.answers["specific_enough"].noul)
    n_items = len(corpus.items)
    if fatwa >= FATWA_THRESHOLD:
        r = _result("fatwa_request", None, fatwa, None, specific, 0, n_items, 0)
        r["fatwa_request"] = fatwa
        return r

    items = corpus.items
    text_of = lambda i: _tag(items[i]["kind"]) + items[i]["text"]
    tok_of = lambda i: items[i]["tok"] + 4

    # Round 1: every unique text.
    order = corpus.order
    groups = [order[s:s + GROUP] for s in range(0, len(order), GROUP)]
    plain_of = lambda i: _tag(items[i]["kind"]) + items[i]["plain"]
    ptok_of = lambda i: items[i]["ptok"]
    w1 = await _knockout_round(client, pacer, state, groups, plain_of, ptok_of,
                               ROUND1_INSTRUCTIONS, progress, "round1")
    round1_winners = []
    seen = set()
    for i, p in sorted(w1, key=lambda ip: -ip[1]):
        if i not in seen:
            seen.add(i)
            round1_winners.append(i)
    rounds = 1

    # Later rounds: narrow the winners by further Choice rounds until FINAL remain.
    survivors = list(round1_winners)
    while len(survivors) > FINAL:
        rounds += 1
        gs = [survivors[s:s + GROUP_LATER] for s in range(0, len(survivors), GROUP_LATER)]
        wn = await _knockout_round(client, pacer, state, gs, text_of, tok_of,
                                   PICK_INSTRUCTIONS, progress, f"round{rounds}")
        nxt, seen = [], set()
        for i, p in sorted(wn, key=lambda ip: -ip[1]):
            if i not in seen:
                seen.add(i)
                nxt.append(i)
        if len(nxt) >= len(survivors):      # no progress; stop rather than loop
            survivors = nxt[:FINAL]
            break
        survivors = nxt

    # Final request: the decision, and for a subject, relevance over every round-one winner.
    finalists = [corpus.candidate(i) for i in survivors]
    topic_pool = []
    if specific < TOPIC_SPECIFIC:
        pool_idx = round1_winners[:60]
        topic_pool = _dedupe([(corpus.candidate(i), 1.0) for i in pool_idx])
        topic_pool = [c for c, _ in topic_pool]

    q, km = {}, {}
    st = dict(state)
    if finalists:
        crit = {}
        for j, c in enumerate(finalists):
            k = f"c{j}"
            km[k] = c
            crit[k] = _tag(c["kind"]) + (c.get("matn") or "")[:MAX_CAND_CHARS]
        crit[NO_MATCH] = NO_MATCH_DESC
        q["pick"] = Choice(instructions=PICK_INSTRUCTIONS, criteria=crit)
    if topic_pool:
        st["texts"] = [{"kind": "Qur'an verse" if c["kind"] == "ayah" else "hadith",
                        "text": (c.get("matn") or "")[:MAX_CAND_CHARS]} for c in topic_pool]
        for i in range(len(topic_pool)):
            q[f"t{i}"] = Noul(instructions=RELEVANCE_INSTRUCTIONS.format(i=i))
    if not q:
        out = _result("no_match", None, 1.0, None, specific, rounds, n_items, len(groups))
        out["elapsed_s"] = round(time.time() - t0, 1)
        return out

    est = sum(len(str(v)) for v in st.get("texts", [])) + sum(
        len(c.get("matn") or "") for c in finalists)
    await pacer.take(int(est * TOKENS_PER_CHAR) + 2000)
    resp = await client.system_one(state=st, questions=q, model=MODEL)
    rounds += 1
    if progress:
        progress("final", 1, 1)

    specific_answer = None
    if "pick" in q:
        pick = resp.answers["pick"]
        probs = {k: float(v) for k, v in (pick.probabilities or {}).items()}
        if pick.choice != NO_MATCH and pick.choice in km:
            rec = km[pick.choice]
            family = [k for k in km if k != pick.choice and _same_report(km[k], rec)]
            p_report = probs.get(pick.choice, 0.0) + sum(probs.get(k, 0.0) for k in family)
            verdict = ("confident" if p_report >= HIGH else "tentative" if p_report >= LOW
                       else "unsure")
            specific_answer = _result(
                verdict, rec, p_report, probs.get(pick.choice), specific, rounds, n_items,
                len(groups),
                probabilities={(km[k]["id"] if k in km else k): v for k, v in probs.items()})
            specific_answer["jev_confidence"] = float(pick.confidence)
            specific_answer["family"] = [km[k]["id"] for k in family]
            specific_answer["_candidates"] = finalists

    def finish(o):
        o["elapsed_s"] = round(time.time() - t0, 1)
        o["texts_read"] = n_items
        return o

    if specific_answer and (specific_answer["verdict"] == "confident" or not topic_pool):
        return finish(specific_answer)
    if topic_pool:
        scored = [(c, float(resp.answers[f"t{i}"].noul)) for i, c in enumerate(topic_pool)]
        relevant = _dedupe([(c, p) for c, p in scored if p >= TOPIC_MIN_REL])
        if relevant:
            relevant.sort(key=lambda cp: (_GRADE_ORDER.get(cp[0].get("severity") or "unknown", 1),
                                          -cp[1]))
            out = _result("topic", None, None, None, specific, rounds, n_items, len(groups))
            out["topic"] = [{"record": c, "relevance": p} for c, p in relevant[:TOPIC_MAX]]
            return finish(out)
    if specific_answer:
        return finish(specific_answer)
    return finish(_result("no_match", None, 1.0, None, specific, rounds, n_items, len(groups)))
