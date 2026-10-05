"""Isnad HTTP API.

One endpoint does the work: POST /api/search runs stage one (hybrid search over every language
surface) and stage two (the Jev tournament), and returns either one text with its source, its
ruling and a calibrated confidence, or an explicit no-match.

User-facing sentences live in the web app, not here. The API returns codes (verdict, severity,
action) so that all interface copy sits in one place, in one register, and is reviewed together.

Run: uvicorn api.app:app --port 8000   (from the isnad/ directory)
"""
import asyncio
import json
import os
import sys
import threading
import time
from collections import OrderedDict, defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cascade                    # noqa: E402
from decide import load_key       # noqa: E402
from search import Isnad          # noqa: E402

MAX_QUERY_CHARS = 300
MIN_QUERY_CHARS = 3
CACHE_SIZE = 512                  # judges will try the same examples; answer those from memory
RATE_LIMIT = 30                   # requests per IP per minute; the Jev key is real money
ALTERNATIVES = 3
ALT_MIN_PROB = 0.05

STATE = {}


@asynccontextmanager
async def lifespan(app):
    if not load_key():
        raise RuntimeError("TYPESAFE_API_KEY is not set and no .env was found")
    from typesafe_sdk import AsyncTypeSafeClient
    t0 = time.time()
    ix = Isnad()
    ix.lang_index("ar")
    ix.embed_query("تهيئة")      # load the model now, not on the first user's request
    STATE["ix"] = ix
    STATE["lock"] = threading.Lock()
    STATE["jev"] = AsyncTypeSafeClient()
    STATE["translators"] = json.load(
        open(os.path.join(ROOT, "data", "translators.json"), encoding="utf-8"))
    STATE["cache"] = OrderedDict()
    STATE["hits"] = defaultdict(deque)
    STATE["ready_s"] = round(time.time() - t0, 1)
    yield
    await STATE["jev"].close()


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


def _limited(ip):
    now = time.time()
    dq = STATE["hits"][ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return True
    dq.append(now)
    return False


def _translation(rec, lang):
    """The published translation in the reader's language, with its translator, or nothing.
    Isnad never produces a translation of its own."""
    if not lang or lang == "ar":
        return None
    text = (rec.get("translations") or {}).get(lang)
    if not text:
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
            "decision_model": cascade.MODEL, "ready_seconds": STATE.get("ready_s")}


@app.post("/api/search")
async def search(body: SearchIn, request: Request):
    q = " ".join(body.q.split())
    if len(q) < MIN_QUERY_CHARS:
        raise HTTPException(422, "query too short")
    ip = (request.headers.get("x-forwarded-for") or request.client.host).split(",")[0].strip()
    if _limited(ip):
        raise HTTPException(429, "rate limited")

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

    cands = await asyncio.to_thread(_run_search)
    t_search = (time.time() - t0) * 1000
    lang = cands[0]["query_language"] if cands else None

    t1 = time.time()
    try:
        d = await cascade.run(q, cands, client=STATE["jev"])
    except Exception as e:  # the decision service is down or refused the request
        # Do not hand over a text without a decision. Show the search results as exactly what
        # they are: unconfirmed candidates.
        return {
            "query": q, "query_language": lang, "verdict": "decision_unavailable",
            "confidence": None, "specific_enough": None, "result": None,
            "alternatives": [_shape(c, lang) for c in cands[:ALTERNATIVES]],
            "error": type(e).__name__,
            "timing_ms": {"search": round(t_search), "decide": None,
                          "total": round((time.time() - t0) * 1000)},
        }
    t_decide = (time.time() - t1) * 1000

    by_id = {c["id"]: c for c in cands}
    chosen = d["record"]["id"] if d["record"] else None
    family = set(d.get("family") or [])
    # Copies merged into the chosen report are not "other texts"; they join its variants.
    alts = sorted(((rid, p) for rid, p in (d.get("probabilities") or {}).items()
                   if rid != chosen and rid not in family and rid in by_id
                   and p >= ALT_MIN_PROB),
                  key=lambda kv: -kv[1])[:ALTERNATIVES]
    if d["record"] and family:
        seen = {v["id"] for v in (d["record"].get("variants") or [])}
        d["record"]["variants"] = list(d["record"].get("variants") or []) + [
            {"id": rid, "ref": by_id[rid]["ref"], "grade": by_id[rid].get("grade")}
            for rid in family if rid in by_id and rid not in seen]

    out = {
        "query": q,
        "query_language": lang,
        "verdict": d["verdict"],
        "confidence": round(d["confidence"], 3) if d["confidence"] is not None else None,
        "specific_enough": round(d["specific_enough"], 3),
        "fatwa_request": d.get("fatwa_request"),
        "result": _shape(d["record"], lang),
        "alternatives": [dict(_shape(by_id[rid], lang), probability=round(p, 3))
                         for rid, p in alts],
        # Topic mode: the description names a subject, so every relevant text is listed with its
        # source and ruling, sound texts first, and the reader chooses.
        "topic": [dict(_shape(t["record"], lang), relevance=round(t["relevance"], 3))
                  for t in (d.get("topic") or [])],
        "jev": {"rounds": d["jev_rounds"], "net": d["net"], "groups": d["groups"],
                "confidence": d.get("jev_confidence"), "merged_copies": len(family)},
        "timing_ms": {"search": round(t_search), "decide": round(t_decide),
                      "total": round((time.time() - t0) * 1000)},
        "cached": False,
    }
    cache[q] = out
    if len(cache) > CACHE_SIZE:
        cache.popitem(last=False)
    return out
