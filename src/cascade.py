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

from decide import HIGH, LOW, NO_MATCH, message_ar             # noqa: E402
from _arabic import normalize                                   # noqa: E402
from _dorar import fiqh_url, refer_url                          # noqa: E402
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
# NO EXAMPLE SENTENCES. Every option below, and every other instruction to Jev, is described in
# words of its own. Earlier versions quoted example requests, and several were the very questions
# the tests and the Reference Framework use ("لماذا يعبد المسلمون الكعبة", "الدين المعاملة"), which
# made the measured accuracy on them partly a memory of the prompt. Removed 2026-10-06 at Omar's
# request ("remove them and re-measure honestly"); eval/heldout2.py measures before and after.
ASK_OPTIONS = {
    "find_text": (
        "To find a specific Qur'anic verse or hadith, its exact wording, its source, or whether a "
        "hadith is authentic and what its grade is; or to find the verses or hadith on a "
        "subject."),
    "general_ruling": (
        "The Islamic ruling on a matter in general: whether something is permitted, forbidden or "
        "obligatory, asked about people in general rather than the asker's own situation."),
    "personal_case": (
        "A ruling on the asker's own situation or circumstances, usually asked in the first "
        "person about what they did or may do, so that the answer depends on the facts of their "
        "case."),
    # QUESTIONS ABOUT ISLAM. The Reference Framework's content-safety test cases are mostly of this
    # kind ("لماذا يعبد المسلمون الكعبة؟", "هل الإسلام انتشر بالسيف؟", "ما معنى التوحيد"), and with
    # three classes every one of them was read as a ruling question: the reader got "إسناد ما يفتي"
    # and a fiqh-encyclopedia search for "لماذا يعبد المسلمون الكعبة" (judge test, 2026-10-06).
    "question": (
        "A question about Islam itself: a belief, the meaning of a term or concept, an event in "
        "its history, the reason behind a teaching, or an objection or misconception about "
        "Islam. Not a ruling on whether an act is permitted, and not a search for a text."),
    # Out of scope by the Reference Framework: "الحكم على الأشخاص أو الجماعات". "هل الشيعة كفار" and
    # "هل ابن تيمية مبتدع" were answered as ruling questions, with a fiqh search for their words.
    "judge_people": (
        "A judgement on a specific person, sect or group of people: whether they are believers, "
        "disbelievers, innovators or astray, or bound for Paradise or Hell."),
}
# "what is the capital of France" is a question too, and read as one about Islam it was sent to an
# Islam Q&A book (local battery, 2026-10-06). An "unrelated" option in the Choice above fixed it but
# took probability from real requests: "verse about bees" (16:68) scored 0.61-0.64 unrelated
# (eval/ask_probe2.py). So the question path alone asks a separate yes/no, which competes with
# nothing.
ISLAMIC_INSTRUCTIONS = (
    "Is this request about Islam, the Qur'an, the hadith, the Prophet, or Muslims' beliefs and "
    "practice in any way?"
)
ISLAMIC_THRESHOLD = 0.50
# P(general_ruling) + P(personal_case) [+ P(question) for a question]. Measured (eval/ask_probe.py,
# 3 runs each): ruling questions 0.97-0.99; "ايه عن بر الوالدين" 0.52-0.56 and once over 0.60 in a
# live run, which sent a request for verses down the ruling path. 0.75 keeps the margin on both
# sides. With five classes (eval/ask_probe2.py, 48 descriptions x 2 runs): questions 0.98-1.00,
# judging people 1.00, find_text and ruling as before.
RULING_THRESHOLD = 0.75
JUDGE_THRESHOLD = 0.50
# The question path needs the form of a question. Bare sayings read as statements about Islam:
# "الدين المعاملة", a saying that is not a hadith, scored P(question) 0.64-0.71, and its answer is
# "not found in the books", not a list of texts about religion.
QUESTION_WORDS = {"هل", "لماذا", "لماذ", "ليش", "ليه", "ما", "ماذا", "ماهو", "ماهي", "مامعني",
                  "كيف", "متي", "اين", "وين", "من", "مين", "وش", "ايش", "شو", "كم", "ترجم",
                  "اشرح", "عرف", "فسر", "وضح", "why", "what", "how", "is", "are", "does", "do",
                  "did", "can", "who", "when", "where", "which", "explain", "define", "translate"}
# WHERE TO SEND A QUESTION. Each option is a reference the Reference Framework approves for that
# kind of content (p. 3): objections and common questions, creed, fiqh, history, terms.
REFER_INSTRUCTIONS = "Which kind of reference would answer this question about Islam best?"
REFER_OPTIONS = {
    "objection": ("A common question, objection or misconception about Islam, the Prophet or the "
                  "Qur'an, as a non-Muslim or a doubter would ask it."),
    "creed": "A point of Islamic creed: belief about Allah, His attributes, prophets, the unseen.",
    "fiqh": "Islamic law: rulings, worship, transactions, or why scholars differ on rulings.",
    "history": "The Prophet's life or Islamic history: an event, a date, a person's story.",
    "term": "The meaning or translation of an Islamic term or concept.",
}
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
QUESTION_RELEVANCE_INSTRUCTIONS = (
    "The user in `description` asks a question about Islam. Here is a {kind}: \"{text}\". Does "
    "this text speak directly to that question, for example by stating the belief, the reason or "
    "the event it asks about, or by correcting the misconception in it? Answer no if the text "
    "only shares a word with the question or is about something else."
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
BROAD_SINGLE = 0.90       # a broad description returns one text only above this (see below)
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
    "or a root with the description, uses that word or a word from its root in another sense, or "
    "says nothing about the subject."
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
# A QUOTED SAYING IS NOT A SUBJECT. "الدين المعاملة", a saying that is not a hadith, is short and
# reads as broad, so it went to topic mode, where "الدين" was read as الدَّين (debt) and four hadith
# on debts were listed as "texts about this" (judge test, 2026-10-06). A reader who quotes words
# asks whether they are a verse or hadith; the answer is that text, or "not found", never a list.
SAYING_INSTRUCTIONS = (
    "Is the user quoting the words of one specific saying as they remember them, to find out "
    "whether it is a verse or a hadith and where it is, rather than naming a subject to find "
    "texts about?"
)
SAYING_THRESHOLD = 0.60


# A QUOTED SAYING MUST BE IN THE ANSWER. Asked "اختلاف أمتي رحمة" - a saying that is not a sound
# hadith - Jev once answered 30:22 "واختلاف ألسنتكم وألوانكم" at 0.71, on the shared word. When
# the query is a bare Arabic quotation (no "عن", "اللي", "يقول"...: those introduce a paraphrase),
# at least half of its content words, light-stemmed, must be in the chosen text's own words, or
# the answer is "not found". Measured (2026-10-06, 20 right answers): bare quotations 0.62-1.00;
# the wrong ones 0.00-0.33. Paraphrases reach 0.40 and are not checked.
QUOTE_MIN = 0.5
DESCRIPTION_WORDS = {"عن", "اللي", "التي", "الذي", "فيها", "فيه", "يقول", "تقول", "يتكلم",
                     "تتكلم", "معناه", "معني",
                     # A request about a text, not words from it: "فسر لي آية الكرسي".
                     "فسر", "اشرح", "وضح", "تفسير", "شرح", "ترجم", "ترجمه"}
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
    found = sum(1 for w in content if w in text)
    # A two-word saying must be there whole. Half of "الدين المعاملة" is one word, and "الدِّين"
    # (religion) is spelt as "الدَّين" (debt): Ibn Majah 2425 on debts came back at 0.76 as the
    # "very weak hadith" behind a saying it does not contain (judge test, 2026-10-06).
    if len(content) <= 2:
        return found == len(content)
    return found / len(content) >= QUOTE_MIN


# THE READER'S WORDING AGAINST THE SOURCE'S. A Reference Framework test case is a question that
# quotes a verse wrongly; the expected behaviour is "التنبيه على النص الصحيح بلطف، وإظهار السورة
# والآية وعدم البناء على النص المحرف". Isnad already shows the right text; this says where the
# reader's words differ: "قل هو الله واحد" -> 112:1 says أحد. Only for a quotation (no describing
# words, two or more quoted words, at least half of them in the text), never for a paraphrase,
# and a word counts as found if any listed copy of the report has it. The article and the
# prepositions joined to it are ignored; a conjunction alone is not stripped, or "واحد" would
# pass as "احد".
_ARTICLE = ("وبال", "فبال", "وال", "بال", "فال", "كال", "لل", "ال")


def _bare(w):
    for p in _ARTICLE:
        if w.startswith(p) and len(w) - len(p) >= 2:
            return w[len(p):]
    return w


def wording(query, texts):
    """Positions (in query.split()) of quoted words that are not in the source's wording, or
    None when the query is not a quotation or every word is there."""
    norm = [normalize(t) for t in query.split()]
    if any(n in DESCRIPTION_WORDS for n in norm):
        return None
    content = [(i, n) for i, n in enumerate(norm)
               if n and n not in REQUEST_WORDS and n not in FUNCTION_WORDS]
    if len(content) < 2:
        return None
    vocab = set()
    for t in texts:
        for w in ((t.get("surface") or "") + " " + normalize(t.get("matn") or "")).split():
            vocab.add(_bare(w))
    missing = [i for i, n in content if _bare(n) not in vocab]
    if not missing or (len(content) - len(missing)) / len(content) < QUOTE_MIN:
        return None
    return missing


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


class _Counting:
    """The client, counting the input tokens of every request a search makes. Jev is charged per
    input token ($0.042 per million, output free: docs.typesafe.ai/models, read 2026-10-06), so
    the cost of a search is measured, not estimated."""

    def __init__(self, client):
        self.client, self.input_tokens = client, 0

    async def system_one(self, **kw):
        r = await self.client.system_one(**kw)
        try:
            self.input_tokens += int(r.usage.input_tokens)
        except Exception:
            pass
        return r


async def run(query, candidates, client=None, net=NET, group=GROUP):
    """Return the decision, with the input tokens it used. Needs an AsyncTypeSafeClient, or makes
    its own."""
    from typesafe_sdk import AsyncTypeSafeClient
    own = client is None
    counting = _Counting(client or AsyncTypeSafeClient())
    try:
        d = await _run(query, candidates, counting, net, group)
    finally:
        if own:
            await counting.client.aclose()
    d["input_tokens"] = counting.input_tokens
    return d


async def _run(query, candidates, client, net=NET, group=GROUP):
    from typesafe_sdk import Choice, Noul

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
    questions["saying"] = Noul(instructions=SAYING_INSTRUCTIONS)
    questions["ask"] = Choice(instructions=ASK_INSTRUCTIONS, criteria=ASK_OPTIONS)
    # Asked of every request, in the same round: it only matters for a question about Islam, and
    # questions in one request run in parallel, so it adds no wait.
    questions["refer"] = Choice(instructions=REFER_INSTRUCTIONS, criteria=REFER_OPTIONS)
    questions["islamic"] = Noul(instructions=ISLAMIC_INSTRUCTIONS)

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
    # Measured (eval/saying_probe.py, 27 descriptions x 2 runs): quoted sayings 0.73-0.92,
    # subjects 0.05-0.23; 0 of 54 on the wrong side of 0.60.
    saying = float(r1.answers["saying"].noul)
    ask = {k: float(v) for k, v in (r1.answers["ask"].probabilities or {}).items()}

    rounds = 1
    p_ruling = ask.get("general_ruling", 0.0) + ask.get("personal_case", 0.0)
    names_kind = bool(cands) and cands[0].get("wanted_kind") is not None
    words = set(normalize(query).lower().replace("؟", " ").replace("?", " ").split())
    ruling_word = bool(words & RULING_WORDS)
    # A reader who names the kind of text ("حديث عن ...", "آية تثبت ...") wants texts, whatever
    # else the request reads like.
    if ask.get("judge_people", 0.0) >= JUDGE_THRESHOLD and not names_kind:
        out = _result("out_of_scope", None, None, None, specific, rounds, len(cands),
                      len(groups))
        out["scope"] = "judge_people"
        return out
    first = (normalize(query).lower().split() or [""])[0]
    is_question = "?" in query or "؟" in query or bool(words & QUESTION_WORDS)
    # Measured (eval/ask_probe2.py, 2 runs): questions about Islam 0.93-0.99, unrelated ones
    # ("what is the capital of France") 0.01-0.02. Only the question path asks it: "verse about
    # bees" scored 0.08, because the word "verse" alone does not say Qur'an to it.
    islamic = float(r1.answers["islamic"].noul)
    p_question = ask.get("question", 0.0) if is_question and \
        islamic >= ISLAMIC_THRESHOLD else 0.0
    # "هل القرآن من تأليف محمد؟" names the Qur'an as its subject, not as the kind of text it
    # wants: a request that opens with a question word is a question whatever it names.
    if p_question > p_ruling and first in QUESTION_WORDS:
        names_kind = False
    if p_ruling + p_question >= RULING_THRESHOLD and (ruling_word or not names_kind):
        if p_question > p_ruling and not ruling_word:
            refer = r1.answers["refer"].choice
            return await _ruling(client, query, candidates, "question", p_question, specific,
                                 len(groups), refer=refer if refer in REFER_OPTIONS else
                                 "objection")
        kind = ("personal" if ask.get("personal_case", 0.0) >= ask.get("general_ruling", 0.0)
                else "general")
        return await _ruling(client, query, candidates, kind, p_ruling, specific, len(groups))
    # A broad description goes to topic mode even when every group answered no_match: the
    # pick question asks for ONE text, and for "حديث عن الكذب" no single text is the one, so
    # all ten groups can rightly decline. Exiting here reported "nothing found" for a subject
    # the shortlist covered (seen 2026-10-05 once the shortlist changed; round two never ran).
    topic_pool = _topic_pool(cands) if specific < TOPIC_SPECIFIC and \
        saying < SAYING_THRESHOLD else []
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

    # A broad description that still pointed clearly at one text gets that text: "verse that
    # Jesus was not crucified" is scored broad and is 4:157 at 0.99. "Clearly" is BROAD_SINGLE,
    # not HIGH: "حديث عن الكذب" got al-Bukhari 2459 alone at 0.82 where a list belongs (production
    # smoke, 2026-10-06), as did "хадис о милосердии" (0.79-0.81) and an Indonesian subject (0.70);
    # loosely described single texts scored 0.91-1.00.
    if specific_answer and (not topic_pool or
                            (specific_answer["verdict"] == "confident" and
                             (specific_answer["confidence"] or 0) >= BROAD_SINGLE)):
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


async def _ruling(client, query, cands, kind, p, specific, n_groups, refer=None):
    """A ruling question: the texts that address the matter, sound before weak, and a referral.
    Never a ruling: the reader gets the sources' words and where to ask.

    kind "question" is a question about Islam that is not a ruling (belief, meaning, history,
    objection): the same texts-then-referral answer, judged against the question, and referred
    to the approved reference for its kind (`refer`) instead of the fiqh encyclopedia. Isnad
    writes no answer of its own in either case."""
    from typesafe_sdk import Noul
    template = QUESTION_RELEVANCE_INSTRUCTIONS if kind == "question" else \
        RULING_RELEVANCE_INSTRUCTIONS
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
        questions = {f"t{i}": Noul(instructions=_judge(template, c))
                     for i, c in enumerate(pool)}
        r = await client.system_one(state={"description": query}, questions=questions,
                                    model=MODEL)
        scored = [(c, float(r.answers[f"t{i}"].noul)) for i, c in enumerate(pool)]
        relevant = _dedupe([(c, s) for c, s in scored if s >= TOPIC_MIN_REL])
        relevant.sort(key=lambda cs: (_GRADE_ORDER.get(cs[0].get("severity") or "unknown", 1),
                                      -cs[1]))
    out = _result("question" if kind == "question" else "ruling", None, None, None, specific,
                  2 if pool else 1, len(cands), n_groups)
    out["topic"] = [{"record": c, "relevance": s} for c, s in relevant[:TOPIC_MAX]]
    if kind == "question":
        lang = cands[0].get("query_language") if cands else None
        out["refer"] = {"kind": refer, "probability": round(p, 3), "url": refer_url(refer, lang)}
    else:
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
        "refer": None,
        "scope": None,
        "jev_confidence": None,
        "family": [],
        "topic": [],
        "net": net,
        "groups": groups,
    }


def run_sync(query, candidates, **kw):
    return asyncio.run(run(query, candidates, **kw))
