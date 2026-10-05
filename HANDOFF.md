# Isnad — session handoff

Written 2026-10-05 22:10 Riyadh, at the end of session 1. A new session starts here.
Gathered challenge context (rules, rubric, Discord answers, sources): `../CONTEXT.md`.

## 1. Deadline and submission

- **Submission closes Tue 2026-10-06 23:59 Riyadh.** Nothing is submitted yet.
- Form (7 required fields): project name, description, track (04 — أدوات المعرفة والتحقق),
  deck **PDF/PPT/PPTX ≤ 10 MB**, demo video link **≤ 2 min**, **public** GitHub repo,
  **live demo URL**. Content-and-sources documentation has no field: it goes in the deck and repo.
- Discord: check in for Day 3 (`حاضر` in #إسناد-450 from 09:00); the mentor's progress
  questionnaire (2026-10-04 16:31) is unanswered.

## 2. State: what works (all committed)

| Part | Where | Status |
|---|---|---|
| Corpus: 6,236 ayahs + 34,153 hadiths, sanad/matn split 93.8%, gradings 99.8% | `scripts/01`–`05`, `07` | done |
| Index: 9 languages, e5-base, float16, per-language memory-mapped | `scripts/06b_embed_surfaces.py` | done |
| Stage 1 search (hybrid dense + BM25, z-score 0.7/0.3) | `src/search.py` | done |
| Stage 2 Jev tournament (net 120, two rounds, topic mode, fatwa referral, copy merge) | `src/cascade.py` | **default** |
| Full-corpus Jev knockout (Jev reads all 37,628 unique texts) | `src/knockout.py` | off by default |
| API (FastAPI, SSE progress, disk cache) | `api/app.py` | done |
| Web (Next.js 16, shadcn RTL, lucide, white Saudi dialect) | `web/` | done |
| Behaviour tests (10 cases) | `eval/smoke.py` | **10/10, median 0.9 s** |

## 3. Run it locally

```bash
cd isnad && . .venv/bin/activate
uvicorn api.app:app --host 127.0.0.1 --port 8000      # ISNAD_MODE=net (default) or knockout
cd web && pnpm dev --port 3000                       # http://localhost:3000
python eval/smoke.py                                 # from isnad/, needs the API up
```

Key in `../.env` (`TYPESAFE_API_KEY`), outside the repo on purpose. Machine has 9 GB RAM:
never run two embedding jobs at once (it swapped to a crawl twice in session 1).

## 4. Decisions (why, at the time)

1. **Jev (TypeSafe) is the decision model.** The idea was built around Jev; session 1 first
   built search without asking what "نموذج القرار" meant. Lesson: ask before substituting.
2. **Interface register: white Saudi dialect** (Omar's choice over recommended simple MSA;
   trade-off recorded in `web/COPY.md`). Scripture, references, grades, names stay as sourced.
3. **Mode: `net` (fast) is the default.** Omar first chose the full knockout for accuracy,
   then reverted after using it: ~40 s and ~3.5 M tokens per search was too slow. Knockout
   stays behind `ISNAD_MODE=knockout`; it found Muslim 4, Bukhari 2682, Bukhari 2459 for
   "حديث عن الكذب" that `net` misses.
4. **Translations are a matching surface only.** Never translate scripture ourselves; show the
   Arabic as the answer with the published translation credited.
5. **dorar.net:** cached cross-check (29/29 agreement) and deep links; never called at runtime.
6. **No login in the demo:** the form has no field for demo credentials.

## 5. Measured numbers (for the deck; each reproducible from a script)

- 40,389 texts; 9 languages; 99.8% of hadith carry a named-scholar ruling; 8 graders.
- dorar.net severity agreement 29/29 on identifiable sampled hadith (`scripts/05`).
- Hybrid search hit@1 7/13 vs dense 3/13, lexical 4/13 (`eval/fusion_sweep.py`).
- English queries that ranked 222, 2,093, 29,463 now return the right Arabic text.
- Fast mode: 10/10, median 0.9 s, max 1.8 s. Knockout: ~42 s, ~3.5 M tokens per search.
- Knockout round-one recall 8/8 with and without diacritics (`eval/round1_recall.py`).
- TypeSafe limits (Omar's org): 80 requests/s, 100,000 input tokens/s, shared across keys;
  one request holds ~240 diacritised texts before `max_tokens_exceeded`.
- Tokens spent in session 1 testing the knockout: roughly 40 M. Check the TypeSafe console.

## 6. Open items, in priority order

1. **NEW FEATURE requested by Omar (verbatim):** "adding a new feature to make isnad not يفتي
   but give existing ones." His example: `ماحكم الزنا` currently returns only
   `سؤالك يحتاج فتوى، وإسناد ما يفتي…`.
   - **Bug behind it:** the fatwa detector (`FATWA_INSTRUCTIONS`, `src/cascade.py`) fires on
     GENERAL ruling questions. The Reference Framework's level (د) covers only a ruling on an
     individual's own case. The prohibition of zina is definitive (level أ: Al-Isra 32,
     An-Nur 2) and should be answered from the texts, not refused.
   - **Ask Omar first:** "existing ones" = (a) the Qur'an verses and hadith on the ruling,
     which the corpus already has; or (b) published fatwas by named bodies (e.g. the
     Permanent Committee, binbaz.org.sa), which needs a new, sourced, licensed dataset.
   - Likely design: three outcomes - personal case → refer AND show the general texts;
     general ruling → show evidence texts with sources; disputed (level ج) → state that
     scholars differ and refer. Never generate a ruling.
2. **Deploy** - API to Hugging Face Spaces (Docker, free, 16 GB); web to Vercel. Needs
   Omar's accounts. **Ask before publishing anything.**
3. **README** (required, terms clause 9): setup, sources and licences log - verified:
   hadith-api and quran-api = The Unlicense, multilingual-e5-base = MIT, Readex Pro / Amiri /
   Amiri Quran = SIL OFL; translations carry their translators' rights and are shown
   attributed - AI disclosure, measured results, limits.
4. **Deck** (PptxGenJS, which built the registered idea deck). Brand: Readex Pro, #12183F,
   #6150EA, #2EF2C2, #F2F4FF; template slides 1-7 are instructions to delete; ≤ 10 MB.
   The registered deck cites صحيح مسلم (35) for إماطة الأذى; this edition numbers it 153.
5. **Video** ≤ 2 minutes.
6. Optional: a "cached answer" line in the UI (offered; no answer yet).

## 7. Known limits

- Fast mode misses some well-known hadith on broad topics (see decision 3).
- Muslim 6640 shows as a separate fragment of Muslim 6638 in topic lists.
- Narrator-variation notes ("وقال ابن أبي شيبة في روايته") stay inside some matns.
- Grader names for four Sunan translations are "Unknown" in the source metadata.

## 8. Processes at session end

API (uvicorn :8000, net) and web (next dev :3000) were running; they stop with the session.
