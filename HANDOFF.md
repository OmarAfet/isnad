# Isnad — session handoff

Updated 2026-10-06 03:45 Riyadh, session 3 (a second judge-style pass; commits f1d630d..b07787e).
A new session starts here. Gathered challenge context (rules, rubric, Discord answers, sources):
`../CONTEXT.md`.

## 1. Deadline and submission

- **Submission closes Tue 2026-10-06 23:59 Riyadh.** Nothing is submitted yet.
- Form (7 required fields): project name, description, track (04 — أدوات المعرفة والتحقق),
  deck **PDF/PPT/PPTX ≤ 10 MB**, demo video link **≤ 2 min**, **public** GitHub repo,
  **live demo URL**. Content-and-sources documentation has no field: it goes in the deck and repo.
- **Live demo URL (published 2026-10-05 23:30 with Omar's approval): https://isnad-app.vercel.app**
- **Public repo (published 2026-10-06 12:3x with Omar's approval): https://github.com/OmarAfet/isnad**
  History scanned first: no secret values. Keep-warm workflow active (first run: HTTP 204).
- Discord: check in for Day 3 (`حاضر` in #إسناد-450 from 09:00). Omar answered the mentors'
  end-of-day-2 questionnaire himself (2026-10-06); his plan there: video and remaining
  requirements.

## 2. State: what works (all committed)

| Part | Where | Status |
|---|---|---|
| Corpus: 6,236 ayahs + 34,153 hadiths, sanad/matn split 93.8%, gradings 99.8% | `scripts/01`–`05`, `07` | done |
| Index: 9 languages, e5-base, float16, per-language memory-mapped | `scripts/06b_embed_surfaces.py` | done |
| Stage 1 search (hybrid dense + BM25, z-score 0.7/0.3) | `src/search.py` | done |
| Query encoder: PyTorch (local) or the author's int8 ONNX (`ISNAD_ENCODER=onnx`, production) | `src/search.py` | done |
| Stage 2 Jev tournament (net 120, two rounds, topic mode, copy merge) | `src/cascade.py` | **default** |
| Ruling questions: texts on the matter + referral + dorar.net/feqhia link, never a ruling | `src/cascade.py`, web | **new, live** |
| Full-corpus Jev knockout (still refers without texts on ruling questions) | `src/knockout.py` | off |
| API (FastAPI, SSE, proxy secret) | `api/app.py` → https://isnad-api.vercel.app | **live** |
| Web (Next.js 16, shadcn RTL, white Saudi dialect) | `web/` → https://isnad-app.vercel.app | **live** |
| Search by subject ("ايه عن النوم"): kind words, light10 stemming, per-text relevance | `src/search.py`, `src/cascade.py` | **fixed 2026-10-06, live** |
| Questions about Islam (belief, meaning, history, objections): texts + approved reference | `src/cascade.py`, web | **new 2026-10-06, live** |
| Judging people or groups: "outside Isnad's work", no texts | `src/cascade.py`, web | **new, live** |
| Citations looked up ("البقرة 255", "2:255", "البخاري 6018", "مسلم 2564", "آية الدين") | `src/search.py` `lookup` | **new, live** |
| Misquoted words marked ("قل هو الله واحد" -> "واحد" underlined) | `src/cascade.py` `wording`, web | **new, live** |
| Every verse links to quranpedia.net (verse + tafsir) | `scripts/_dorar.py` `ayah_url` | **new, live** |
| Page load starts the API (`POST /api/warm`) | `web/src/app/api/warm` | **new, live** |
| Word index in flat arrays (all 9 languages fit 2 GB) | `src/search.py` `Bm25` | **fixed, live** |
| Behaviour tests (14 cases) | `eval/smoke.py` | **14/14 local and production** |
| Judge battery (78 typed questions) | `eval/battery.py` | **78/78 production** |
| README: sources log, licences, results, limits, setup | `README.md`, `requirements*.txt` | **done, b07787e** |
| Translations: Arabic-letter "translations" hidden (502 Bengali); list cards preview translations | `api/app.py`, web | **live, 1b047f8** |
| Branded tab icon (svg, ico, apple); template files removed | `web/src/app/icon.svg` etc. | **live, 4137434** |
| Keep-warm ping every 5 min (GitHub Actions) | `.github/workflows/keep-warm.yml` | **active** (registered after a second push touching the file) |
| Qur'an translations shown: all 8 from QuranEnc.com, credited, versioned, footnotes | `scripts/09_quranenc.py`, web | **live, 017267e** |
| Qur'an text vs quran.com, all 6,236 verses | `eval/check_quran_text.py` | **0 split words** |

## 3. Run, test, deploy

```bash
cd isnad && . .venv/bin/activate
uvicorn api.app:app --port 8000                          # local, PyTorch encoder
ISNAD_ENCODER=onnx uvicorn api.app:app --port 8000       # local, as deployed
cd web && pnpm dev --port 3000                            # http://localhost:3000
python eval/smoke.py                                      # needs the API up
ISNAD_PROXY_SECRET=$(grep ^ISNAD_PROXY_SECRET= ../.env | cut -d= -f2-) \
  python eval/smoke.py --api https://isnad-api.vercel.app # against production
scripts/deploy_api.sh                                     # stage + deploy API, checks health
scripts/deploy_web.sh                                     # deploy web, checks a search
```

Secrets live in `../.env`, outside the repo: `TYPESAFE_API_KEY`, `ISNAD_PROXY_SECRET`. On
Vercel they are "Sensitive" env vars (API: both + `ISNAD_ENCODER=onnx` +
`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`; web: `ISNAD_API_URL`, `ISNAD_PROXY_SECRET`,
`ENABLE_EXPERIMENTAL_COREPACK=1`). The ONNX model downloads to `data/models/` (gitignored):
`hf_hub_download("intfloat/multilingual-e5-base", "onnx/model_qint8_avx512_vnni.onnx",
revision="d128750597153bb5987e10b1c3493a34e5a4502a")` plus `onnx/tokenizer.json`.
Machine has 9 GB RAM: never run two embedding jobs at once.

## 4. Decisions (why, at the time)

1. **Jev (TypeSafe) is the decision model.** The idea was built around Jev; session 1 first
   built search without asking what "نموذج القرار" meant. Lesson: ask before substituting.
2. **Interface register: white Saudi dialect** (Omar's choice; trade-off in `web/COPY.md`).
3. **Mode: `net` (fast) is the default.** Knockout (~40 s, ~3.5 M tokens) was too slow.
4. **Translations are a matching surface only.** Never translate scripture ourselves.
5. **dorar.net:** cached cross-check (29/29) and deep links; never called at runtime.
6. **No login in the demo.**
7. **Hosting must be completely free** (Omar, session 2: "The app should be completely free
   somehow"). Hugging Face Docker Spaces now need PRO ($9/month), so: Vercel Hobby, scope
   **omar-afet**. The Vercel login also has **drjat** (company team, Pro, and the CLI's
   default): never deploy Isnad there; every command passes `--scope omar-afet`.
8. **int8 ONNX query encoder in production**: PyTorch + float32 model did not fit Vercel's 2 GB;
   the author's int8 export measured equal or better (section 5).
9. **Ruling questions** (Omar's request "make isnad not يفتي but give existing ones", his choice
   among three previews): the texts on the matter, then "إسناد ما يفتي" with a dorar.net/feqhia
   link and "ask scholars"; a personal case (framework level د) leads with the referral.
   Rejected: published fatwas by named bodies (new dataset, licences, too risky).
10. **API locked to the web tier** by `ISNAD_PROXY_SECRET`: every search spends the paid Jev key.
11. **Five request classes** (session 3): the Reference Framework's own test questions
    ("لماذا يعبد المسلمون الكعبة؟") got "إسناد ما يفتي" and a fiqh search. Added "question"
    (texts that speak to it + the approved reference for its kind: بينات for objections, dorar
    creed/fiqh/history encyclopedias, the terms dictionary) and "judge_people" (out of scope).
    The question path needs a question form and a yes on "is this about Islam" (a separate
    Noul: an "unrelated" option inside the Choice took "verse about bees" to unrelated).
12. **A quoted saying never gets a subject list** (Jev Noul, 54/54): "الدين المعاملة" listed
    debt hadith (الدَّين). Two-word quotations must be in the text whole.
13. **Citations are looked up, not searched**; no match percentage, no Jev call.
14. **Identical shown text = one report**, so the Sahihayn copy leads (al-Bukhari 6922, not
    al-Nasa'i 4063, for "من بدل دينه فاقتلوه").
15. **No disk writes in the default mode**: answers live in memory; only knockout saves them.
16. **A broad request returns one text only at p >= 0.90** (BROAD_SINGLE), else the list:
    "حديث عن الكذب" got one hadith at 0.82; loosely described single verses score 0.91-1.00.
17. **Translations whose letters are mostly Arabic are not shown** (502 Bengali entries).
18. **Qur'an translations shown come from QuranEnc.com** (Omar, 2026-10-06: "show approved and
    trusted ones"): en Hilali-Khan, ur Junagarhi, tr and ru Rowwad Center, fr Noor International,
    ta Baqawi, bn Abu Bakr Zakaria, id the Complex edition. QuranEnc's terms: no alteration,
    name publisher, source, version; so the credit line links QuranEnc.com with the version (or
    the fetch date) and the footnotes open on request. Search surfaces unchanged.

## 5. Measured numbers (each reproducible from a script)

- 40,389 texts; 9 languages; 34,109 of 34,153 hadith graded (Sahihayn by inclusion, Sunan by
  8 named graders).
- dorar.net severity agreement 29/29 (`scripts/05`).
- Hybrid search hit@1 8/13 vs dense 4/13, lexical 6/13; hit@120 13, 11, 13
  (`eval/hybrid_vs_single.py`, ONNX as deployed; `eval/fusion_sweep.py` no longer imports).
- Encoders (`eval/compare_encoders.py`, 25 queries, 7 languages): cosine 0.98–0.99; shortlist
  overlap median 85%; labelled hit@1 ONNX 7/13 vs PyTorch-CPU 6/13; hit@120 13/13 vs 12/13.
- Memory (`ISNAD_ENCODER=onnx python eval/measure_memory.py`, all 9 languages): peak 1.1 GB
  after the flat-array index (was 1.6 GB; production was SIGKILLed at 2 GB after 6 languages).
  BM25 heap 1,313 MB -> 200 MB; scores equal to 3.8e-06, same top 50. `ready_seconds` 3.3-3.6.
- Production (`eval/smoke.py`, from Riyadh to Vercel iad1): 14/14, median 1.2 s; 7-9 s on a
  cold instance (right after a deploy, or after idle minutes).
- Search by subject (`eval/topic_recall.py`, 10 topic queries, 45 known answers): answers
  reaching topic mode 15 -> 27; labelled single-text queries 13/13 inside Jev's 120.
- Relevance judging (`eval/relevance_probe.py`): text inside each question, "same sense"
  wording, bar 0.75; right texts 0.80+. Request classifier (`eval/ask_probe.py`): 0/36 wrong.
- Trace one query without Jev: `python eval/explain.py "<query>" --expect quran:2:255`.
- **Held-out** (`eval/heldout.py`, 38 questions written after f7fed9f, run once on production):
  described texts right first, of 30: keyword 22, meaning 16, hybrid 23, **Isnad 28**; sayings
  not in the books answered honestly, of 8: 0, 1, 0, **8**. Misses: Muslim 782 for 783 and
  al-Tirmidhi 2485 for al-Bukhari 12 (same subject, other wording). Do not tune on this set.
  Second run after later fixes (5e2f66a, production): identical, 28/30 and 8/8.
- Baseline (`eval/baseline.py`, production): described texts right first, of 29: keyword 17,
  meaning 20, hybrid 22, Isnad 29; sayings not in the books answered honestly, of 7: 0, 1, 0, 7.
  In-sample for Isnad (the battery guided the fixes).
- Accessibility (`eval/a11y.sh`, axe-core 4.10.2, WCAG 2.0-2.2 A/AA rules): 0 violations on
  home, a result, a list and /method. History scan before publishing: neither secret value in
  any commit or tracked file; no .env ever committed.
- Cost: Jev input tokens per search, battery of 76: mean 23,232, median 24,344, max 37,780
  -> $0.00098 a search, ~$1 per 1,000 ($0.042/Mtok input, output free; docs.typesafe.ai/models).
- Session 3 probes: `eval/ask_probe2.py` (5 classes + Islamic gate, 58 descriptions x 2: 108/116
  in class, the rest safe), `eval/saying_probe.py` (54/54), `eval/refer_probe.py` (16/18, the
  other 2 defensible). Production after deploy: battery 76/76 (median 1.0 s), smoke 14/14.
- Judge-style test (2026-10-06, agent on the live site + `eval/battery.py`): fixed split Qur'an
  words (2,054 places, source fault), Muslim cited by Abd al-Baqi numbers (7,215 refs,
  `scripts/08_cite_muslim.py`), quoted-saying guard, both kinds for ruling lists, cards open
  the clicked text, Back works. Commit 92bb67f lists every finding and its evidence.
  First search after idle through the web ≈ 8 s (both functions start cold); warm ≈ 1 s.
- Vercel Hobby CLI refuses any single file over 100 MB (per file, not total; measured).
- TypeSafe limits (Omar's org): 80 requests/s, 100,000 input tokens/s.

## 6. Open items, in priority order

1. Done: Qur'an translations (decision 18). 2. Done: public GitHub repo.
2a. **Deck**, **video**, **submission form**: Omar's next steps. (`gh` is logged in as OmarAfet; no remote yet). Ask Omar before
   publishing. Check first: no secrets in history (keys live in `../.env`), `deploy/` and
   `data/models/` are gitignored.
3. **Deck** (PptxGenJS). Brand: Readex Pro, #12183F, #6150EA, #2EF2C2, #F2F4FF; template
   slides 1-7 are instructions to delete; ≤ 10 MB. The registered deck cites صحيح مسلم (35) for
   إماطة الأذى; this edition numbers it 153.
4. **Video** ≤ 2 minutes. Warm the site first (one search) to avoid the 8 s cold start.
5. **Submit** the form; keep the confirmation.
6. Done: `dorar.net/feqhia/search?q=…` returned HTTP 200 in an Internet Archive capture of
   2025-08-07; `/aqeeda`, `/feqhia`, `/history` HTTP 200 in 2024 captures (CDX API). A live
   click from a real browser is still the only first-hand check (Cloudflare blocks scripts).
7. Optional: host the built index (1.2 GB) as a release asset so the repo runs without a
   rebuild (needs the public repo first); Discord check-in.

## 7. Known limits

- Fast mode misses some well-known hadith on broad topics (decision 3).
- Jev's topic and ruling lists vary a little between runs (same query, different 8th text).
- Subject search still misses some verses whose wording differs from the query (for sleep:
  39:42 "منامها", 8:11 "النعاس", 6:60): dense search ranks short unrelated verses above them.
- Some matns still hold the chain (e.g. Tirmidhi 887); Muslim 6640 shows apart from 6638.
- Knockout mode still answers ruling questions with a referral only.
- Grader names for four Sunan translations are "Unknown" in the source metadata.
- Cold start: the first search after a few idle minutes takes ≈ 8 s (the page says so after 3 s);
  the home page now starts the API on load, so a reader who types first does not wait.
- Questions about Islam: search often misses the texts that answer them (Kaaba: 2:144, 106:3,
  al-Bukhari 1597 are not in the 120), so the answer is the referral alone.
- Latin-script Turkish can be detected as English (translation then shown in English).
- "آخر آية نزلت" gets "not found" (the reports are hadith; the request names a verse).
- Modern words miss classical texts: "ما حكم الموسيقى" finds no text (al-Bukhari 5590 says
  المعازف; "حكم المعازف" finds it). Hadith Jibril shows the Tirmidhi copy (the Sahihayn copies
  are worded too differently to merge). Source punctuation (stray quote marks) is shown as is.

## 8. Processes at this point

Local API on :8000 runs the current code with the ONNX encoder (session 3); `next dev` on :3000.
The isolated headless browser session `isnad-judge` (agent-browser `--auto-connect false`) was
used for screenshots; `/tmp/isnad-judge/` holds the probe tool and outputs.
