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

MODEL = "jev-latest"
NET = 120           # candidates taken from stage one
GROUP = 12          # candidates per Choice question
MAX_CAND_CHARS = 420
MAX_FINALISTS = 12

PICK_INSTRUCTIONS = (
    "A user is trying to find one specific Qur'anic verse or hadith. They are describing it from "
    "memory, in their own words, possibly in a different language and possibly misremembering the "
    "wording. Which of these texts is the one they are describing? Judge by meaning, not by "
    "shared wording. Choose no_match if none of them is the text they mean."
)
NO_MATCH_DESC = (
    "None of the texts above is the one being described. Choose this when the description points "
    "to a different text, or is too vague to identify any single one of these."
)
SPECIFIC_INSTRUCTIONS = (
    "Does this description contain enough specific detail to identify one particular Qur'anic "
    "verse or hadith, as opposed to naming a broad topic?"
)


def _criteria(group):
    """Neutral option keys. Option names reach the model, and 'bukhari:1' would invite a choice
    made on a collection's reputation rather than on whether the text matches the description."""
    crit, keymap = {}, {}
    for i, c in enumerate(group):
        k = f"c{i}"
        keymap[k] = c
        crit[k] = (c.get("matn") or "")[:MAX_CAND_CHARS]
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

        rounds = 1
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
        verdict = ("confident" if conf >= HIGH else "tentative" if conf >= LOW else "unsure")
        return _result(verdict, rec, conf, probs.get(pick.choice), specific, rounds,
                       len(cands), len(groups),
                       probabilities={(km[k]["id"] if k in km else k): v
                                      for k, v in probs.items()})
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
        "net": net,
        "groups": groups,
    }


def run_sync(query, candidates, **kw):
    return asyncio.run(run(query, candidates, **kw))
