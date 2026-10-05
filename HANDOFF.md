# Isnad — session handoff

Updated 2026-10-05 23:35 Riyadh, during session 2 (session 1 ended 22:10). A new session starts
here. Gathered challenge context (rules, rubric, Discord answers, sources): `../CONTEXT.md`.

## 1. Deadline and submission

- **Submission closes Tue 2026-10-06 23:59 Riyadh.** Nothing is submitted yet.
- Form (7 required fields): project name, description, track (04 — أدوات المعرفة والتحقق),
  deck **PDF/PPT/PPTX ≤ 10 MB**, demo video link **≤ 2 min**, **public** GitHub repo,
  **live demo URL**. Content-and-sources documentation has no field: it goes in the deck and repo.
- **Live demo URL (published 2026-10-05 23:30 with Omar's approval): https://isnad-app.vercel.app**
- Discord: check in for Day 3 (`حاضر` in #إسناد-450 from 09:00); the mentor's progress
  questionnaire (2026-10-04 16:31) is unanswered.

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
| Behaviour tests (12 cases) | `eval/smoke.py` | **12/12 local and production** |

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

## 5. Measured numbers (each reproducible from a script)

- 40,389 texts; 9 languages; 99.8% of hadith carry a named-scholar ruling; 8 graders.
- dorar.net severity agreement 29/29 (`scripts/05`).
- Hybrid search hit@1 7/13 vs dense 3/13, lexical 4/13 (session 1, MPS; `eval/fusion_sweep.py`
  no longer imports: it asks `search.py` for the removed `_minmax`).
- Encoders (`eval/compare_encoders.py`, 25 queries, 7 languages): cosine 0.98–0.99; shortlist
  overlap median 85%; labelled hit@1 ONNX 7/13 vs PyTorch-CPU 6/13; hit@120 13/13 vs 12/13.
- Memory (`eval/measure_memory.py`, all 9 languages): PyTorch 2.0 GB, ONNX 1.6 GB; Arabic ready
  10 s → 1.8 s locally; on Vercel `ready_seconds` 3.6–4.1.
- Production (`eval/smoke.py`, from Riyadh to Vercel iad1): 12/12, median 1.1 s, max 3.4 s.
  First search after idle through the web ≈ 8 s (both functions start cold); warm ≈ 1 s.
- Vercel Hobby CLI refuses any single file over 100 MB (per file, not total; measured).
- TypeSafe limits (Omar's org): 80 requests/s, 100,000 input tokens/s.

## 6. Open items, in priority order

1. **README** (required, terms clause 9): setup, sources and licences log - hadith-api and
   quran-api = The Unlicense, multilingual-e5-base and its ONNX export = MIT, Readex Pro /
   Amiri / Amiri Quran = SIL OFL; translations carry their translators' rights and are shown
   attributed; hosting Vercel Hobby; Jev (TypeSafe). AI disclosure, measured results, limits.
2. **Public GitHub repo** (`gh` is logged in as OmarAfet; no remote yet). Ask Omar before
   publishing. Check first: no secrets in history (keys live in `../.env`), `deploy/` and
   `data/models/` are gitignored.
3. **Deck** (PptxGenJS). Brand: Readex Pro, #12183F, #6150EA, #2EF2C2, #F2F4FF; template
   slides 1-7 are instructions to delete; ≤ 10 MB. The registered deck cites صحيح مسلم (35) for
   إماطة الأذى; this edition numbers it 153.
4. **Video** ≤ 2 minutes. Warm the site first (one search) to avoid the 8 s cold start.
5. **Submit** the form; keep the confirmation.
6. Verify `https://dorar.net/feqhia/search?q=…` on the live site (Cloudflare blocks curl; the
   pattern comes from the page's own search form in an Internet Archive copy, 2025).
7. Optional: Discord check-in; mentor questionnaire; "cached answer" line in the UI.

## 7. Known limits

- Fast mode misses some well-known hadith on broad topics (decision 3).
- Jev's topic and ruling lists vary a little between runs (same query, different 8th text).
- Some matns still hold the chain (e.g. Tirmidhi 887); Muslim 6640 shows apart from 6638.
- Knockout mode still answers ruling questions with a referral only.
- Grader names for four Sunan translations are "Unknown" in the source metadata.
- Cold start: the first search after a few idle minutes takes ≈ 8 s.

## 8. Processes at this point

Session-1 servers still run: API on :8000 (old code, PyTorch) and `next dev` on :3000. The
isolated headless browser session `isnad-shots` (agent-browser `--auto-connect false`) was used
for screenshots; close it with `agent-browser --auto-connect false --session isnad-shots close`.
