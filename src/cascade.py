"""Isnad stage two: a tournament of Jev judgments down to one answer, or to silence.

WHY A TOURNAMENT. Jev cannot be handed the whole corpus. 40,389 candidates is roughly five
million tokens in one request, and a Choice spread over 40,389 options returns a flat
distribution, which collapses confidence toward zero and destroys the single signal this product
depends on. TypeSafe's own re-ranking cookbook shortlists first for exactly this reason, and is
explicit about the consequence: "re-ranking only ever sees the passages that make the shortlist".

So the net is widened instead of removed:

    stage 1   hybrid search over 40,389            -> NET (default 120)
    round 1   one Choice per group of 12, ALL IN ONE REQUEST  -> a winner per group
    round 2   one Choice over the surviving winners            -> the answer + confidence

Round one is a single request, not ten. The docs state that independent questions over the same
state run in parallel and cannot see one another's answers, which is exactly the shape of "which
of these twelve is it" asked ten times over one description. Two sequential rounds, so latency is
about twice a single call rather than eleven times.

Every round carries an explicit no_match option, and a group whose answer is no_match contributes
no finalist. If no group yields one, Isnad says it found nothing. Silence is a real answer here,
not a failure mode.
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from decide import HIGH, LOW, NO_MATCH, load_key, message_ar   # noqa: E402
from _arabic import normalize                                   # noqa: E402

# Family merge at decision time. Search already collapses near-identical copies of a report, but
# its threshold is strict on purpose, because collapsing two DIFFERENT hadiths would hide one.
# Looser copies survive to the final round, and there they split Jev's probability: Bukhari 1
# took 0.59 and Bukhari 2529, the same hadith with "بالنية" and one more clause, took 0.24. A
# correct answer was reported as tentative because its own twin competed with it.
#
# The question the user asked is "which report is this", so the probability of a report is the
# sum over its copies on the final shortlist. The merge is looser than search's (0.60 against
# 0.80) because it only ever adds probability to the text Jev already chose; it cannot change
# which text is shown.
FAMILY_CONTAINMENT = 0.60
FAMILY_MIN_TOKENS = 5


def _tokens(rec):
    return set(normalize(rec.get("matn") or "").split())


def _same_report(a, b):
    if a.get("kind") != "hadith" or b.get("kind") != "hadith":
        return False
    ta, tb = _tokens(a), _tokens(b)
    d = min(len(ta), len(tb))
    return d >= FAMILY_MIN_TOKENS and len(ta & tb) / d >= FAMILY_CONTAINMENT

MODEL = "jev-latest"
NET = 120           # candidates taken from stage one
GROUP = 12          # candidates per Choice question
MAX_CAND_CHARS = 420
MAX_FINALISTS = 12

PICK_INSTRUCTIONS = (
    "A user is trying to find one specific Qur'anic verse or hadith. They are describing it from "
    "memory, in their own words, possibly in a different language and possibly misremembering the "
    "wording. Which of these texts is the one they are describing? Judge by meaning, not by "
    "shared wording. Each option is marked as a Qur'an verse or a hadith. If the user asks for a "
    "verse, choose the verse itself, not a hadith that quotes it; if they ask for a hadith, choose "
    "a hadith. Choose no_match if none of them is the text they mean."
)
NO_MATCH_DESC = (
    "None of the texts above is the one being described. Choose this when the description points "
    "to a different text, or is too vague to identify any single one of these."
)
# Level (د) of the Reference Framework: a fatwa or a personal case. The system must not issue an
# independent ruling; it refers the person to someone qualified. Isnad finds texts and issues no
# rulings at all, so a request for one is answered with a referral and no text - placing a verse
# beside "is this permitted for me" would read as an answer.
FATWA_INSTRUCTIONS = (
    "Is this person asking for a religious ruling or fatwa about their own situation, for example "
    "whether something is permitted or forbidden for them, rather than trying to find the wording "
    "or source of a specific Qur'anic verse or hadith?"
)
FATWA_THRESHOLD = 0.60

SPECIFIC_INSTRUCTIONS = (
    "Does this description contain enough specific detail to identify one particular Qur'anic "
    "verse or hadith, as opposed to naming a broad topic?"
)


def _criteria(group):
    """Neutral option keys. Option names reach the model, and 'bukhari:1' would invite a choice
    made on a collection's reputation rather than on whether the text matches the description.

    The KIND is shown, though, because it is part of what the user asked for. Asked for "the
    verse", Jev chose Abu Dawud 4003 at 0.97, a hadith whose matn is that verse in braces: with
    the kind hidden the two were indistinguishable. Collection is irrelevant to the request and
    stays hidden; kind is relevant and is stated."""
    crit, keymap = {}, {}
    for i, c in enumerate(group):
        k = f"c{i}"
        keymap[k] = c
        tag = "[Qur'an verse] " if c.get("kind") == "ayah" else "[Hadith] "
        crit[k] = tag + (c.get("matn") or "")[:MAX_CAND_CHARS]
    crit[NO_MATCH] = NO_MATCH_DESC
    return crit, keymap


def _groups(candidates, size=GROUP):
    return [candidates[i:i + size] for i in range(0, len(candidates), size)]


async def run(query, candidates, client=None, net=NET, group=GROUP):
    """Return the decision. Needs an AsyncTypeSafeClient, or makes its own."""
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

    cands = candidates[:net]
    groups = _groups(cands, group)
    state = {"description": query}

    questions, keymaps = {}, {}
    for gi, g in enumerate(groups):
        crit, km = _criteria(g)
        questions[f"g{gi}"] = Choice(instructions=PICK_INSTRUCTIONS, criteria=crit)
        keymaps[f"g{gi}"] = km
    questions["specific_enough"] = Noul(instructions=SPECIFIC_INSTRUCTIONS)
    questions["fatwa_request"] = Noul(instructions=FATWA_INSTRUCTIONS)

    own = client is None
    client = client or AsyncTypeSafeClient()
    try:
        r1 = await client.system_one(state=state, questions=questions, model=MODEL)

        finalists = []
        for gi in range(len(groups)):
            a = r1.answers[f"g{gi}"]
            if a.choice == NO_MATCH or a.choice not in keymaps[f"g{gi}"]:
                continue
            rec = keymaps[f"g{gi}"][a.choice]
            finalists.append((rec, float(a.confidence),
                              float((a.probabilities or {}).get(a.choice, 0.0))))
        specific = float(r1.answers["specific_enough"].noul)
        fatwa = float(r1.answers["fatwa_request"].noul)

        rounds = 1
        if fatwa >= FATWA_THRESHOLD:
            r = _result("fatwa_request", None, fatwa, None, specific, rounds, len(cands),
                        len(groups))
            r["fatwa_request"] = fatwa
            return r
        if not finalists:
            return _result("no_match", None, 1.0, None, specific, rounds, len(cands), len(groups))

        # Order finalists by round-one confidence so the strongest candidates survive the cap.
        finalists.sort(key=lambda t: -t[1])
        short = [f[0] for f in finalists[:MAX_FINALISTS]]

        if len(short) == 1:
            # One survivor still goes to round two: its round-one confidence was measured against
            # eleven neighbours, not against the field, and the product reports a calibrated
            # number or it reports nothing.
            pass

        crit, km = _criteria(short)
        r2 = await client.system_one(
            state=state,
            questions={"pick": Choice(instructions=PICK_INSTRUCTIONS, criteria=crit)},
            model=MODEL)
        rounds = 2
        pick = r2.answers["pick"]
        conf = float(pick.confidence)
        probs = {k: float(v) for k, v in (pick.probabilities or {}).items()}

        if pick.choice == NO_MATCH or pick.choice not in km:
            return _result("no_match", None, conf, None, specific, rounds, len(cands), len(groups))
        rec = km[pick.choice]
        family = [k for k in km if k != pick.choice and _same_report(km[k], rec)]
        p_report = probs.get(pick.choice, 0.0) + sum(probs.get(k, 0.0) for k in family)
        # The verdict rests on the probability of the REPORT. Jev's own confidence statistic
        # measures how concentrated the distribution is, and a distribution split between two
        # copies of one hadith is concentrated on one answer even though it looks spread.
        verdict = ("confident" if p_report >= HIGH else "tentative" if p_report >= LOW
                   else "unsure")
        out = _result(verdict, rec, p_report, probs.get(pick.choice), specific, rounds,
                      len(cands), len(groups),
                      probabilities={(km[k]["id"] if k in km else k): v
                                     for k, v in probs.items()})
        out["jev_confidence"] = conf
        out["family"] = [km[k]["id"] for k in family]
        return out
    finally:
        if own:
            await client.close()


def _result(verdict, record, conf, prob, specific, rounds, net, groups, probabilities=None):
    return {
        "verdict": verdict,
        "record": record,
        "confidence": conf,
        "probability": prob,
        "probabilities": probabilities or {},
        "specific_enough": specific,
        "message_ar": message_ar(verdict, record, specific),
        "jev_rounds": rounds,
        "fatwa_request": None,
        "jev_confidence": None,
        "family": [],
        "net": net,
        "groups": groups,
    }


def run_sync(query, candidates, **kw):
    return asyncio.run(run(query, candidates, **kw))
