"""Shown Qur'an translations from QuranEnc.com, with their translators' footnotes.

WHY. The Reference Framework (p. 3) asks for approved translations for every language used: the
King Fahd Complex's, or those listed on quranpedia.net. Three of the eight shown came from
tanzil.net editions outside that group (Urdu: Maududi; Turkish: Golpinarli; Russian: Abu Adel),
and the French one was credited to "Islamic Foundation" where its publisher names Noor
International Center (Dr. Nabil Radwan). Omar's decision (2026-10-06): "show approved and trusted
ones". QuranEnc.com (موسوعة القرآن الكريم), developed under the Rowwad Translation Center with the
Islamic Content Service Association, publishes reviewed translations with a public API and
version numbers, so all eight shown translations now come from it, one source, cited.

QuranEnc's terms for republishing (every translation page): no addition or deletion; name the
publisher and the source (QuranEnc.com); state the version; keep the version information. So the
text is stored as published, the footnotes are kept beside it, and the version or the fetch date
travels with each translation to the page.

Search is unchanged: the language surfaces that queries are matched against stay as built
(scripts/06b_embed_surfaces.py). A translation is a reading aid; Isnad never translates.

Writes data/quranenc/<key>.json (not in git: the texts are QuranEnc's to publish), then updates
data/index/display.db (translations of quran:* rows, footnotes in table `tnotes`) and the "quran"
section of data/translators.json.

Usage: python scripts/09_quranenc.py [--fetch-only | --apply-only]
"""
import json, os, sqlite3, ssl, sys, time, urllib.request
from datetime import date

# python.org builds on macOS ship without root certificates; certifi's bundle makes HTTPS work.
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "data", "quranenc")
DB = os.path.join(ROOT, "data", "index", "display.db")
TRANSLATORS = os.path.join(ROOT, "data", "translators.json")
API = "https://quranenc.com/api/v1"
UA = {"User-Agent": "Isnad/1.0 (IslamicAICh 2026; https://github.com/OmarAfet/isnad)"}

# Language -> QuranEnc key, and the credit as QuranEnc words it (title and description, read from
# its API and its Arabic pages on 2026-10-06).
KEYS = {
    "en": ("english_hilali_khan", "Taqi-ud-Din al-Hilali and Muhammad Muhsin Khan"),
    "ur": ("urdu_junagarhi", "Muhammad Ibrahim Junagarhi"),
    "tr": ("turkish_rwwad", "Rowwad Translation Center"),
    "ru": ("russian_rwwad", "Rowwad Translation Center"),
    "fr": ("french_montada", "Noor International Center"),
    "ta": ("tamil_baqavi", "Abdulhamid Al-Baqawi"),
    "bn": ("bengali_zakaria", "Abu Bakr Zakaria"),
    "id": ("indonesian_complex", "Indonesian Ministry of Religious Affairs (the Complex edition)"),
}
SURAHS = 114


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60,
                                        context=CTX) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def fetch():
    os.makedirs(OUT, exist_ok=True)
    listed = {t["key"]: t for t in get(f"{API}/translations/list").get("translations", [])}
    for lang, (key, credit) in KEYS.items():
        path = os.path.join(OUT, f"{key}.json")
        if os.path.exists(path):
            print(f"  have  {key}")
            continue
        verses = {}
        for s in range(1, SURAHS + 1):
            for v in get(f"{API}/translation/sura/{key}/{s}")["result"]:
                verses[f"{int(v['sura'])}:{int(v['aya'])}"] = {
                    "t": v.get("translation") or "", "n": v.get("footnotes") or ""}
            time.sleep(0.15)
        meta = listed.get(key, {})
        json.dump({"key": key, "lang": lang, "credit": credit,
                   "version": meta.get("version"), "title": meta.get("title"),
                   "fetched": date.today().isoformat(), "verses": verses},
                  open(path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  fetched {key}: {len(verses)} verses, version {meta.get('version') or '-'}")


def apply():
    db = sqlite3.connect(DB)
    db.execute("CREATE TABLE IF NOT EXISTS tnotes (id TEXT, lang TEXT, notes TEXT, "
               "PRIMARY KEY (id, lang))")
    data = {lang: json.load(open(os.path.join(OUT, f"{key}.json"), encoding="utf-8"))
            for lang, (key, _) in KEYS.items()}
    rows = db.execute("SELECT id, translations FROM display WHERE id LIKE 'quran:%'").fetchall()
    changed = missing = 0
    for rid, tj in rows:
        tr = json.loads(tj or "{}")
        sa = rid.split(":", 1)[1]
        for lang, d in data.items():
            v = d["verses"].get(sa)
            if not v or not v["t"]:
                missing += 1
                tr.pop(lang, None)        # never leave the old edition under the new credit
                continue
            tr[lang] = v["t"]
            if v["n"]:
                db.execute("INSERT OR REPLACE INTO tnotes VALUES (?, ?, ?)", (rid, lang, v["n"]))
        db.execute("UPDATE display SET translations=? WHERE id=?",
                   (json.dumps(tr, ensure_ascii=False), rid))
        changed += 1
    db.commit()
    db.execute("VACUUM")
    tj = json.load(open(TRANSLATORS, encoding="utf-8"))
    for lang, d in data.items():
        tj["quran"][lang] = {"edition": d["key"], "author": d["credit"],
                             "source": f"https://quranenc.com/en/browse/{d['key']}",
                             "publisher": "QuranEnc.com", "version": d["version"],
                             "fetched": d["fetched"]}
    json.dump(tj, open(TRANSLATORS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    notes = db.execute("SELECT COUNT(*) FROM tnotes").fetchone()[0]
    print(f"  display.db: {changed} verses updated, {missing} verse-languages without text, "
          f"{notes} footnote entries; translators.json quran section rewritten")


if __name__ == "__main__":
    print("RAN: python scripts/09_quranenc.py " + " ".join(sys.argv[1:]))
    if "--apply-only" not in sys.argv:
        fetch()
    if "--fetch-only" not in sys.argv:
        apply()
