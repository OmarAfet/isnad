"""Isnad HTTP API.

One endpoint does the work: POST /api/search runs stage one (hybrid search over every language
surface) and stage two (the Jev tournament), and returns either one text with its source, its
ruling and a calibrated confidence, or an explicit no-match.

User-facing sentences live in the web app, not here. The API returns codes (verdict, severity,
action) so that all interface copy sits in one place, in one register, and is reviewed together.

Run: uvicorn api.app:app --port 8000   (from the isnad/ directory)
"""
import asyncio
import hmac
import json
import os
import re
import sys
import threading
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cascade                    # noqa: E402
import knockout                   # noqa: E402
from decide import load_key       # noqa: E402
from search import Isnad          # noqa: E402

MAX_QUERY_CHARS = 300
MIN_QUERY_CHARS = 3
CACHE_SIZE = 512                  # judges will try the same examples; answer those from memory
RATE_LIMIT = 30                   # requests per IP per minute; the Jev key is real money
ALTERNATIVES = 3
ALT_MIN_PROB = 0.05

# Default: "net" - search shortlists 120 texts, Jev decides over them in two rounds (~1 s).
# "knockout" makes Jev read all 40,389 texts on every search (~40 s, ~3.5M tokens). The team lead
# chose knockout for accuracy, then reverted to net after using it: the 40-second wait was too
# long. Knockout stays available, since on topic queries it found hadith the shortlist missed
# (Muslim 4, Bukhari 2682, Bukhari 2459 for "حديث عن الكذب").
MODE = os.environ.get("ISNAD_MODE", "net")
CACHE_VERSION = "2026-10-06.questions-lookup"  # bump when behaviour changes, so stale answers die
# Test runs point ISNAD_CACHE_FILE at /tmp, so they do not overwrite the saved answers in git.
CACHE_FILE = (os.environ.get("ISNAD_CACHE_FILE")
              or os.path.join(ROOT, "data", "cache", f"answers-{MODE}.json"))

# Every search spends the paid Jev key, and once deployed this service has a public address. When
# ISNAD_PROXY_SECRET is set, only a caller that presents it - the web tier - is served. Behind that
# proxy the connecting address is the proxy's own, so the proxy forwards the reader's address in
# x-isnad-client-ip, and that is the address the per-minute limit applies to.
PROXY_SECRET = os.environ.get("ISNAD_PROXY_SECRET") or None

STATE = {}


@asynccontextmanager
async def lifespan(app):
    if not load_key():
        raise RuntimeError("TYPESAFE_API_KEY is not set and no .env was found")
    from typesafe_sdk import AsyncTypeSafeClient
    t0 = time.time()
    ix = Isnad()
    if MODE != "knockout":
        # Only the shortlist mode searches. In knockout mode Jev reads the Arabic of every text
        # directly - measured to match English descriptions too - so the embedding model, its
        # matrices and PyTorch are never touched, and a small host can run the service.
        ix.lang_index("ar")
        ix.embed_query("تهيئة")  # load the model now, not on the first user's request
    STATE["ix"] = ix
    STATE["lock"] = threading.Lock()
    STATE["jev"] = AsyncTypeSafeClient()
    STATE["translators"] = json.load(
        open(os.path.join(ROOT, "data", "translators.json"), encoding="utf-8"))
    STATE["cache"] = OrderedDict()
    STATE["corpus"] = knockout.Corpus(ix) if MODE == "knockout" else None
    # One pacer for the whole process: concurrent searches share the organisation's token limit.
    STATE["pacer"] = knockout.Pacer()
    # A full read costs ~3.5M tokens, so answers persist across restarts and deploys.
    try:
        saved = json.load(open(CACHE_FILE, encoding="utf-8"))
        if saved.get("version") == CACHE_VERSION:
            for k, v in saved.get("answers", {}).items():
                STATE["cache"][k] = v
    except Exception:
        pass
    STATE["hits"] = defaultdict(deque)
    STATE["ready_s"] = round(time.time() - t0, 1)
    yield
    await STATE["jev"].aclose()


app = FastAPI(title="Isnad", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ISNAD_ALLOWED_ORIGINS",
                                             "http://localhost:3000").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class SearchIn(BaseModel):
    q: str = Field(..., min_length=MIN_QUERY_CHARS, max_length=MAX_QUERY_CHARS)


def _client(request):
    """The reader's address for the rate limit; 403 if a proxy secret is set and not presented."""
    if PROXY_SECRET:
        if not hmac.compare_digest(request.headers.get("x-isnad-proxy", ""), PROXY_SECRET):
            raise HTTPException(403, "forbidden")
        fwd = request.headers.get("x-isnad-client-ip")
        if fwd:
            return fwd.split(",")[0].strip()
    peer = request.client.host if request.client else "unknown"
    return (request.headers.get("x-forwarded-for") or peer).split(",")[0].strip()


def _limited(ip):
    now = time.time()
    dq = STATE["hits"][ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return True
    dq.append(now)
    return False


# A "translation" that is mostly Arabic letters, in a language not written in Arabic script, is not
# a translation: 502 Bengali hadith entries are (al-Bukhari 6114's is only the Arabic chapter
# heading "لقول الله تعالى ..."), counted 2026-10-06. Shown, it was labelled "the published
# Bengali translation". No translation is better than a wrong one; the entry still serves search.
_ARABIC_LETTER = re.compile(r"[\u0600-\u06FF]")
_LETTER = re.compile(r"\w")


def _mostly_arabic(text):
    n = len(_LETTER.findall(text))
    return n > 0 and len(_ARABIC_LETTER.findall(text)) / n > 0.5


def _translation(rec, lang):
    """The published translation in the reader's language, with its translator, or nothing.
    Isnad never produces a translation of its own."""
    if not lang or lang == "ar":
        return None
    text = (rec.get("translations") or {}).get(lang)
    if not text or (lang != "ur" and _mostly_arabic(text)):
        return None
    tr = STATE["translators"]
    if rec["kind"] == "ayah":
        meta = tr["quran"].get(lang, {})
    else:
        meta = tr["hadith"].get(lang, {}).get(rec.get("collection_key"), {})
    author = meta.get("author") or ""
    return {"lang": lang, "text": text,
            "translator": None if author in ("", "Unknown") else author,
            "edition": meta.get("edition")}


def _shape(rec, lang):
    """Only what the interface shows. Field names are stable; the web app depends on them."""
    if rec is None:
        return None
    kind = rec["kind"]
    return {
        "id": rec["id"],
        "kind": kind,
        "ref": rec["ref"],
        "collection": rec.get("collection"),
        "surah_name": rec.get("surah_name"),
        "ayah": rec.get("ayah"),
        "number": rec.get("number"),
        "matn": rec.get("matn") or rec.get("text"),
        "sanad": rec.get("sanad") if kind == "hadith" else None,
        "commentary": rec.get("commentary") or None,
        "grade": rec.get("grade"),
        "grade_basis": rec.get("grade_basis"),
        "severity": rec.get("severity"),
        "action": rec.get("action"),
        "scope": rec.get("scope"),
        # The grader who supplied the display label, and every other named ruling beside it.
        "graders": [{"grader": g.get("grader_ar") or g.get("grader"),
                     "grade": g.get("grade_ar") or g.get("grade")}
                    for g in (rec.get("graders") or [])],
        "variants": [{"id": v["id"], "ref": v["ref"], "grade": v.get("grade")}
                     for v in (rec.get("variants") or [])],
        "translation": _translation(rec, lang),
        "matched_language": rec.get("matched_language"),
        "verify_url": rec.get("verify_url"),
    }


@app.get("/api/health")
async def health():
    ix = STATE.get("ix")
    return {"ok": ix is not None, "records": len(ix.recs) if ix else 0,
            "languages": sorted(ix.meta.get("languages", {})) if ix else [],
            "model": ix.meta.get("model") if ix else None,
            "encoder": ix.encoder if ix else None,
            "decision_model": cascade.MODEL, "mode": MODE,
            "texts_jev_reads": len(STATE["corpus"].items) if STATE.get("corpus") else cascade.NET,
            "cached_answers": len(STATE.get("cache") or {}),
            "ready_seconds": STATE.get("ready_s")}


@app.post("/api/search")
async def search(body: SearchIn, request: Request):
    q = " ".join(body.q.split())
    if len(q) < MIN_QUERY_CHARS:
        raise HTTPException(422, "query too short")
    ip = _client(request)
    if _limited(ip):
        raise HTTPException(429, "rate limited")

    cache = STATE["cache"]
    if q in cache:
        cache.move_to_end(q)
        hit = dict(cache[q])
        hit["cached"] = True
        return hit

    return await _answer(q)



def _save_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        json.dump({"version": CACHE_VERSION, "answers": dict(STATE["cache"])},
                  open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        pass


async def _answer(q, progress=None):
    """Run the decision for one query and shape the response. Shared by both endpoints."""
    cache = STATE["cache"]
    if q in cache:
        cache.move_to_end(q)
        hit = dict(cache[q])
        hit["cached"] = True
        return hit

    ix = STATE["ix"]
    t0 = time.time()

    def _run_search():
        # The embedding model is not safe to drive from several threads at once.
        with STATE["lock"]:
            return ix.search(q, k=cascade.NET)

    try:
        if MODE == "knockout":
            # No shortlist: Jev reads every text. Search is only used to detect the language
            # for the translation shown beside the answer.
            from _lang import detect
            lang = detect(q)
            t_search = 0.0
            t1 = time.time()
            d = await knockout.run(q, ix, STATE["corpus"], STATE["jev"], STATE["pacer"],
                                   progress=progress)
            cands = d.pop("_candidates", []) if isinstance(d, dict) else []
        else:
            surah = ix.named_surah(q)
            found = None if surah else ix.lookup(q)
            if found:
                # A citation ("البقرة 255", "مسلم 2564") is answered from the reference itself.
                # No match percentage: nothing was judged, so none is shown.
                from _lang import detect
                recs = found.pop("records")
                lang = detect(q) if any(ch.isalpha() for ch in q) else "ar"
                cands, t_search, t1 = recs, (time.time() - t0) * 1000, time.time()
                if len(recs) == 1:
                    d = cascade._result("confident", recs[0], None, None, 1.0, 0, 0, 0)
                else:
                    d = cascade._result("topic", None, None, None, 1.0, 0, 0, 0)
                    d["topic"] = [{"record": r, "relevance": 1.0} for r in recs]
                d["lookup"] = found
            elif surah:
                # A surah named on its own is looked up, not judged: its verses, in order.
                cands, t_search, lang, t1 = surah, (time.time() - t0) * 1000, "ar", time.time()
                d = cascade._result("topic", None, None, None, 1.0, 0, 0, 0)
                d["topic"] = [{"record": r, "relevance": 1.0} for r in surah[:cascade.TOPIC_MAX]]
                d["surah"] = {"name": surah[0].get("surah_name"), "verses": len(surah)}
            else:
                cands = await asyncio.to_thread(_run_search)
                t_search = (time.time() - t0) * 1000
                lang = cands[0]["query_language"] if cands else None
                t1 = time.time()
                d = await cascade.run(q, cands, client=STATE["jev"])
    except Exception as e:
        # Do not hand over a text without a decision.
        return {
            "query": q, "query_language": None, "verdict": "decision_unavailable",
            "confidence": None, "specific_enough": None, "result": None, "alternatives": [],
            "topic": [], "error": type(e).__name__,
            "timing_ms": {"search": None, "decide": None,
                          "total": round((time.time() - t0) * 1000)},
        }
    t_decide = (time.time() - t1) * 1000

    by_id = {c["id"]: c for c in cands}
    if d.get("record"):
        by_id.setdefault(d["record"]["id"], d["record"])
    chosen = d["record"]["id"] if d["record"] else None
    family = set(d.get("family") or [])
    alts = sorted(((rid, p) for rid, p in (d.get("probabilities") or {}).items()
                   if rid != chosen and rid not in family and rid in by_id
                   and p >= ALT_MIN_PROB),
                  key=lambda kv: -kv[1])[:ALTERNATIVES]
    if d["record"] and family:
        seen = {v["id"] for v in (d["record"].get("variants") or [])}
        d["record"]["variants"] = list(d["record"].get("variants") or []) + [
            {"id": rid, "ref": by_id[rid]["ref"], "grade": by_id[rid].get("grade")}
            for rid in family if rid in by_id and rid not in seen]
    if d.get("record") is not None:
        d["record"]["matched_language"] = lang

    # A quotation whose words differ from the source's: which of the reader's words are not in it
    # (cascade.wording). Every listed copy of the report counts, so a wording found in another
    # collection is not marked.
    missing = None
    rec = d.get("record")
    if rec and d["verdict"] in ("confident", "tentative") and lang == "ar" and not d.get("lookup"):
        copies = [rec] + [by_id.get(v["id"]) or ix.display(v["id"])
                          for v in rec.get("variants") or []]
        missing = cascade.wording(q, [c for c in copies if c])

    out = {
        "query": q,
        "query_language": lang,
        "mode": MODE,
        "verdict": d["verdict"],
        "confidence": round(d["confidence"], 3) if d["confidence"] is not None else None,
        "specific_enough": round(d["specific_enough"], 3),
        "fatwa_request": d.get("fatwa_request"),
        "ruling": d.get("ruling"),
        # A question about Islam that is not a ruling: where its answer is (an approved reference).
        "refer": d.get("refer"),
        # Outside what Isnad does ("judge_people"): said plainly, with no texts.
        "scope": d.get("scope"),
        "surah": d.get("surah"),
        # A citation looked up rather than searched: what was asked for.
        "lookup": d.get("lookup"),
        # Positions of the reader's quoted words that the text does not have (see above).
        "wording": {"missing": missing} if missing else None,
        "result": _shape(d["record"], lang),
        "alternatives": [dict(_shape(by_id[rid], lang), probability=round(p, 3))
                         for rid, p in alts],
        "topic": [dict(_shape(t["record"], lang), relevance=round(t["relevance"], 3))
                  for t in (d.get("topic") or [])],
        "jev": {"rounds": d["jev_rounds"], "texts_read": d.get("texts_read", d["net"]),
                "groups": d["groups"], "confidence": d.get("jev_confidence"),
                "merged_copies": len(family),
                # Jev is charged per input token; a citation lookup uses none.
                "input_tokens": d.get("input_tokens", 0)},
        "timing_ms": {"search": round(t_search) if t_search else None,
                      "decide": round(t_decide), "total": round((time.time() - t0) * 1000)},
        "cached": False,
    }
    cache[q] = out
    if len(cache) > CACHE_SIZE:
        cache.popitem(last=False)
    # Only a full read is worth keeping across restarts (~3.5M tokens an answer). In the default
    # mode nothing a reader types is written to disk: the answers live in memory only. On Vercel
    # the write failed silently anyway (read-only file system); now it is not attempted.
    if MODE == "knockout":
        _save_cache()
    return out


@app.post("/api/search/stream")
async def search_stream(body: SearchIn, request: Request):
    """Same answer as /api/search, as Server-Sent Events: progress while Jev reads every text,
    then the result. A ~40 second read is only acceptable if the reader can see it working."""
    q = " ".join(body.q.split())
    ip = _client(request)
    if _limited(ip):
        raise HTTPException(429, "rate limited")

    queue: asyncio.Queue = asyncio.Queue()
    total = len(STATE["corpus"].items) if STATE.get("corpus") else 0

    def progress(stage, done, n_groups):
        texts = min(total, done * knockout.GROUP) if stage == "round1" else total
        queue.put_nowait({"type": "progress", "stage": stage, "done": done, "of": n_groups,
                          "texts_read": texts, "texts_total": total})

    async def worker():
        try:
            res = await _answer(q, progress=progress)
            await queue.put({"type": "result", "data": res})
        except Exception as e:  # pragma: no cover
            await queue.put({"type": "error", "error": type(e).__name__})

    async def events():
        task = asyncio.create_task(worker())
        yield f"data: {json.dumps({'type': 'start', 'texts_total': total})}\n\n"
        while True:
            ev = await queue.get()
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if ev["type"] in ("result", "error"):
                break
        await task

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
