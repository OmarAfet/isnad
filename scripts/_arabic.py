"""Arabic text handling for Isnad.

Two separate jobs, deliberately kept apart:
  * display  — always the original text, diacritics intact, nothing removed;
  * matching — a folded form that hides orthographic variation.

The sanad/matn split reports positions in the ORIGINAL string, so folding keeps a
character-for-character offset map back to it.

Note on patterns: every regex below is written in FOLDED space. Folding maps ى to ي, so the
Prophet's formula appears as "صلي الله عليه وسلم", not "صلى". Writing the patterns in unfolded
space matches nothing at all — measured: 0 hits in 34,532 hadiths.
"""
import re

# Diacritics, tatweel, Quranic annotation marks, and the bidi controls this corpus sprinkles
# around quote marks. All are invisible to a reader and must not reach a matcher.
INVISIBLE = set(
    "ًٌٍَُِّْٕٖٓٔٗ"
    "ٰٜٟ٘ٙٚٛٝٞـ"
    "ۖۗۘۙۚۛۜ۝۞۟"
    "ۣ۠ۡۢۤۥۦۧۨ۩۪ۭ۫۬"
    "‎‏؜​‌‍﻿"
)

_FOLD = str.maketrans({
    "آ": "ا", "أ": "ا", "إ": "ا", "ٱ": "ا",  # آأإٱ -> ا
    "ى": "ي",                                                               # ى -> ي
    "ؤ": "و",                                                               # ؤ -> و
    "ئ": "ي",                                                               # ئ -> ي
    "ة": "ه",                                                               # ة -> ه
    "ی": "ي", "ک": "ك",                                           # Persian ی ک
})

QUOTES = frozenset(chr(c) for c in (0x22, 0x27, 0x201C, 0x201D, 0x00AB, 0x00BB, 0x2018, 0x2019))


def strip_with_map(s):
    """Drop invisible marks. Return (stripped, offsets) where offsets[i] is the index of
    stripped[i] inside the original s."""
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch in INVISIBLE:
            continue
        out.append(ch)
        idx.append(i)
    return "".join(out), idx


def fold(s):
    """Orthographic folding, strictly one character in and one out, so any index into the result
    still indexes the input."""
    return s.translate(_FOLD)


_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^ء-ي٠-٩a-zA-Z0-9\s]")


def normalize(s):
    """Full normalization for matching and embedding. Offsets are NOT preserved."""
    stripped, _ = strip_with_map(s or "")
    return _WS.sub(" ", _PUNCT.sub(" ", fold(stripped))).strip()


# ---------- sanad / matn ----------
P_PROPHET = r"(?:صلي\s+الله\s+عليه\s+و\s*سلم(?:\s+و\s*علي\s+اله\s+و\s*صحبه)?|عليه\s+الصلاه\s+و\s*السلام)"
_SPEECH_WORDS = r"(?:فقال|قال|قالت|قالوا|يقول|تقول|يقولون|حدث)"
# Arabic letters are word characters, so \b never fires between them. Anchor explicitly or the
# verb matches inside an unrelated word: "سال" hit "فسأله" and cut the matn mid-word.
P_SPEECH = r"(?:(?<=\s)|(?<=^))" + _SPEECH_WORDS + r"(?=\s|[:،\.\"\u200f]|$)"
P_TITLE = r"(?:رسول\s+الله|النبي|نبي\s+الله)"
P_TRANS = r"(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|سمعت|قال\s+لي|ثنا)"

RX_PROPHET_SPEECH = re.compile(
    P_PROPHET + r"\s*[،:,\.]?\s*(?:انه\s+|انها\s+|ثم\s+)?" + P_SPEECH + r"\s*[:،]?\s*")
RX_AN_PROPHET = re.compile(r"(?:\bان|\bانه)\s+(?:كان\s+)?" + P_TITLE)
RX_TRANS = re.compile(P_TRANS)
RX_SPEECH_COLON = re.compile(P_SPEECH + r"\s*[:،]\s*")
RX_SPEECH_ANY = re.compile(P_SPEECH + r"\s*[:،]?\s*")
# A speech verb that only introduces the next transmitter ("قال حدثنا فلان") is still sanad.
RX_NEXT_IS_TRANS = re.compile(r"^\s*(?:" + P_TRANS + r"|عن\s|ان\s|انه\s)")

MIN_MATN = 12   # normalized characters; below this the cut landed inside the matn's tail


def _first_quote(folded):
    for i, ch in enumerate(folded):
        if ch in QUOTES:
            return i
    return -1


def split_sanad_matn(text):
    """Return (sanad, matn, rule). Both halves keep their original diacritics."""
    if not text or not text.strip():
        return "", "", "empty"
    stripped, offsets = strip_with_map(text)
    folded = fold(stripped)
    n = len(folded)

    def finish(cut, rule):
        if cut is None or cut <= 0 or cut >= len(offsets):
            return None
        o = offsets[cut]
        sanad, matn = text[:o].strip(), text[o:].strip()
        if len(normalize(matn)) < MIN_MATN:
            return None
        return sanad, matn, rule

    # 1. "… أن رسول الله صلى الله عليه وسلم قال: ‹matn›" — the most precise anchor there is.
    m = RX_PROPHET_SPEECH.search(folded)
    if m:
        r = finish(m.end(), "prophet_speech")
        if r:
            return r

    # 2. The editions wrap most matns in quote marks. Measured: present in 56–70% of each
    #    collection, so it is the strongest fallback available.
    q = _first_quote(folded)
    if q != -1:
        r = finish(q, "quote")
        if r:
            return r

    # 3. Action report: the matn itself opens with "أن رسول الله ﷺ …", so cut before it.
    m = RX_AN_PROPHET.search(folded)
    if m:
        r = finish(m.start(), "an_prophet")
        if r:
            return r

    # 4. No Prophet formula and no quotes — usually a Companion's words. Walk the speech verbs
    #    backwards and take the last one that does NOT merely introduce the next transmitter;
    #    "قال حدثنا فلان" is still chain, "قال: ‹words›" is the matn.
    cands = [m for m in RX_SPEECH_ANY.finditer(folded) if m.end() < n * 0.85]
    for m in cands:
        if RX_NEXT_IS_TRANS.match(folded[m.end():m.end() + 14]):
            continue
        r = finish(m.end(), "after_chain")
        if r:
            return r

    return "", text.strip(), "unsplit"


# ---------- display cleaning ----------
# The editions embed bidi controls around their quote marks, which render as stray marks and
# confuse copy-paste. Clean only the invisibles and the edges; never touch the letters.
_EDGE = None


def clean_display(s):
    """Tidy text for display: drop bidi controls, collapse whitespace, strip the quote and
    full-stop artifacts the editions leave at the edges. Letters and internal punctuation are
    left exactly as they are."""
    if not s:
        return ""
    out = "".join(ch for ch in s if ch not in ("‎", "‏", "؜", "​", "﻿"))
    out = _WS.sub(" ", out).strip()
    # Repeatedly peel edge noise: quote marks, full stops, commas, spaces.
    noise = set(QUOTES) | {".", "،", ",", " ", "؛", ";"}
    while out and out[0] in noise:
        out = out[1:]
    while out and out[-1] in noise:
        out = out[:-1]
    return out.strip()
