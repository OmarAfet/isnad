"""Shared helpers for the Isnad corpus pipeline. Stdlib only, on purpose: the judges must be able
to clone the repo and rebuild the corpus with no API key and no paid service."""
import json, os, re, ssl, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
CORPUS = os.path.join(ROOT, "data", "corpus")

CDN = "https://cdn.jsdelivr.net/gh/fawazahmed0"
# jsDelivr starts answering 403 after a few dozen requests in quick succession. These mirror the
# same repositories, so a blocked or timed-out file is retried elsewhere rather than failing the
# build.
CDN_MIRRORS = [
    "https://cdn.statically.io/gh/fawazahmed0",
    "https://raw.githubusercontent.com/fawazahmed0",
]

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

# ---------------------------------------------------------------------------
# Translations as a MATCHING SURFACE ONLY.
#
# Isnad never translates scripture itself. The Reference Framework requires a translation to
# preserve the legal sense of its terms, and the binding output standard forbids presenting
# generated text as scripture - machine-translating a hadith would be generating it, which is the
# one thing this product refuses to do.
#
# So published translations are indexed so that a non-Arabic description can FIND the right
# record, and the answer shown is always the Arabic original, with the translation displayed
# beneath it and credited to its translator. The choice of translation therefore affects recall,
# never the correctness of the answer.
#
# Quran: Indonesian is the King Fahd Complex's own translation, and English is Hilali & Muhsin
# Khan, the Complex's Noble Qur'an - both named by the framework ("طبعة مجمع الملك فهد أو ترجماته").
# The rest are established published translations, used for matching and attributed on display.
QURAN_TRANSLATIONS = {
    "en": "eng-muhammadtaqiudd",     # Hilali & Muhsin Khan, the Noble Qur'an (King Fahd Complex)
    "id": "ind-kingfahdcomplex",     # King Fahd Complex
    "ur": "urd-abulaalamaududi",     # Abul A'la Maududi
    "tr": "tur-abdulbakigolpin",     # Abdulbaki Golpinarli
    "bn": "ben-abubakrzakaria",      # Abu Bakr Zakaria
    "fr": "fra-islamicfoundati",     # Islamic Foundation
    "ru": "rus-abuadel",             # Abu Adel
    "ta": "tam-abdulhameedbaqa",     # Abdulhameed Baqavi
}

# Hadith translation prefixes. Coverage is uneven and that is recorded rather than smoothed over:
# French lacks Tirmidhi, Russian has only three collections, Tamil only two. A record with no
# translation in a language simply has no surface in that language.
HADITH_LANG_PREFIX = {
    "en": "eng", "bn": "ben", "fr": "fra", "id": "ind",
    "ru": "rus", "ta": "tam", "tr": "tur", "ur": "urd",
}
HADITH_LANG_COVERAGE = {
    "en": ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah"],
    "bn": ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah"],
    "id": ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah"],
    "tr": ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah"],
    "ur": ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah"],
    "fr": ["bukhari", "muslim", "abudawud", "nasai", "ibnmajah"],
    "ru": ["bukhari", "muslim", "abudawud"],
    "ta": ["bukhari", "muslim"],
}
LANGS = list(HADITH_LANG_PREFIX)

LANG_NAME_AR = {
    "ar": "العربية", "en": "الإنجليزية", "ur": "الأردية", "tr": "التركية",
    "id": "الإندونيسية", "bn": "البنغالية", "fr": "الفرنسية", "ru": "الروسية",
    "ta": "التاميلية",
}


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


def mirror_urls(url):
    """The same path on each mirror. raw.githubusercontent needs the branch in place of @1."""
    out = []
    for m in CDN_MIRRORS:
        u = url.replace(CDN, m)
        if "raw.githubusercontent" in m:
            u = u.replace("@1/", "/1/")
        out.append(u)
    return out


def fetch(url, dest, retries=3, required=True):
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
    # Then the mirrors, for files jsDelivr is rate-limiting.
    for attempt_url in [url] + mirror_urls(url):
        cmd = ["curl", "-sSL", "--fail", "--max-time", "120", "-o", dest, attempt_url]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 1000:
            host = attempt_url.split("/")[2]
            say(f"  fetched {os.path.basename(dest)} "
                f"({os.path.getsize(dest)/1e6:.1f} MB) via curl @ {host}")
            return dest
        if os.path.exists(dest):
            os.remove(dest)

    if required:
        raise RuntimeError(f"could not fetch {url} from any mirror (last urllib error: {last})")
    say(f"  MISSING {os.path.basename(dest)} - not available from any mirror; "
        f"this language keeps no surface for it")
    return None


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
