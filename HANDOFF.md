# Isnad — session handoff

Updated 2026-10-06 15:20 Riyadh, at the end of session 3. A new session starts here. Challenge
context (rules, rubric, Discord answers, sources): `../CONTEXT.md`. Every decision below has its
reason and evidence in the commit that made it (`git log`).

## 0. BLOCKER (found at the end of session 3)

**The live demo cannot decide: TypeSafe credits are exhausted.** Since about 15:08 Riyadh every
Jev call returns HTTP 402, "Your organization has no available TypeSafe API credits"
(`req_01a11126bce471608ee0da0645d6bb95`, checked 15:25). Every description then shows "خدمة
التحقق متوقفة الحين" with no text; only citations ("البقرة 255") still work, since they need no
Jev call. Fix: Omar adds credits or auto-reload at https://console.typesafe.ai/settings/billing
(a paid action: his decision). Then run `python eval/smoke.py --api https://isnad-api.vercel.app`
to confirm 14/14. Estimate, not a measurement: session 3's test runs used about 50 million input
tokens (~$2 at $0.042 per million), counted from the runs made times the measured mean per
search, so testing very likely used a large share of the credits. Budget future test runs: one
full battery run is about 1.9 M tokens. The keep-warm ping and the page warm-up call
`/api/health` only and use no credits.

## 1. Deadline and submission

- **Submission closes Tue 2026-10-06 23:59 Riyadh.** Not submitted yet; Omar does the deck, the
  video and the form.
- Form (7 fields): project name, description, track (04 — أدوات المعرفة والتحقق), deck
  **PDF/PPT/PPTX ≤ 10 MB**, video link **≤ 2 min**, **public** GitHub repo, **live demo URL**.
  Content-and-sources documentation has no field: it is in the README and goes in the deck.
- Live demo: **https://isnad-app.vercel.app** (published 2026-10-05 with Omar's approval).
- Public repo: **https://github.com/OmarAfet/isnad** (published 2026-10-06 ~12:35 with Omar's
  approval, after a history scan: neither secret value in any commit or tracked file).
- Omar answered the mentors' end-of-day-2 questionnaire himself. His answer calls it "النموذج
  الأولي"; the guide says a prototype is not accepted, so the deck and video should present it
  as a complete, live product.

## 2. State (all committed, pushed, deployed)

| Part | Where | Status |
|---|---|---|
| Corpus: 6,236 verses + 34,153 hadith; gradings for 34,109 | `scripts/01`-`08` | done |
| Index: 9 languages, e5-base, per-language memory-mapped; word index in flat arrays | `scripts/06b`, `src/search.py` | done |
| Stage 1 hybrid search; stage 2 Jev tournament (120 texts, two rounds) | `src/search.py`, `src/cascade.py` | live |
| Request classes: find a text, general ruling, personal case, question about Islam, judging people | `src/cascade.py` | live |
| Ruling questions: texts on the matter + "إسناد ما يفتي" + dorar.net/feqhia link | `src/cascade.py`, web | live |
| Questions about Islam: texts that speak to it + the approved reference for its kind | `src/cascade.py`, `scripts/_dorar.py` | live |
| Judging people or groups: "outside Isnad's work", no texts | `src/cascade.py`, web | live |
| Citations looked up by number ("البقرة 255", "2:255", "البخاري 6018", "مسلم 2564") | `src/search.py` `lookup` | live |
| Misquoted words underlined ("قل هو الله واحد" -> "واحد") | `src/cascade.py` `wording`, web | live |
| Same words in several books: al-Bukhari / Muslim copy shown first | `src/search.py` | live |
| Every verse links to quranpedia.net (verse + tafsir) | `scripts/_dorar.py` `ayah_url` | live |
| Qur'an translations shown: all 8 from QuranEnc.com, translator + version + footnotes | `scripts/09_quranenc.py`, web | live |
| Hadith "translations" that are mostly Arabic letters hidden (502 Bengali) | `api/app.py` | live |
| Jev input tokens counted per search (`jev.input_tokens`) | `src/cascade.py` | live |
| Page load warms the API; GitHub Action pings `/api/warm` every 5 min | `web/src/app/api/warm`, `.github/workflows/keep-warm.yml` | live, active |
| README: sources log, licences, held-out results, limits, setup | `README.md`, `requirements*.txt` | done |
| Branded tab icon; template files removed | `web/src/app/icon.svg` etc. | live |
| SEO: search-word title + description, canonical URLs, JSON-LD SearchAction on `?q=`, `robots.txt` (blocks `/api/`), `sitemap.xml` (`/`, `/method`), manifest; site icon as the share image (512 px from `icon.svg`) | `web/src/app/layout.tsx`, `robots.ts`, `sitemap.ts`, `manifest.ts`, `opengraph-image.png` | live |
| Full-corpus knockout mode (~40 s a search) | `src/knockout.py` | off |

Production: API at commit 96807f6; web at a29739c (SEO, deployed 2026-10-06 16:20 Riyadh; home,
`/method`, `robots.txt`, `sitemap.xml`, `manifest.webmanifest` and `opengraph-image.png` checked
HTTP 200 on the live site).

## 3. Run, test, deploy

```bash
cd isnad && . .venv/bin/activate
ISNAD_ENCODER=onnx uvicorn api.app:app --port 8000       # local API, as deployed
cd web && pnpm dev --port 3000                            # http://localhost:3000
export ISNAD_PROXY_SECRET=$(grep ^ISNAD_PROXY_SECRET= ../.env | cut -d= -f2-)
python eval/smoke.py   --api https://isnad-api.vercel.app --gap 2.1   # 14 behaviour cases
python eval/battery.py --api https://isnad-api.vercel.app --gap 2.1   # 78 cases + Jev cost
python eval/heldout3.py --api https://isnad-api.vercel.app --gap 2.1  # held-out, see section 5
python eval/probe.py "query" ...                          # one answer, compact (judge probe)
python eval/explain.py "query" --expect quran:2:255       # trace stage 1, no Jev call
eval/a11y.sh                                              # axe-core on 4 live pages
scripts/deploy_api.sh && scripts/deploy_web.sh            # Vercel, scope omar-afet only
```

Secrets are in `../.env`, outside the repo: `TYPESAFE_API_KEY`, `ISNAD_PROXY_SECRET`. On Vercel:
API has both + `ISNAD_ENCODER=onnx` + `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`; web has `ISNAD_API_URL`,
`ISNAD_PROXY_SECRET`, `ENABLE_EXPERIMENTAL_COREPACK=1`. The ONNX model (gitignored) downloads
with `hf_hub_download` (README, "Run it"). QuranEnc texts (`data/quranenc/`) are gitignored;
`python scripts/09_quranenc.py` fetches and applies them. The machine has 8 GB RAM: never run two
embedding jobs at once.

## 4. Decisions (why, at the time)

1. **Jev (TypeSafe) is the decision model.** Ask before substituting any named component.
2. **Interface register: white Saudi dialect** (Omar; `web/COPY.md`).
3. **Fast mode (`net`) is the default**: knockout took ~40 s and ~3.5 M tokens a search.
4. **Isnad never writes or translates scripture**: it selects texts; translations are shown
   attributed.
5. **dorar.net**: cached cross-check (29/29) and links only; never called at runtime.
6. **No login.** 7. **Free hosting only**: Vercel Hobby, scope **omar-afet**, never drjat.
8. **int8 ONNX query encoder** in production (PyTorch did not fit 2 GB).
9. **Ruling questions**: texts on the matter, then a referral (Omar's choice); never a ruling.
10. **API locked to the web tier** by `ISNAD_PROXY_SECRET` (every search spends the Jev key).
11. **Questions about Islam and judging people are their own classes** (session 3): the
    Reference Framework's test questions had got "إسناد ما يفتي". The question path needs a
    question form and a yes on "is this about Islam" (a separate Jev Noul).
12. **Citations are looked up, not searched** (no Jev call, no match percentage).
13. **Identical shown text = one report**, so the Sahihayn copy leads.
14. **No disk writes in the default mode** (answers live in memory only).
15. **A broad request returns one text only at p >= 0.90**, else the list.
16. **Qur'an translations from QuranEnc.com** (Omar: "show approved and trusted ones"); its
    terms: no alteration, name publisher, source and version.
17. **No example sentences in instructions to Jev, no hand-written answer tables** (Omar: "make
    sure not to lie and add hard coded fixes ... let the idea talk"; "remove them and
    re-measure honestly"). Several examples had been the test questions themselves. Never add
    test phrases to prompts or lookup tables to make a case pass.
18. **Fix generally, then measure on a held-out set frozen in git before the fix**; report every
    miss as it came. Kept in session 3: question words name a subject (fixed "أهل السنة" being
    read as a hadith cue); route by the whole non-text share; "what Islam teaches about a
    subject" is a question; misquote marks follow Jev's quoted-saying score. Measured and
    dropped: English-translation search for verse names, Arabic root matching, verses quoted by
    hadith, three prompt rewordings, a "bare statement" rule.
19. **Share image is the site icon, not a screenshot** (2026-10-06): the saved screenshot
    (`web/.shots/desktop-home.png`) shows an old subtitle and the dev-mode button, and a
    generated image risks broken Arabic letter joining. A page that sets its own `openGraph` or
    `twitter` must name the image again: Next.js replaces the layout's values, it does not merge.

## 5. Measured numbers (each printed by a script that also prints its command)

- **Held-out set 1** (`eval/heldout.py`, 38 questions): 28/30 described texts (keyword search
  22, meaning search 16, both 23), 8/8 sayings that are not sound hadith (search 0-1). Never
  used for tuning; unchanged by every later change.
- **Held-out set 3** (`eval/heldout3.py`, 59 questions of every kind, frozen at 6a3c392 before
  the last fixes): **46 before, 49 after**. After: described 12/13 (search 5, 4, 7), sayings
  8/8 (search 0, 0, 1), questions 8/8, judging people 5/5, rulings 4/4, citations 3/3, subjects
  4/4, misquotes 4/5 (the miss is a labelling error: 20:114 says "رَبِّ", so marking "ربي" is
  right), **verse names 1/9**. One set-3 query ("آية الحجاب") was traced by mistake during a
  dropped experiment; disclosed in the README.
- **Set 2** (`eval/heldout2.py`, 57): 49/57 before and after the examples were removed; it then
  guided the last fixes, so it is a development set now (53/57).
- **Battery** (`eval/battery.py`, 78, in-sample): 72/78 on production. Failing: "آية الدين",
  "خواتيم سورة البقرة", "the verse of the throne" (gives 27:26), "Аят аль-Курси", and
  "الدين المعاملة" twice (lists hadith on debts). **Smoke** 14/14.
- Before the cleanup the battery read 78/78 and the saying probe 54/54: those numbers were
  inflated by test phrases in the prompts and the name table; do not quote them.
- Cost: mean 24,141 Jev input tokens a search (78-case battery) -> $0.00101 a search, about $1
  per 1,000 ($0.042 per million input tokens, output free; docs.typesafe.ai/models).
- Hybrid stage 1 (`eval/hybrid_vs_single.py`, 13 labelled): first place 8 vs meaning 4, words 6.
- Qur'an text vs quran.com: 0 split words in 6,236 verses. dorar.net grading agreement: 29/29.
- Accessibility (`eval/a11y.sh`): 0 axe-core violations on 4 pages. Memory: peak 1.1 GB with all
  9 languages (production had been killed at 2 GB before the flat-array index).
- Latency: warm ~1 s; citations ~20 ms; cold start 7-9 s (page warm-up and the 5-minute ping
  reduce how often a reader meets it).

## 6. Open items

0. **Add TypeSafe credits** (section 0), then re-run the smoke test on production.
1. **Deck, video, submission form** (Omar; a parallel session built them in `../submission/`,
   see its HANDOFF.md). For the video: open the site once first, so the
   server is warm. Good demo searches: "الجنة تحت أقدام الأمهات" (sound text, differing words
   marked), "حديث إن الفقيه أشد على الشيطان من ألف عابد" (fabricated warning), "قل هو الله
   واحد" (misquote), "the hadith about the five pillars of Islam" (English), "لماذا يعبد
   المسلمون الكعبة؟" (question -> referral), "البقرة 255" (citation). Deck brand: Readex Pro,
   #12183F, #6150EA, #2EF2C2, #F2F4FF; template slides 1-7 are instructions to delete; ≤ 10 MB.
2. **Google Search Console** (Omar; needs his Google account): add https://isnad-app.vercel.app
   and submit `/sitemap.xml`. Old shared links keep their cached preview; the Facebook Sharing
   Debugger refreshes one.
3. Optional: host the built index (1.2 GB) as a GitHub release asset so the repo runs without a
   rebuild; Discord check-in.

## 7. Known limits (also in the README)

- **Verse names**: a traditional name shares no words with its verse ("آية الدين", "آية الوضوء"),
  so search never hands the verse to Jev: 1/9 in set 3. "the verse of the throne" gives 27:26.
  "آية الكرسي" works through search. No name table, by decision 17.
- "الدين المعاملة" (a saying, not a hadith) is read as being about debts and gets a list.
- "Does Islam allow X?" is handled as a ruling question (texts + fiqh referral).
- Questions about Islam: search often misses the texts that answer them (the Kaaba question gets
  the referral only).
- Fast mode can miss well-known hadith on broad subjects; lists vary a little between runs.
- Modern words can miss classical wording ("الموسيقى" vs "المعازف").
- Some matns still begin with part of the chain; some hadith translations name no translator
  or include the chain; Latin-script Turkish can be detected as English.

## 8. Processes and files at the end of session 3

- Stopped: the local API on :8000 and the isolated browser sessions (`isnad-judge`, `isnad-a11y`).
- Still running from session 1: `next dev` on :3000 (not started in session 3).
- `/tmp/isnad-judge/` (not in git): raw outputs of every run in session 3, and
  `display.db.bak`, the display store before the QuranEnc translations (rollback copy).
