# إسناد — Isnad

Describe a verse or hadith from memory, in any language. Isnad returns the exact text, its source,
its grading, and a calibrated confidence — or it says plainly that it found no matching text.

Isnad **selects from verified texts. It never generates text.** It does not rule on authenticity;
it relays the ruling of the specialists and names them.

IslamicAICh 2026 — track 04, knowledge and verification tools. Team إسناد (#450).

## Corpus

Built by `scripts/`, stdlib only, no API keys.

| Script | Does |
|---|---|
| `01_fetch.py` | Downloads Quran and six hadith collections to `data/raw/` |
| `02_normalize.py` | Unifies records, splits sanad from matn, normalizes Arabic for matching |
| `03_report.py` | Corpus quality report — split coverage per rule, grade coverage, samples |

Every script prints the exact command to repeat it.
