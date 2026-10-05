"""Query language detection.

Deliberately not a model. The job is only to pick which language surfaces to search, a wrong
guess costs recall in one language rather than correctness, and a dependency that loads a model
to answer a question a character range already answers is not worth its weight on a free tier.

Script settles Arabic, Urdu, Bengali, Tamil and Russian. Urdu needs care: it uses the Arabic
script, so it is identified by the letters Arabic does not have.
"""

# Letters present in Urdu and absent from Arabic.
URDU_ONLY = set("ٹڈڑھہۃیےںچژگک")

RANGES = (
    ("bn", 0x0980, 0x09FF),
    ("ta", 0x0B80, 0x0BFF),
    ("ru", 0x0400, 0x04FF),
)

# Function words, which separate these four far more reliably than content words do.
STOPWORDS = {
    "en": {"the", "of", "a", "an", "about", "is", "that", "which", "and", "in", "on", "to",
           "hadith", "verse", "ayah", "quran", "prophet", "says", "said", "where", "what"},
    "fr": {"le", "la", "les", "de", "des", "du", "un", "une", "qui", "que", "est", "sur",
           "dans", "pour", "hadith", "verset", "coran", "prophete", "dit"},
    "tr": {"ve", "bir", "ile", "icin", "bu", "ne", "olan", "daha", "gibi", "hadis", "ayet",
           "kuran", "peygamber", "dedi", "hangi"},
    "id": {"yang", "dan", "dari", "untuk", "ini", "itu", "dengan", "pada", "adalah", "hadits",
           "hadis", "ayat", "quran", "nabi", "tentang", "apa"},
}


def detect(text):
    """Return a language code. Defaults to Arabic for Arabic script and English for Latin."""
    t = text or ""
    if not t.strip():
        return "ar"

    counts = {}
    arabic = urdu_hits = latin = 0
    for ch in t:
        o = ord(ch)
        if ch in URDU_ONLY:
            urdu_hits += 1
            arabic += 1
            continue
        if 0x0600 <= o <= 0x06FF:
            arabic += 1
            continue
        if ("a" <= ch.lower() <= "z"):
            latin += 1
            continue
        for code, lo, hi in RANGES:
            if lo <= o <= hi:
                counts[code] = counts.get(code, 0) + 1
                break

    if counts:
        top = max(counts, key=counts.get)
        if counts[top] >= max(arabic, latin):
            return top
    if arabic and arabic >= latin:
        return "ur" if urdu_hits >= 2 else "ar"
    if latin:
        words = {w for w in "".join(c.lower() if c.isalnum() else " " for c in t).split()}
        scores = {lg: len(words & sw) for lg, sw in STOPWORDS.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "en"
    return "ar"
