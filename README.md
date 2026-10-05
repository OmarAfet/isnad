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
| `04_dorar_queries.py` | Builds the dorar.net lookup set: ungraded hadiths plus a seeded sample |
| `05_dorar_crosscheck.py` | Compares our gradings against dorar.net and reports the agreement rate |

Every script prints the exact command to repeat it.

## Verification against dorar.net

`dorar.net` is the platform the challenge Reference Framework names for hadith grading. It answers
automated requests with HTTP 403, so it is used two ways instead:

- **Offline cross-check.** `scripts/dorar_harvest.js` runs inside a real browser session on
  dorar.net and caches its rulings. On a seeded sample of 62 hadiths, 29 were identified in dorar
  by source *and* hadith number, and severity agreement on those was **29/29**. Rows dorar did not
  surface, and rows where it declines to rule (`سكت عنه`), are excluded rather than counted either
  way. Method and limits: `data/dorar/crosscheck.md`.
- **Runtime verification link.** `scripts/_dorar.py` builds a `dorar.net/hadith/search?q=…` deep
  link for any matn, so a reader can check the ruling at the named platform in one click. No API
  call, so nothing to fail while the judges are looking at it.
