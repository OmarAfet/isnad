"""Isnad retrieval: hybrid dense + lexical search over the verified corpus.

Isnad SELECTS a text. It never writes one. Everything this module returns is a record that exists
in the corpus, carrying its own reference and the ruling of a named scholar.

Why hybrid, measured rather than assumed (eval/retrieval_eval.py):
    dense only   hit@1 4/11
    lexical only hit@1 4/11
    hybrid       hit@1 8/11
Each half covers the other's blind spot. Dense finds a paraphrase that shares no words with the
text; lexical finds the half-remembered quotation that dense flattens into a cloud of similar
sentences. Fusing is a weighted sum over min-max normalized scores, not reciprocal rank fusion:
RRF was tried first and demoted a correct dense rank-1 to rank 7 when the lexical ranking had
nothing useful to say about that query.
"""
import json, math, os, sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "data", "index")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from _arabic import normalize, plain          # noqa: E402
from _dorar import verify_url                 # noqa: E402

# Fusion chosen by eval/fusion_sweep.py over the full index, not by preference:
#   z-score        dense 0.70 / lex 0.30   hit@1 7/13   MRR 0.616   <- selected
#   global min-max dense 0.70 / lex 0.30   hit@1 6/13   MRR 0.579
#   pool min-max   dense 0.50 / lex 0.50   hit@1 6/13   MRR 0.560
#   RRF                                    hit@1 4/13   MRR 0.449
#   dense only                             hit@1 3/13   MRR 0.322
#   lexical only                           hit@1 4/13   MRR 0.382
# z-score asks "how unusual is this score for this corpus", which survives the fact that e5's
# cosines all sit in a narrow high band. Min-max inside the candidate pool rescales that band to
# fill 0..1 and turns its noise into confident-looking separation.
DENSE_W = 0.70
LEX_W = 0.30
CANDIDATES = 400      # per retriever, before fusion

# The user usually says which kind of text they want. Honouring that is free accuracy: a query
# containing "الآية" asking for 2:255 was losing to a hadith that quotes 2:255.
# Cues are written in normalized form, because that is what normalize() produces: ة folds to ه
# and آ to ا, so "آية" arrives as "ايه" and "سورة" as "سوره".
AYAH_CUES = {"ايه", "الايه", "ايات", "الايات", "سوره", "قران", "القران", "مصحف",
             "verse", "verses", "ayah", "ayat", "quran", "quranic", "surah", "surat"}
HADITH_CUES = {"حديث", "الحديث", "احاديث", "الاحاديث", "سنه", "السنه", "نبوي", "روي", "اخرج",
               "hadith", "hadeeth", "sunnah", "narration", "narrated", "prophet"}
KIND_BOOST = 0.10     # added when the record matches the stated kind, subtracted when it clashes


class Bm25:
    """Okapi BM25 over normalized Arabic tokens."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        toks = [d.split() for d in docs]
        self.dl = np.array([len(t) for t in toks], dtype=np.float32)
        self.avgdl = float(self.dl.mean()) or 1.0
        self.post = defaultdict(list)
        for i, t in enumerate(toks):
            for w, c in Counter(t).items():
                self.post[w].append((i, c))
        self.N = len(docs)
        self.idf = {w: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5))
                    for w, p in self.post.items()}

    def score(self, query_norm):
        s = np.zeros(self.N, dtype=np.float32)
        for w in set(query_norm.split()):
            p = self.post.get(w)
            if not p:
                continue
            idf = self.idf[w]
            for i, c in p:
                s[i] += idf * c * (self.k1 + 1) / (
                    c + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl))
        return s


def _minmax(x):
    lo, hi = float(x.min()), float(x.max())
    return (x - lo) / (hi - lo) if hi > lo else np.zeros_like(x)


def _zscore(x):
    m, sd = float(x.mean()), float(x.std())
    return (x - m) / sd if sd > 0 else np.zeros_like(x)


def wanted_kind(query_norm):
    """Which kind of text the query asks for, or None if it does not say."""
    toks = set(query_norm.split())
    a, h = toks & AYAH_CUES, toks & HADITH_CUES
    if a and not h:
        return "ayah"
    if h and not a:
        return "hadith"
    return None


class Isnad:
    def __init__(self, index_dir=INDEX, model=None, device=None):
        self.meta = json.load(open(os.path.join(index_dir, "meta.json"), encoding="utf-8"))
        self.E = np.load(os.path.join(index_dir, "embeddings.f16.npy"), mmap_mode="r")
        with open(os.path.join(index_dir, "records.jsonl"), encoding="utf-8") as f:
            self.recs = [json.loads(l) for l in f]
        if len(self.recs) != self.E.shape[0]:
            raise SystemExit(f"index mismatch: {len(self.recs)} records vs {self.E.shape[0]} rows")
        self.bm25 = Bm25([r["match_text"] for r in self.recs])
        self._model = model
        self._device = device

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            import torch
            dev = self._device or ("mps" if torch.backends.mps.is_available() else "cpu")
            self._model = SentenceTransformer(self.meta["model"], device=dev)
        return self._model

    def embed_query(self, q):
        v = self.model.encode([self.meta["query_prefix"] + q], normalize_embeddings=True,
                              convert_to_numpy=True)[0]
        return v.astype(np.float32)

    def search(self, query, k=10, dense_w=DENSE_W, lex_w=LEX_W):
        """Return the k best candidates, each with the scores that produced it.

        The per-retriever scores are returned alongside the fused one because the decision layer
        above needs them: a result that both halves agree on is a different kind of answer from
        one only lexical overlap liked, and the user is owed that distinction.
        """
        qn = normalize(query)
        qv = self.embed_query(query)
        dense = self.E.astype(np.float32) @ qv
        lex = self.bm25.score(qn)

        # Fuse inside a candidate pool, not across all 40,389 rows. Global min-max is set by the
        # single best and single worst score in the corpus, which flattens every real candidate
        # into the same narrow band and lets one retriever's noise outvote the other's signal.
        n = len(dense)
        d_top = np.argpartition(-dense, min(CANDIDATES, n - 1))[:CANDIDATES]
        nz = np.nonzero(lex)[0]
        l_top = nz[np.argsort(-lex[nz])[:CANDIDATES]] if nz.size else np.empty(0, dtype=int)
        pool = np.unique(np.concatenate([d_top, l_top])) if l_top.size else np.unique(d_top)

        fused = dense_w * _zscore(dense)[pool] + lex_w * _zscore(lex)[pool]

        kind = wanted_kind(qn)
        if kind:
            # Scaled by the pool's own spread: KIND_BOOST is a fraction of the gap between the
            # best and worst candidate, not a fixed number of z-units, so it nudges rather than
            # overrides.
            same = np.array([self.recs[i]["kind"] == kind for i in pool])
            spread = float(fused.max() - fused.min()) or 1.0
            fused = fused + np.where(same, KIND_BOOST, -KIND_BOOST) * spread

        order = pool[np.argsort(-fused)][:k]
        rank_score = {int(i): float(sc) for i, sc in zip(pool[np.argsort(-fused)],
                                                         np.sort(fused)[::-1])}
        out = []
        for i in order:
            r = self.recs[i]
            out.append({
                **{key: r.get(key) for key in
                   ("id", "kind", "collection", "ref", "text", "matn", "grade", "grade_note",
                    "severity", "severity_ar", "action", "scope", "graders", "section",
                    "surah_name", "ayah", "number", "grade_basis")},
                "score": rank_score[int(i)],
                "dense": float(dense[i]),
                "lexical": float(lex[i]),
                "asked_for": kind,
                "verify_url": verify_url(plain(r.get("matn", ""))) if r["kind"] == "hadith" else None,
            })
        return out
