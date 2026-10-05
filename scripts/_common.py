"""Shared helpers for the Isnad corpus pipeline. Stdlib only, on purpose: the judges must be able
to clone the repo and rebuild the corpus with no API key and no paid service."""
import json, os, re, ssl, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CORPUS = os.path.join(ROOT, "data", "corpus")

CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0"

# Six collections. Bukhari and Muslim carry no per-hadith grade because inclusion in a Sahih
# collection IS the grading; the four Sunan carry explicit named-muhaddith rulings.
# "short" is the compiler's name, used inside sentences ("أخرجه البخاري في صحيحه"); "ar" is the
# full title used as a citation label.
HADITH_BOOKS = {
    "bukhari":  {"ar": "صحيح البخاري", "short": "البخاري",   "grade_basis": "inherent"},
    "muslim":   {"ar": "صحيح مسلم",     "short": "مسلم",      "grade_basis": "inherent"},
    "abudawud": {"ar": "سنن أبي داود",  "short": "أبو داود",  "grade_basis": "cited"},
    "tirmidhi": {"ar": "سنن الترمذي",   "short": "الترمذي",   "grade_basis": "cited"},
    "nasai":    {"ar": "سنن النسائي",   "short": "النسائي",   "grade_basis": "cited"},
    "ibnmajah": {"ar": "سنن ابن ماجه",  "short": "ابن ماجه",  "grade_basis": "cited"},
}

# Two Quran editions, for two different jobs.
#   display  — King Fahd Complex Uthmani, the edition the Reference Framework names.
#   matching — the simple (imlaa'i) orthography. The Uthmani text writes الْعَٰلَمِينَ with a
#              superscript alef, which normalizes to العلمين, but a user types العالمين and would
#              never match it. Modern spelling is what people actually enter.
QURAN_EDITION = "ara-quranuthmanihaf"
QURAN_MATCH_EDITION = "ara-quransimple"


def say(msg):
    print(msg, flush=True)


def ran(cmd):
    """Record the exact command, so any result here can be reproduced by hand."""
    say(f"RAN: {cmd}")


def _ssl_context():
    """python.org builds on macOS ship without root certificates, so urllib fails on every HTTPS
    request. Use certifi when it happens to be installed; otherwise fall back to curl below."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def fetch(url, dest, retries=3):
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        say(f"  cached  {os.path.basename(dest)} ({os.path.getsize(dest)/1e6:.1f} MB)")
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    ctx = _ssl_context()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "isnad-corpus/1.0"})
            kw = {"timeout": 120}
            if ctx is not None:
                kw["context"] = ctx
            with urllib.request.urlopen(req, **kw) as r, open(dest, "wb") as f:
                f.write(r.read())
            say(f"  fetched {os.path.basename(dest)} ({os.path.getsize(dest)/1e6:.1f} MB)")
            return dest
        except Exception as e:
            last = e
            if isinstance(e, (ssl.SSLError, urllib.error.URLError)) and "CERTIFICATE" in str(e):
                break          # no point retrying a trust-store problem
            say(f"  retry {i+1}/{retries} after {e}")
            time.sleep(2 * (i + 1))

    # Fallback: curl carries the OS trust store, so it works where the Python build does not.
    cmd = ["curl", "-sSL", "--fail", "--max-time", "180", "-o", dest, url]
    say(f"  urllib failed ({type(last).__name__}); falling back to curl")
    ran(" ".join(cmd))
    subprocess.run(cmd, check=True)
    say(f"  fetched {os.path.basename(dest)} ({os.path.getsize(dest)/1e6:.1f} MB) via curl")
    return dest


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    say(f"  wrote   {os.path.relpath(path, ROOT)} ({os.path.getsize(path)/1e6:.1f} MB)")


# ---------- Arabic normalization ----------
_HARAKAT = re.compile(r"[ً-ٰٟۖ-ۭـ]")
_ALEF = re.compile(r"[آأإٱ]")       # آ أ إ ٱ -> ا
_YA = re.compile(r"ى")                              # ى -> ي
_WAW_HAMZA = re.compile(r"ؤ")                       # ؤ -> و
_YA_HAMZA = re.compile(r"ئ")                        # ئ -> ي
_PUNCT = re.compile(r"[^ء-ي٠-٩a-zA-Z0-9\s]")
_WS = re.compile(r"\s+")


def strip_diacritics(s):
    return _HARAKAT.sub("", s or "")


def normalize_ar(s):
    """Fold the orthographic variation that makes two spellings of the same word look different.
    Used only for matching. Display always uses the original text."""
    s = strip_diacritics(s)
    s = _ALEF.sub("ا", s)
    s = _YA.sub("ي", s)
    s = _WAW_HAMZA.sub("و", s)
    s = _YA_HAMZA.sub("ي", s)
    s = s.replace("ة", "ه")   # ة -> ه
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()
