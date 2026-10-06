# إسناد — Isnad

**Describe a verse or hadith from memory, in any language. Isnad returns the exact Arabic text,
its source, and the grading of named scholars, or says plainly that it found no matching text.**

- Live demo: **https://isnad-app.vercel.app** (no login)
- How it works, for specialists: https://isnad-app.vercel.app/method
- IslamicAICh 2026, track 04 (knowledge and verification tools). Team إسناد (#450).

## نظرة عامة

يتذكر الناس معنى الآية أو الحديث وينسون لفظه ومصدره، فينقلون ألفاظًا محرّفة أو أحاديث ضعيفة
وموضوعة. إسناد يأخذ وصف المستخدم بأي لغة، ويختار النص من مصادر موثقة: القرآن الكريم بطبعة مجمع
الملك فهد، والصحيحان، والسنن الأربع. يعرض النص بلفظه ومصدره ورقمه، وحكم العلماء عليه بأسمائهم.

- يختار من نصوص موجودة، ولا يكتب نصًا ولا يترجم نصًا شرعيًا من عنده.
- لا يحكم على صحة حديث، بل ينقل حكم العلماء بأسمائهم.
- لا يفتي: سؤال الحكم يُعرض معه النصوص الواردة في المسألة، ويُحال إلى أهل العلم وإلى الموسوعة الفقهية.
- إذا لم يجد نصًا مطابقًا قال ذلك صراحة.

## What it does

| The reader types | Isnad answers |
|---|---|
| A description or part of the wording: "الآية اللي فيها لا تأخذه سنة ولا نوم", "hadith about intentions" | The text, its source and number, the named gradings, and how well it matches the description |
| A wording that is not in the books: "حب الوطن من الإيمان" | "No matching text in the approved sources", and a dorar.net search link |
| A quotation with wrong words: "قل هو الله واحد" | The right text (112:1), with the reader's differing word marked |
| A subject: "ايه عن النوم", "حديث عن الكذب" | A list of the texts on it, the Qur'an first, sound before weak |
| A citation: "البقرة 255", "2:255", "البخاري 6018", "مسلم 2564", "آية الدين" | The text itself, looked up, not searched |
| A ruling question: "ما حكم الربا" | The texts on the matter, then "Isnad does not issue fatwas" and a referral |
| A question about Islam: "لماذا يعبد المسلمون الكعبة؟" | The texts that speak to it (if any), then the approved reference for that kind of question |
| A judgement on people or groups | "Outside Isnad's work", with no texts |

## How it works

```
description ──► stage 1: hybrid search over 40,389 texts ──► 120 candidates
                 (meaning: multilingual-e5-base, int8 ONNX;
                  wording: BM25 with Arabic light stemming; 9 language surfaces)
            ──► stage 2: Jev (TypeSafe) decides, in two requests
                 round 1: one Choice per group of 12 candidates, plus what is asked
                          (text / ruling / personal case / question / judging people),
                          how specific it is, whether it is a quoted saying
                 round 2: the final Choice, or relevance per text for a subject list
            ──► one text with its probability, a list, a referral, or "not found"
```

A citation ("البقرة 255") and a surah name ("سورة الإخلاص") skip both stages: they are read from
the reference itself. Every number on the screen comes from the sources; Jev only chooses.

## Sources

| What | From | Used for | Licence or terms | Date |
|---|---|---|---|---|
| Qur'an, Uthmani script, King Fahd Complex edition | [quran-api](https://github.com/fawazahmed0/quran-api) edition `ara-quranuthmanihaf` (source: qurancomplex.gov.sa) | The text shown | The Unlicense | fetched 2026-10-05 |
| Qur'an translations, 8 languages | quran-api editions (tanzil.net, quranenc.com, qurancomplex.gov.sa); translator per edition in `data/translators.json` | Search in that language; shown with the translator's name | The translators' rights; shown attributed, never altered | fetched 2026-10-05 |
| Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud, al-Tirmidhi, al-Nasa'i, Ibn Majah, with gradings | [hadith-api](https://github.com/fawazahmed0/hadith-api) | Text, reference numbers, named gradings (al-Albani, Shu'ayb al-Arna'ut, Ahmad Shakir and 5 others) | The Unlicense | fetched 2026-10-05 |
| Hadith translations, 8 languages | hadith-api editions | Search in that language; shown attributed (the source names some translators as "Unknown") | The translators' rights | fetched 2026-10-05 |
| dorar.net | A browser session, cached in `data/dorar/` | Cross-check of gradings; a "verify at dorar" link on every hadith | Not redistributed; links only | 2026-10-05 |
| quranpedia.net | Links | Every verse links to its page there, with tafsir | Links only | checked 2026-10-06 |
| بينات: أسئلة وأجوبة عن الإسلام (dawa.center/file/7937), the dorar.net encyclopedias, islamic-content.com/dictionary | Links | Referral for questions about Islam, by kind | Links only | checked 2026-10-06 |
| quran.com API | `eval/check_quran_text.py` | Checks the Qur'an text shown, word for word | Public API | 2026-10-06 |

The King Fahd Complex edition, dorar.net, quranpedia.net, بينات and the terms dictionary are
references the challenge's Reference Framework names (p. 3). The hadith texts are the six books
themselves, as hadith-api publishes them; their gradings were cross-checked against dorar.net
(below). quran.com is used only to test our own Qur'an text.

## Models, services and code

| Component | Role | Licence or terms |
|---|---|---|
| [intfloat/multilingual-e5-base](https://huggingface.co/intfloat/multilingual-e5-base), revision `d128750`, and its int8 ONNX export by the same author | Embeds the corpus (PyTorch) and each query (ONNX Runtime) | MIT |
| Jev by [TypeSafe](https://typesafe.ai) (`jev-latest`, `typesafe-sdk` 0.7.2) | Every decision: which text, what is asked, relevance | Commercial API; the key stays on the server |
| Vercel, Hobby plan | Hosts the web app and the API | Free plan |
| FastAPI, Pydantic, Uvicorn, NumPy, ONNX Runtime, tokenizers, huggingface-hub | API | MIT, BSD-3-Clause, Apache-2.0 |
| Next.js 16, React 19, Radix UI, shadcn/ui, Tailwind CSS 4, lucide, sonner | Web app | MIT, ISC, Apache-2.0 |
| Readex Pro (the challenge's brand font), Amiri, Amiri Quran | Typefaces | SIL Open Font License 1.1 |

Development: the code was written during the challenge with an AI coding assistant (Claude Code,
Anthropic), directed by the team lead. No earlier version exists: the first commit is
2026-10-05 17:02 (UTC+3).

## Measured results

Each number is printed by a script in this repository, which also prints the command it ran.

**Against the alternatives a reader has today**, on a held-out set: 38 questions written after
the code was frozen and run once on production (`eval/heldout.py`, 2026-10-06), in Arabic, Saudi
dialect, English, Indonesian, Urdu, French and Russian:

| | Keyword search (BM25, same books) | Meaning search (e5) | Both (Isnad's stage 1) | Isnad |
|---|---|---|---|---|
| Described texts: right text first, of 30 | 22 | 16 | 23 | **28** |
| Sayings that are not sound hadith in these books: honest answer, of 8 | 0 | 1 | 0 | **8** |

A search engine always returns its top hit, so for a saying that is not in the books it shows a
text that does not contain it; Isnad said "not found" for 6 and gave 2 as "closest, verify before
citing". Isnad's 2 misses each gave a sound hadith on the same subject in other words (Muslim 782
for 783; al-Tirmidhi 2485 for al-Bukhari 12). On the battery's own questions, which also guided
the fixes (in-sample): 29, 17, 20 and 22 of 29; 7, 0, 1 and 0 of 7 (`eval/baseline.py`).

| What | Result | Script |
|---|---|---|
| Judge battery: 76 typed questions, each with what an honest answer must contain | 76/76 on production, median 1.0 s | `eval/battery.py` |
| Behaviour tests | 14/14 on production | `eval/smoke.py` |
| Hybrid search vs each half alone, 13 labelled descriptions | first place: hybrid 8, meaning only 4, wording only 6; in the 120 Jev reads: 13, 11, 13 | `eval/hybrid_vs_single.py` |
| Qur'an text shown vs quran.com, all 6,236 verses | 0 split words; 3 differences, all spelling conventions of the King Fahd Mushaf | `eval/check_quran_text.py` |
| Gradings vs dorar.net, seeded sample of 62 | 29 found there by book and number; 29/29 agree | `scripts/05_dorar_crosscheck.py` |
| Hadith with a grading: the two Sahihs by inclusion, the Sunan by named scholars | 34,109 of 34,153 (99.9%) | `scripts/03_report.py` |
| What is asked: 5 classes, 58 descriptions x 2 runs | 108 of 116 in the labelled class; the other 8 take a safe path (for example a ruling read as general, not personal) | `eval/ask_probe2.py` |
| Quoted saying vs subject, 27 descriptions x 2 runs | 54/54 | `eval/saying_probe.py` |
| Citations looked up | about 20 ms, no model call | `eval/battery.py` (group "cite") |
| Cost of the decision model per search, 76 questions | 23,232 input tokens mean (median 24,344): $0.00098 a search, about $1 per 1,000 at Jev's $0.042 per million input tokens (output is free) | `eval/battery.py` |
| Accessibility, automated (axe-core 4.10.2, WCAG 2.0-2.2 A/AA rules), 4 pages | 0 violations (21-27 rules passed per page) | `eval/a11y.sh` |
| Memory, all 9 languages loaded, 3 searches | peak 1.1 GB (was 1.6 GB, and production was killed at the 2 GB limit) | `eval/measure_memory.py` with `ISNAD_ENCODER=onnx` |

## Limits

- The corpus is the Qur'an and the six books. A hadith found only in other books (Musnad Ahmad,
  al-Muwatta', and others) gets "not found".
- Search reads 120 candidates per query. On broad subjects it can miss well-known hadith; the
  full-corpus mode (`ISNAD_MODE=knockout`, about 40 s per query) finds more and is off by default.
- For a question about Islam, search often does not reach the texts that answer it (for
  "لماذا يعبد المسلمون الكعبة؟": 2:144, 106:3, al-Bukhari 1597). Isnad then gives the referral only.
- Modern words can miss classical wording: "ما حكم الموسيقى" does not reach al-Bukhari 5590
  ("المعازف"); "حكم المعازف" does.
- Jev's subject lists vary slightly between runs.
- Some hadith texts still begin with part of the chain; source punctuation is shown as published.
- Some hadith translations name no translator ("Unknown" in the source), and some include the
  chain of narrators.
- Language detection can read Latin-script Turkish as English; the result is right, but the
  translation then shows in English.
- The first search after some idle minutes starts the server (7-9 s). The home page starts it on
  load, so a reader who types first does not wait.

## Run it

Needs Python 3.13, Node.js 20 or later with pnpm, and a TypeSafe API key.

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # serve only
echo 'TYPESAFE_API_KEY=...' > ../.env      # outside the repository, read by src/decide.py

# The built index (1.2 GB) is not in git. Build it from the sources (several hours on a CPU):
pip install -r requirements-build.txt
python scripts/01_fetch.py                 # sources -> data/raw/
python scripts/02_normalize.py             # corpus, sanad/matn split, gradings
python scripts/03_report.py                # quality report -> data/corpus/report.md
python scripts/06b_embed_surfaces.py       # embeddings per language, resumable
python scripts/06_build_index.py           # records.jsonl, display.db; skips embedded languages
python scripts/07_translators.py           # translator credits

# The query encoder used in production (int8 ONNX, pinned revision):
python -c "from huggingface_hub import hf_hub_download as d; r='d128750597153bb5987e10b1c3493a34e5a4502a'; [d('intfloat/multilingual-e5-base', f, revision=r, local_dir='data/models/e5-base-onnx') for f in ('onnx/model_qint8_avx512_vnni.onnx', 'onnx/tokenizer.json')]"

ISNAD_ENCODER=onnx uvicorn api.app:app --port 8000
cd web && pnpm install && pnpm dev          # http://localhost:3000, calls localhost:8000

python eval/smoke.py --api http://127.0.0.1:8000
python eval/battery.py --api http://127.0.0.1:8000 --gap 2.1
```

Deploying: `scripts/deploy_api.sh` and `scripts/deploy_web.sh` (Vercel, personal Hobby scope).
The API serves only the web tier, which holds `ISNAD_PROXY_SECRET`: every search spends the paid
Jev key.

## Privacy

No accounts, no cookies, no database. A query is sent to TypeSafe for the decision; TypeSafe
states that Jev is not trained on customer requests or responses (docs.typesafe.ai/models). The API
keeps, in memory only, the last 512 answers (so repeated examples are fast) and, for one
minute, a count of requests per address (30 per minute). In the default mode nothing a reader
types is written to disk (`api/app.py`). Tests use synthetic queries only.

## Layout

```
scripts/   build the corpus and the index; deploy
src/       search.py (stage 1, citations), cascade.py (stage 2, Jev), knockout.py (full read)
api/       app.py, the HTTP service
web/       the Next.js interface (copy in web/src/lib/copy.ts, decisions in web/COPY.md)
eval/      every measurement above, and the probes behind each decision
data/      corpus report, dorar cross-check, records; the large index files are built, not stored
```

Decisions and their reasons are in the commit messages and in `HANDOFF.md`.
