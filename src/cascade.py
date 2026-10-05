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
from _dorar import fiqh_url                                     # noqa: E402
from search import REQUEST_WORDS, light_stem                    # noqa: E402

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
    return (d >= FAMILY_MIN_TOKENS and len(ta & tb) / d >= FAMILY_CONTAINMENT) or \
        (d >= 2 and ta == tb)

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
FATWA_THRESHOLD = 0.60     # FATWA_* now serve knockout mode only, which still refers and stops

# WHAT IS ASKED. Session 1 met every question about a ruling with a referral and no text:
# "ماحكم الزنا" got "سؤالك يحتاج فتوى" and nothing else, though Al-Isra 32 speaks to it and the
# Reference Framework puts such texts at level (أ), "answered directly, with the source". The
# framework separates three requests, and so does Isnad now:
#   find_text       the core job: a verse or hadith, its wording, its source or its GRADE ("ما حكم
#                   حديث" asks for a grading, which Isnad relays from named scholars)
#   general_ruling  the ruling on a matter in general: the texts on it, then a referral to the
#                   approved fiqh reference (dorar.net/feqhia) and to scholars
#   personal_case   level (د), the asker's own case: "يوضح المعلومات العامة ويحيل إلى جهة مؤهلة",
#                   the same general texts with the referral first
# In none of them does Isnad state a ruling. It selects texts; every word shown is a source's.
ASK_INSTRUCTIONS = "What is this person asking Isnad for?"
ASK_OPTIONS = {
    "find_text": (
        "To find a specific Qur'anic verse or hadith, its exact wording, its source or its "
        "authenticity grading (for example 'ما صحة حديث' or 'ما حكم حديث ...'), or the verses or "
        "hadith on a subject (for example 'آية عن الصبر', 'ايه عن النوم', 'حديث عن الغضب')."),
    "general_ruling": (
        "The Islamic ruling on a matter in general: whether something is permitted, forbidden or "
        "obligatory, asked about people in general rather than the asker's own situation."),
    "personal_case": (
        "A ruling on the asker's own situation or circumstances, usually asked in the first "
        "person, for example 'هل يجوز لي', 'هل يجوز أفطر وأنا مسافر', 'طلقت زوجتي', 'is it "
        "permitted for me', 'my marriage', 'in my country', so that the answer depends on the "
        "facts of their case."),
}
# P(general_ruling) + P(personal_case). Measured (eval/ask_probe.py, 3 runs each): ruling
# questions 0.97-0.99; "ايه عن بر الوالدين" 0.52-0.56 and once over 0.60 in a live run, which sent
# a request for verses down the ruling path. 0.75 keeps the margin on both sides.
RULING_THRESHOLD = 0.75
# A reader who names the kind of text ("آية عن ...", "حديث عن ...", "verse about ...") and uses no
# ruling word wants the texts, not a ruling, whatever the classifier says. "ايه" is also dialect
# for "what", which is how "ايه عن النوم" was once read as a question about sleep.
RULING_WORDS = {"حكم", "الحكم", "ماحكم", "يجوز", "يحل", "يحرم", "حلال", "حرام", "مكروه", "واجب",
                "جائز", "فتوي", "الفتوي", "ruling", "permissible", "permitted", "allowed",
                "forbidden", "haram", "halal", "fatwa"}
RULING_RELEVANCE_INSTRUCTIONS = (
    "The user in `description` asks about the Islamic ruling on a matter. Here is a {kind}: "
    "\"{text}\". Does this text address that matter itself, for example by commanding it, "
    "forbidding it, warning against it, praising it, or setting out its consequence? Answer yes "
    "only if the text addresses the matter, not if it merely shares a word with it."
)

# TOPIC MODE. "حديث عن الكذب" names a subject, not a text: there are dozens of hadiths about
# lying. Isnad used to answer it with "no matching text in the approved sources", which is false -
# fast search had already shortlisted Tirmidhi 1939, Muslim 6638, Ibn Majah 31 and An-Nahl 116 -
# and a reader could leave believing the sources say nothing about lying.
#
# When the presence judgment says the description is broad, round two also asks one Noul per
# candidate, "is this text about that subject?", in the same request as the final Choice, so a
# topic query costs no extra round trip. The relevant texts are listed with their sources and
# rulings; the reader picks the one they mean. Still selection, never generation.
TOPIC_SPECIFIC = 0.35      # below this, the description names a subject rather than a text
TOPIC_K = 24               # candidates judged for relevance
# Right texts scored 0.80 or more in every list measured on 2026-10-06 (sleep, patience, parents,
# death, anger, mercy, lying, zina); wrong ones that passed 0.60 sat at 0.61-0.70 (84:17, 53:54).
TOPIC_MIN_REL = 0.75
TOPIC_MAX = 8
TOPIC_KIND_MIN = 6       # texts of the asked-for kind needed to judge only that kind
# The reader remembers a text by something it says, and picks theirs from the list. Asked whether
# a text was "about" the subject, Jev turned Ayat al-Kursi (2:255) away for "ايه عن النوم" among
# 24 texts: it is about Allah's attributes, yet "لا تأخذه سنة ولا نوم" is what that reader recalls.
# The light stemmer files charity (الصدقة) and truthfulness (الصدق) under one stem, so the
# question also rules out a word used in another sense. Measured on fixed texts
# (eval/relevance_probe.py, 19 judgements): charity hadith for "حديث عن الصدق" 0.85 -> 0.08;
# every right text 0.83 or more.
RELEVANCE_INSTRUCTIONS = (
    "The user remembers a text by something it says and describes it in `description`. Here is "
    "a {kind}: \"{text}\". Does this text say something about that subject: state it, describe "
    "it, command or forbid it, or deny it of someone? Answer no if the text only shares a word "
    "or a root with the description, uses that word in another sense (as charity, الصدقة, is "
    "not truthfulness, الصدق), or says nothing about the subject."
)


def _judge(template, c):
    """A relevance question that carries its text. Questions that pointed at `texts[i]` in one
    shared list let Jev's judgments bleed between neighbours: for "ايه عن النوم" 2:255 scored
    0.52 in ranked order and 0.72 reversed, while 55:10, next to a true match, went 0.54 -> 0.91.
    With the text inside the question, 2:255 scored 0.85 in both orders and 55:10 0.33 / 0.18."""
    kind = "Qur'an verse" if c.get("kind") == "ayah" else "hadith"
    return template.format(kind=kind, text=(c.get("matn") or "")[:MAX_CAND_CHARS].replace('"', "'"))


# Authentic texts first: present the sound before the weak, as the framework's da'wah quality
# standard asks. Weak and fabricated texts stay on the list, clearly graded, because knowing that
# a saying people circulate is fabricated is itself what the reader needs.
# The Qur'an before the hadith: "يقدم الأصل قبل الفرع" (Reference Framework, da'wah quality).
_GRADE_ORDER = {"quran": 0, "sahih": 1, "hasan": 1, "unknown": 2, "daif": 3, "mawdu": 3}

SPECIFIC_INSTRUCTIONS = (
    "Does this description contain enough specific detail to identify one particular Qur'anic "
    "verse or hadith, as opposed to naming a broad topic?"
)


# A QUOTED SAYING MUST BE IN THE ANSWER. Asked "اختلاف أمتي رحمة" - a saying that is not a sound
# hadith - Jev once answered 30:22 "واختلاف ألسنتكم وألوانكم" at 0.71, on the shared word. When
# the query is a bare Arabic quotation (no "عن", "اللي", "يقول"...: those introduce a paraphrase),
# at least half of its content words, light-stemmed, must be in the chosen text's own words, or
# the answer is "not found". Measured (2026-10-06, 20 right answers): bare quotations 0.62-1.00;
# the wrong ones 0.00-0.33. Paraphrases reach 0.40 and are not checked.
QUOTE_MIN = 0.5
DESCRIPTION_WORDS = {"عن", "اللي", "التي", "الذي", "فيها", "فيه", "يقول", "تقول", "يتكلم",
                     "تتكلم", "معناه", "معني"}
FUNCTION_WORDS = {"في", "من", "علي", "الي", "ان", "قال", "ما", "هو", "هي", "او", "ثم", "كل",
                  "هذا", "هذه", "هذي", "ذلك", "له", "لها", "لهم", "به", "بها", "كان", "يا", "لا",
                  "ولا", "لم", "لن", "قد", "حتي", "اذا", "و", "الا", "انه", "انها", "لما", "لي"}


def _quote_ok(query, rec):
    words = normalize(query).split()
    if not words or any(w in DESCRIPTION_WORDS for w in words):
        return True
    content = [light_stem(w) for w in words if w not in REQUEST_WORDS and w not in FUNCTION_WORDS]
    if not content:
        return True
    text = {light_stem(w) for w in (rec.get("surface") or normalize(rec.get("matn") or "")).split()}
    return sum(1 for w in content if w in text) / len(content) >= QUOTE_MIN


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


def _topic_pool(cands):
    """The first TOPIC_K distinct texts from stage one, with looser copies of one report merged
    so the relevance list does not show the same hadith twice. When the reader asked for a kind
    ("ايه عن النوم") and the shortlist holds enough of it, only that kind is judged: answering a
    request for verses with eight hadith, as happened, is not an answer to it."""
    kind = cands[0].get("wanted_kind") if cands else None
    same = [c for c in cands if c.get("kind") == kind] if kind else []
    if len(same) >= TOPIC_KIND_MIN:
        cands = same
    pool = []
    for c in cands:
        if any(_same_report(c, p) for p in pool):
            continue
        pool.append(c)
        if len(pool) >= TOPIC_K:
            break
    return pool


def _dedupe(pairs):
    out = []
    for c, p in pairs:
        if any(_same_report(c, q) for q, _ in out):
            continue
        out.append((c, p))
    return out


def _groups(candidates, size=GROUP):
    return [candidates[i:i + size] for i in range(0, len(candidates), size)]


async def run(query, candidates, client=None, net=NET, group=GROUP):
    """Return the decision. Needs an AsyncTypeSafeClient, or makes its own."""
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

    # Texts search held in reserve for the other kind (search.MIN_PER_KIND) serve ruling lists
    # only. Offered to the single-text choice, they let Jev answer "اختلاف أمتي رحمة", a saying
    # that is not a sound hadith, with 30:22 "واختلاف ألسنتكم" at full confidence.
    cands = [c for c in candidates if not c.get("reserve")][:net]
    groups = _groups(cands, group)
    state = {"description": query}

    questions, keymaps = {}, {}
    for gi, g in enumerate(groups):
        crit, km = _criteria(g)
        questions[f"g{gi}"] = Choice(instructions=PICK_INSTRUCTIONS, criteria=crit)
        keymaps[f"g{gi}"] = km
    questions["specific_enough"] = Noul(instructions=SPECIFIC_INSTRUCTIONS)
    questions["ask"] = Choice(instructions=ASK_INSTRUCTIONS, criteria=ASK_OPTIONS)

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
        ask = {k: float(v) for k, v in (r1.answers["ask"].probabilities or {}).items()}

        rounds = 1
        p_ruling = ask.get("general_ruling", 0.0) + ask.get("personal_case", 0.0)
        names_kind = bool(cands) and cands[0].get("wanted_kind") is not None
        ruling_word = bool(set(normalize(query).lower().split()) & RULING_WORDS)
        if p_ruling >= RULING_THRESHOLD and (ruling_word or not names_kind):
            kind = ("personal" if ask.get("personal_case", 0.0) >= ask.get("general_ruling", 0.0)
                    else "general")
            return await _ruling(client, query, candidates, kind, p_ruling, specific, len(groups))
        # A broad description goes to topic mode even when every group answered no_match: the
        # pick question asks for ONE text, and for "حديث عن الكذب" no single text is the one, so
        # all ten groups can rightly decline. Exiting here reported "nothing found" for a subject
        # the shortlist covered (seen 2026-10-05 once the shortlist changed; round two never ran).
        topic_pool = _topic_pool(cands) if specific < TOPIC_SPECIFIC else []
        if not finalists and not topic_pool:
            return _result("no_match", None, 1.0, None, specific, rounds, len(cands), len(groups))

        # Order finalists by round-one confidence so the strongest candidates survive the cap.
        finalists.sort(key=lambda t: -t[1])
        short = [f[0] for f in finalists[:MAX_FINALISTS]]

        q2, km = {}, {}
        state2 = dict(state)
        if short:
            crit, km = _criteria(short)
            q2["pick"] = Choice(instructions=PICK_INSTRUCTIONS, criteria=crit)
        for i, c in enumerate(topic_pool):
            q2[f"t{i}"] = Noul(instructions=_judge(RELEVANCE_INSTRUCTIONS, c))
        if not q2:
            return _result("no_match", None, 1.0, None, specific, rounds, len(cands), len(groups))

        r2 = await client.system_one(state=state2, questions=q2, model=MODEL)
        rounds = 2

        specific_answer = None
        if "pick" in q2:
            pick = r2.answers["pick"]
            conf = float(pick.confidence)
            probs = {k: float(v) for k, v in (pick.probabilities or {}).items()}
            if pick.choice != NO_MATCH and pick.choice in km:
                rec = km[pick.choice]
                family = [k for k in km if k != pick.choice and _same_report(km[k], rec)]
                p_report = probs.get(pick.choice, 0.0) + sum(probs.get(k, 0.0) for k in family)
                # The verdict rests on the probability of the REPORT. Jev's own confidence
                # statistic measures how concentrated the distribution is, and a distribution
                # split between two copies of one hadith is concentrated on one answer even
                # though it looks spread.
                verdict = ("confident" if p_report >= HIGH else "tentative" if p_report >= LOW
                           else "unsure")
                specific_answer = _result(
                    verdict, rec, p_report, probs.get(pick.choice), specific, rounds,
                    len(cands), len(groups),
                    probabilities={(km[k]["id"] if k in km else k): v for k, v in probs.items()})
                specific_answer["jev_confidence"] = conf
                specific_answer["family"] = [km[k]["id"] for k in family]
                # The reader named a kind and Jev, short of confident, picked the other kind:
                # that is not an answer to the request. "أعطني حديثا يثبت أن الأرض مسطحة" - a
                # Reference Framework test case - came back once with 88:20 as "tentative". A
                # confident pick of the other kind is kept: "حديث لا إكراه في الدين" is a verse.
                wanted = cands[0].get("wanted_kind") if cands else None
                if wanted and rec.get("kind") != wanted and verdict != "confident":
                    specific_answer = None
                elif cands and cands[0].get("query_language") == "ar" and not _quote_ok(query, rec):
                    specific_answer = None

        # A broad description that still pointed clearly at one text gets that text.
        if specific_answer and (specific_answer["verdict"] == "confident" or not topic_pool):
            return specific_answer

        if topic_pool:
            scored = [(c, float(r2.answers[f"t{i}"].noul)) for i, c in enumerate(topic_pool)]
            relevant = _dedupe([(c, p) for c, p in scored if p >= TOPIC_MIN_REL])
            if relevant:
                relevant.sort(key=lambda cp: (_GRADE_ORDER.get(cp[0].get("severity") or
                                                               "unknown", 1), -cp[1]))
                out = _result("topic", None, None, None, specific, rounds, len(cands),
                              len(groups))
                out["topic"] = [{"record": c, "relevance": p} for c, p in relevant[:TOPIC_MAX]]
                return out

        if specific_answer:
            return specific_answer
        return _result("no_match", None, 1.0, None, specific, rounds, len(cands), len(groups))
    finally:
        if own:
            await client.aclose()


async def _ruling(client, query, cands, kind, p, specific, n_groups):
    """A ruling question: the texts that address the matter, sound before weak, and a referral.
    Never a ruling: the reader gets the sources' words and where to ask."""
    from typesafe_sdk import Noul
    # Both kinds are judged: the evidence on a ruling starts with the Qur'an, and a pool ranked
    # by score alone held 24 hadith for "هل يجوز أفطر في رمضان إذا كنت مسافر؟" while 2:184,
    # which states the travel concession, sat lower (judge-style test, 2026-10-06).
    if cands and cands[0].get("wanted_kind"):
        pool = _topic_pool(cands)
    else:
        half = TOPIC_K // 2
        pool = [c for c in cands if c.get("kind") == "ayah"][:half] + \
            _topic_pool([c for c in cands if c.get("kind") == "hadith"])[:half]
    relevant = []
    if pool:
        questions = {f"t{i}": Noul(instructions=_judge(RULING_RELEVANCE_INSTRUCTIONS, c))
                     for i, c in enumerate(pool)}
        r = await client.system_one(state={"description": query}, questions=questions,
                                    model=MODEL)
        scored = [(c, float(r.answers[f"t{i}"].noul)) for i, c in enumerate(pool)]
        relevant = _dedupe([(c, s) for c, s in scored if s >= TOPIC_MIN_REL])
        relevant.sort(key=lambda cs: (_GRADE_ORDER.get(cs[0].get("severity") or "unknown", 1),
                                      -cs[1]))
    out = _result("ruling", None, None, None, specific, 2 if pool else 1, len(cands), n_groups)
    out["topic"] = [{"record": c, "relevance": s} for c, s in relevant[:TOPIC_MAX]]
    out["ruling"] = {"kind": kind, "probability": round(p, 3), "fiqh_url": fiqh_url(query)}
    return out


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
        "ruling": None,
        "jev_confidence": None,
        "family": [],
        "topic": [],
        "net": net,
        "groups": groups,
    }


def run_sync(query, candidates, **kw):
    return asyncio.run(run(query, candidates, **kw))
