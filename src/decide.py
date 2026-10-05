"""The decision stage: Jev picks the intended text, or says nothing matched.

This is the second half of the architecture the idea was filed with — "مرحلتان: استرجاع ثم قرار",
two stages, retrieval then decision — and the half that makes Isnad different from a chatbot.
Stage one (search.py) narrows 40,389 records to a shortlist. It cannot tell which candidate is
the one the user meant. Jev can, and reports how sure it is.

Why Choice and not a score per candidate: a Choice returns a probability for every option plus a
confidence for the selected one, which is exactly the filed promise — "يختار النص الأقرب ويعطي
احتمالاً معايَراً" — in a single request. TypeSafe's own re-ranking cookbook scores each
query-candidate pair separately; that is better for ordering a long list, but here the product
needs one answer, a calibrated probability, and an explicit no-match, and Choice gives all three
at once.

Two limits worth stating plainly:
  * Jev can only choose from the shortlist. "Re-ranking only ever sees the passages that make the
    shortlist", so a text stage one misses is unreachable here. That is why stage one is tuned for
    recall, not for first place.
  * Confidence describes how concentrated Jev's distribution is. It is not proof the text is the
    right one, and it says nothing about whether the hadith is authentic — that comes from the
    named scholar's ruling carried in the record.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

MODEL = "jev-latest"
SHORTLIST = 12          # candidates handed to Jev
MAX_CAND_CHARS = 420    # per candidate, to keep one request compact
# Send candidates WITH their diacritics. Stripping them was tried on the assumption that the marks
# are matching noise, and it measured worse: confidence on "الأعمال بالنيات" fell from 0.74 to
# 0.49 and the verdict dropped from confident to tentative. Fully vocalized text is the natural
# form of this material, and Jev reads it better that way.
PLAIN_CANDIDATES = False

NO_MATCH = "no_match"

# Confidence bands. Isnad's whole claim is that it would rather say nothing than hand over a text
# it is unsure of, so the floor is deliberately high and the failure direction is silence.
HIGH = 0.70
LOW = 0.45


def load_key():
    """Read TYPESAFE_API_KEY. The .env lives outside the git repo on purpose, so the key cannot
    be committed to the public repository the challenge requires."""
    if os.environ.get("TYPESAFE_API_KEY"):
        return True
    for p in (os.path.join(HERE, "..", ".env"), os.path.join(HERE, "..", "..", ".env")):
        if os.path.isfile(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line.startswith("TYPESAFE_API_KEY") and "=" in line:
                    os.environ["TYPESAFE_API_KEY"] = line.split("=", 1)[1].strip().strip('"\'')
                    return True
    return False


def build_question(query, candidates):
    """One Choice over the shortlist, plus a presence judgment.

    Candidate keys are neutral (c1, c2, ...) rather than "bukhari:1". Option names are sent to the
    model, and a famous collection's name in the key would invite Jev to prefer it on reputation
    instead of on whether the text matches what the user described.
    """
    from typesafe_sdk import Choice, Noul

    criteria = {}
    keymap = {}
    for i, c in enumerate(candidates, 1):
        k = f"c{i}"
        keymap[k] = c
        label = c.get("matn") or ""
        if PLAIN_CANDIDATES:
            from _arabic import plain
            label = plain(label)
        label = label[:MAX_CAND_CHARS]
        criteria[k] = label
    criteria[NO_MATCH] = (
        "None of the texts above is the one being described. Choose this when the description "
        "points to a different text, or is too vague to identify any single one of these."
    )

    questions = {
        "pick": Choice(
            instructions=(
                "A user is trying to find one specific Qur'anic verse or hadith. They are "
                "describing it from memory, in their own words, possibly in a different language "
                "and possibly getting the wording wrong. Which of these texts is the one they are "
                "describing? Judge by meaning, not by shared wording. Choose no_match if none of "
                "them is the text they mean."
            ),
            criteria=criteria,
        ),
        # A separate presence judgment, because "the description is too vague to identify
        # anything" and "the right text is not on this list" need different replies to the user.
        "specific_enough": Noul(
            instructions=(
                "Does this description contain enough specific detail to identify one particular "
                "Qur'anic verse or hadith, as opposed to naming a broad topic?"
            ),
        ),
    }
    return questions, keymap


def decide(query, candidates, client=None):
    """Return the decision for one query over one shortlist."""
    from typesafe_sdk import TypeSafeClient

    questions, keymap = build_question(query, candidates)
    state = {"description": query}

    own = client is None
    client = client or TypeSafeClient()
    try:
        resp = client.system_one(state=state, questions=questions, model=MODEL)
    finally:
        if own:
            client.close()

    pick = resp.answers["pick"]
    specific = resp.answers["specific_enough"]
    chosen_key = pick.choice
    conf = float(pick.confidence)
    probs = {k: float(v) for k, v in (pick.probabilities or {}).items()}

    if chosen_key == NO_MATCH or chosen_key not in keymap:
        verdict, record = "no_match", None
    elif conf < LOW:
        verdict, record = "unsure", keymap[chosen_key]
    elif conf < HIGH:
        verdict, record = "tentative", keymap[chosen_key]
    else:
        verdict, record = "confident", keymap[chosen_key]

    return {
        "verdict": verdict,
        "record": record,
        "confidence": conf,
        "probability": probs.get(chosen_key),
        "probabilities": {(keymap[k]["id"] if k in keymap else k): v for k, v in probs.items()},
        "specific_enough": float(specific.noul),
        "message_ar": message_ar(verdict, record, float(specific.noul)),
    }


def message_ar(verdict, record, specific):
    """What Isnad says. Silence is a valid answer and is phrased as one, not as an apology.

    No-match leads with the fact, never with a complaint about the user's wording. An earlier
    version branched on the presence judgment and told a user whose English description was
    perfectly specific that their description was too vague — the shortlist had simply missed the
    text. Blaming the user for the system's own gap is the wrong default, so vagueness is now only
    ever appended as a suggestion.
    """
    if verdict == "no_match":
        base = "لم يُعثر على نص مطابق في المصادر المعتمدة."
        if specific < 0.35:
            return base + " إن كنت تقصد نصًا بعينه، أضف جزءًا من لفظه أو معناه."
        return base
    if verdict == "unsure":
        return "لم يُعثر على نص مطابق بثقة كافية. هذه أقرب نتيجة، ولا يُستشهد بها دون تحقق."
    if verdict == "tentative":
        return "نتيجة مرجحة وليست مؤكدة. راجع المصدر قبل الاستشهاد."
    return "تم تحديد النص."
