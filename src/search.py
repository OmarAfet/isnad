"""Isnad stage one: hybrid dense + lexical search across language surfaces.

Isnad SELECTS a text. It never writes one. Every result is a record that exists in the corpus,
carrying its own reference and the ruling of a named scholar.

HYBRID, measured rather than assumed (eval/fusion_sweep.py, full index):
    dense only   hit@1 3/13      lexical only hit@1 4/13      hybrid 7/13
Each half covers the other's blind spot. Dense finds a paraphrase that shares no word with the
text; lexical finds the half-remembered quotation that dense flattens into a cloud of similar
sentences. Fusion is z-score weighted 0.70/0.30 - chosen over min-max and RRF, which both scored
worse. z-score asks "how unusual is this score for this corpus", which survives the fact that
e5's cosines all sit in a narrow high band.

MANY LANGUAGES, ONE ANSWER. A description in Urdu is matched against the Urdu surface of each
record and still answers with the Arabic, because the Arabic is the text and the translation is
only a way of finding it. Stage one is tuned for RECALL, not for first place: Jev decides which
candidate is right, and it can only choose from what this hands it.
"""
import json, math, os, sqlite3, sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "data", "index")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
from _arabic import normalize, plain, split_commentary   # noqa: E402
from _dorar import verify_url                 # noqa: E402
from _lang import detect                      # noqa: E402
from _surfaces import surface_text            # noqa: E402

DENSE_W = 0.70
LEX_W = 0.30
CANDIDATES = 400          # per retriever per language, before fusion

# The user usually says which kind of text they want, and honouring it is free accuracy: a query
# containing "الآية" was losing 2:255 to a hadith that quotes 2:255.
# The words in each language the battery and the judges' test typed (eval/battery.py): French
# "verset" was missing, so "le verset sur la patience" listed hadith; so was the accusative
# "حديثا", so "أعطني حديثا يثبت ..." was answered with a verse.
AYAH_CUES = {"ايه", "الايه", "ايات", "الايات", "سوره", "قران", "القران", "مصحف", "ايت",
             "verse", "verses", "ayah", "ayat", "quran", "quranic", "surah", "surat",
             "verset", "versets", "coran", "sourate", "ayet", "ayeti", "ayetler", "kuran",
             "suresi", "аят", "аята", "аяте", "аяты", "коран", "сура", "суры"}
HADITH_CUES = {"حديث", "الحديث", "حديثا", "احاديث", "الاحاديث", "سنه", "السنه", "نبوي", "روي",
               "اخرج", "hadith", "hadeeth", "hadis", "hadisi", "hadits", "sunnah", "narration",
               "narrated", "prophet", "хадис", "хадиса", "хадисе", "хадисы"}
KIND_BOOST = 0.10

# REQUEST WORDS. Words that say which kind of text the reader wants, not what the text says. They
# still choose the kind (above); they are dropped from the literal match only. Matched literally,
# "ايه" in "ايه عن النوم" pulled in verses that contain the word "آية" (26:128, 37:14, 19:10), and
# they filled the verse slots while the verses about sleep stayed out (eval/explain.py).
# Only the kind words: dropping function words too ("عن", "the", "about") measured worse on the
# labelled single-text queries, and BM25 already gives them little weight (eval/topic_recall.py).
# "سنه" stays a content word: it is the slumber of 2:255 ("لا تأخذه سنة ولا نوم") as often as Sunnah.
# The phrasing of a ruling question goes too: "حكم" and "الحكمة" (wisdom) share the light10 stem,
# and for "ما حكم الموسيقى" the shortlist filled with hadith on wisdom.
RULING_PHRASE = {"حكم", "الحكم", "ماحكم", "يجوز", "شرعا", "الشرع", "الشرعي"}
REQUEST_WORDS = (AYAH_CUES | HADITH_CUES) - {"سنه", "السنه"} | {"ءايه", "آيه"} | RULING_PHRASE
LEX_CLEAN = True


# WHICH COPY IS SHOWN. A report found in several books shows its copy in al-Bukhari, else in
# Muslim, with the rest under "ورد أيضًا في". "انما الاعمال بالنيات" was answered with Sunan
# al-Nasa'i 3794 while its family held al-Bukhari 54 and Muslim 4927; a reader checking the
# citation, and a judge, expect the Sahihayn first.
BOOK_RANK = {"bukhari": 0, "muslim": 1}


def _book_rank(rid):
    book, _, num = rid.partition(":")
    return BOOK_RANK.get(book, 2), int(num) if num.isdigit() else 10 ** 9


def literal_query(text):
    """The words of the query that the literal match should look for: request words dropped,
    unless nothing else is left."""
    if not LEX_CLEAN:
        return text
    kept = [w for w in text.split() if w not in REQUEST_WORDS]
    return " ".join(kept) if kept else text

# LIGHT STEMMING for the Arabic literal match. The Qur'an writes "نَوۡمࣱ" (2:255), "وَٱلنَّوۡمَ"
# (25:47), "نَوۡمَكُمۡ" (78:9); a reader writes "النوم". As whole tokens they never meet. Larkey,
# Ballesteros and Connell's light10 (SIGIR 2002), the standard light stemmer for Arabic
# retrieval: strip a leading و when 3 letters remain, one article (ال وال بال كال فال لل) when 2
# remain, then the suffixes ها ان ات ون ين يه ه ي each when 2 remain. كم and هم are added, only
# when 3 remain, for "نومكم". Applied to the index and the query alike; dense search is untouched.
STEM_AR = True
_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_AR_SUFFIXES = ("ها", "ان", "ات", "ون", "ين", "يه", "ه", "ي")
_AR_SUFFIXES3 = ("كم", "هم")
_stem_cache = {}


def light_stem(w):
    s = _stem_cache.get(w)
    if s is not None:
        return s
    s = w
    if len(s) > 3 and s.startswith("و"):
        s = s[1:]
    for p in _AR_PREFIXES:
        if s.startswith(p) and len(s) - len(p) >= 2:
            s = s[len(p):]
            break
    for x in _AR_SUFFIXES3:
        if s.endswith(x) and len(s) - len(x) >= 3:
            s = s[:-len(x)]
    for x in _AR_SUFFIXES:
        if s.endswith(x) and len(s) - len(x) >= 2:
            s = s[:-len(x)]
    _stem_cache[w] = s
    return s


def ar_tokens(text):
    return [light_stem(w) for w in text.split()]

# Variant collapsing. The same report sits in several collections - "إنما الأعمال بالنيات" occupies
# seven places here - and handing all seven to a Choice splits the probability mass between them.
# Measured: the correct hadith was selected with confidence 0.22 because six near-identical twins
# were competing with it. The more copies of the right answer existed, the less certain the system
# claimed to be, which is the opposite of what a calibrated number should do.
#
# So variants are collapsed to one representative, which also means the shortlist holds that many
# more DISTINCT texts. The collapsed ids are kept and shown: "ورد أيضًا في..." is useful to a
# reader checking a citation, and it is what distinguishing what the sources support looks like.
VARIANT_CONTAINMENT = 0.80
VARIANT_MIN_TOKENS = 6

# QUERY ENCODER. The index was embedded once, in PyTorch, with multilingual-e5-base. Serving only
# encodes the query - one short text per search - yet PyTorch and the float32 model held 1.1 GB of
# the 2.0 GB the service peaked at (eval/measure_memory.py), and the free host allows 2 GB in all.
# The model's author publishes an int8 ONNX export of the same weights in the same repository
# (intfloat/multilingual-e5-base, onnx/model_qint8_avx512_vnni.onnx, 279 MB), which ONNX Runtime
# runs without PyTorch. Agreement with the PyTorch encoder is measured: eval/compare_encoders.py.
ENCODER = os.environ.get("ISNAD_ENCODER", "torch")
ONNX_DIR = os.environ.get("ISNAD_ONNX_DIR",
                          os.path.join(HERE, "..", "data", "models", "e5-base-onnx", "onnx"))
ONNX_FILE = "model_qint8_avx512_vnni.onnx"
ONNX_REPO, ONNX_REVISION = "intfloat/multilingual-e5-base", "d128750597153bb5987e10b1c3493a34e5a4502a"


class OnnxEncoder:
    """What sentence-transformers computes for this model - mean pooling over the attention mask
    (the model's 1_Pooling/config.json), then L2 normalisation - from ONNX Runtime instead."""

    def __init__(self, model_dir=ONNX_DIR, max_len=256):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.sess = ort.InferenceSession(os.path.join(model_dir, ONNX_FILE),
                                         providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
        self.tok.enable_truncation(max_length=max_len)   # the PyTorch path's max_seq_length
        self.tok.no_padding()

    def encode(self, text):
        e = self.tok.encode(text)
        ids = np.array([e.ids], dtype=np.int64)
        mask = np.array([e.attention_mask], dtype=np.int64)
        h = self.sess.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask})[0]
        v = (h * mask[..., None]).sum(axis=1)[0] / mask.sum()
        return (v / np.linalg.norm(v)).astype(np.float32)


class Bm25:
    def __init__(self, docs, k1=1.5, b=0.75, tokenize=str.split):
        self.k1, self.b = k1, b
        self.tokenize = tokenize
        toks = [tokenize(d) for d in docs]
        self.dl = np.array([len(t) for t in toks], dtype=np.float32)
        self.avgdl = float(self.dl.mean()) or 1.0
        self.post = defaultdict(list)
        for i, t in enumerate(toks):
            for w, c in Counter(t).items():
                self.post[w].append((i, c))
        self.N = len(docs)
        self.idf = {w: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5))
                    for w, p in self.post.items()}

    def score(self, q):
        s = np.zeros(self.N, dtype=np.float32)
        for w in set(self.tokenize(q)):
            p = self.post.get(w)
            if not p:
                continue
            idf = self.idf[w]
            for i, c in p:
                s[i] += idf * c * (self.k1 + 1) / (
                    c + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avgdl))
        return s


def _dense(E, qv, rows=8192):
    """Cosine of the query against a float16 matrix, a slice at a time. Converting the whole
    matrix to float32 at once made a 124 MB temporary per language per search, on a host whose
    whole allowance is 2 GB; a slice of 8,192 rows makes 25 MB and the result is the same."""
    out = np.empty(E.shape[0], dtype=np.float32)
    for i in range(0, E.shape[0], rows):
        out[i:i + rows] = E[i:i + rows].astype(np.float32) @ qv
    return out


def _zscore(x):
    m, sd = float(x.mean()), float(x.std())
    return (x - m) / sd if sd > 0 else np.zeros_like(x)


def wanted_kind(q_tokens):
    a, h = q_tokens & AYAH_CUES, q_tokens & HADITH_CUES
    if a and not h:
        return "ayah"
    if h and not a:
        return "hadith"
    return None


def _match_tokens(ix, rec_index):
    """Tokens of a record's Arabic surface, for variant detection. Cached on first use."""
    cache = ix._tok_cache
    if rec_index in cache:
        return cache[rec_index]
    idx = ix.lang_index("ar")
    pos = ix._ar_pos.get(rec_index)
    toks = set(idx["bm25_docs"][pos].split()) if pos is not None else set()
    cache[rec_index] = toks
    return toks


class Isnad:
    def __init__(self, index_dir=INDEX, device=None, encoder=None):
        self.dir = index_dir
        self.meta = json.load(open(os.path.join(index_dir, "meta.json"), encoding="utf-8"))
        with open(os.path.join(index_dir, "records.jsonl"), encoding="utf-8") as f:
            self.recs = [json.loads(l) for l in f]
        self._by_id = {r["id"]: i for i, r in enumerate(self.recs)}
        self._surahs = None
        self.db = sqlite3.connect(os.path.join(index_dir, "display.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lang = {}          # lang -> {"E","rows","bm25"}; built on first use
        self._tok_cache = {}
        self._ar_pos = {}        # record index -> row position in the Arabic surface
        self._model = None
        self._device = device
        self.encoder = encoder or ENCODER
        self._onnx = None

    # -- lazily loaded pieces: a free tier should hold Arabic plus whatever was just asked for --
    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            import torch
            dev = self._device or ("mps" if torch.backends.mps.is_available() else "cpu")
            self._model = SentenceTransformer(self.meta["model"], device=dev)
            # Half precision on a GPU: one short query per request, so the saving is memory, not
            # time, and memory is what a small host runs out of first.
            if dev != "cpu":
                self._model.half()
            self._model.max_seq_length = 256
        return self._model

    def lang_index(self, lg):
        if lg in self._lang:
            return self._lang[lg]
        emb = os.path.join(self.dir, f"emb_{lg}.f16.npy")
        if not os.path.exists(emb):
            return None
        E = np.load(emb, mmap_mode="r")
        rows = np.load(os.path.join(self.dir, f"rows_{lg}.npy"))
        docs = []
        with open(os.path.join(self.dir, f"surface_{lg}.jsonl"), encoding="utf-8") as f:
            for line in f:
                docs.append(json.loads(line)["t"])
        tok = ar_tokens if (lg == "ar" and STEM_AR) else str.split
        self._lang[lg] = {"E": E, "rows": rows, "bm25": Bm25(docs, tokenize=tok),
                          "bm25_docs": docs}
        if lg == "ar":
            self._ar_pos = {int(r): p for p, r in enumerate(rows)}
        return self._lang[lg]

    def embed_query(self, q):
        if self.encoder == "onnx":
            if self._onnx is None:
                self._onnx = OnnxEncoder()
            return self._onnx.encode(self.meta["query_prefix"] + q)
        v = self.model.encode([self.meta["query_prefix"] + q], normalize_embeddings=True,
                              convert_to_numpy=True)[0]
        return v.astype(np.float32)

    def display(self, rec_id):
        row = self.db.execute("SELECT * FROM display WHERE id=?", (rec_id,)).fetchone()
        if row is None:
            return {}
        return {"text": row["text"], "matn": row["matn"], "sanad": row["sanad"],
                "graders": json.loads(row["graders"] or "[]"),
                "translations": json.loads(row["translations"] or "{}")}

    def search(self, query, k=12, dense_w=DENSE_W, lex_w=LEX_W):
        lang = detect(query)
        langs = ["ar"] if lang == "ar" else ["ar", lang]
        qv = self.embed_query(query)

        best = {}      # record index -> fused score
        via = {}       # record index -> which language surface found it
        for lg in langs:
            idx = self.lang_index(lg)
            if idx is None:
                continue
            dense = _dense(idx["E"], qv)
            lex = idx["bm25"].score(literal_query(surface_text(lg, query)))
            n = len(dense)
            d_top = np.argpartition(-dense, min(CANDIDATES, n - 1))[:CANDIDATES]
            nz = np.nonzero(lex)[0]
            l_top = nz[np.argsort(-lex[nz])[:CANDIDATES]] if nz.size else np.empty(0, int)
            pool = np.unique(np.concatenate([d_top, l_top])) if l_top.size else np.unique(d_top)
            fused = dense_w * _zscore(dense)[pool] + lex_w * _zscore(lex)[pool]
            for p, sc in zip(pool, fused):
                ri = int(idx["rows"][p])
                # A record reachable in two languages keeps its better score; the surfaces are
                # alternative routes to one text, not independent pieces of evidence.
                if sc > best.get(ri, -1e9):
                    best[ri] = float(sc)
                    via[ri] = lg

        if not best:
            return []
        items = np.array(list(best.keys()))
        scores = np.array([best[i] for i in items], dtype=np.float32)

        toks = set(surface_text("ar" if lang in ("ar", "ur") else lang, query).split())
        kind = wanted_kind(toks)
        if kind:
            same = np.array([self.recs[i]["kind"] == kind for i in items])
            spread = float(scores.max() - scores.min()) or 1.0
            scores = scores + np.where(same, KIND_BOOST, -KIND_BOOST) * spread

        # Rank everything, then collapse variants, then take k distinct texts.
        order = np.argsort(-scores)
        out = []
        kept_tokens = []
        for o in order:
            if len(out) >= k:
                break
            ri = int(items[o])
            rec = self.recs[ri]
            disp = self.display(rec["id"])
            toks = set((rec.get("surah_name") and "" or "").split())
            toks = set(_match_tokens(self, ri))
            dup_of = None
            for pos, prev in enumerate(kept_tokens):
                # Only hadith collapse into hadith. A narration that quotes an ayah shares its
                # wording almost exactly, and collapsing on wording alone folded 2:255 into Abu
                # Dawud 4003 - the Qur'an filed as a "variant" of a report that cites it. The
                # ayah is the primary source and always stands on its own.
                if rec["kind"] != "hadith" or out[pos]["kind"] != "hadith":
                    continue
                d = min(len(toks), len(prev))
                if d >= VARIANT_MIN_TOKENS and len(toks & prev) / d >= VARIANT_CONTAINMENT:
                    dup_of = pos
                    break
            if dup_of is not None:
                out[dup_of].setdefault("variants", []).append(
                    {"id": rec["id"], "ref": rec["ref"], "grade": rec.get("grade")})
                continue
            out.append(self._full(ri, float(scores[o]), via[ri], lang, kind))
            kept_tokens.append(toks)
        for pos, r in enumerate(out):
            if r["kind"] != "hadith" or not r["variants"]:
                continue
            best = min([r["id"]] + [v["id"] for v in r["variants"]], key=_book_rank)
            if _book_rank(best)[0] >= _book_rank(r["id"])[0]:
                continue
            new = self._full(self._by_id[best], r["score"], r["matched_language"], lang, kind)
            new["variants"] = [{"id": r["id"], "ref": r["ref"], "grade": r.get("grade")}] + \
                [v for v in r["variants"] if v["id"] != best]
            out[pos] = new
        return out

    def _full(self, ri, score, via_lang, lang, kind):
        """A record as stage two and the reader get it: display text, the compiler's notes off
        the matn, the dorar link."""
        r = dict(self.recs[ri])
        r.update(self.display(r["id"]))
        # The compiler's notes come off the text and travel beside it, so Jev judges, and the
        # reader sees, the Prophet's words alone, and al-Tirmidhi's own grading is still shown.
        if r.get("kind") == "hadith":
            r["matn"], r["commentary"] = split_commentary(r.get("matn") or "")
        r["score"] = score
        r["matched_language"] = via_lang
        r["query_language"] = lang
        r["wanted_kind"] = kind
        r["variants"] = []
        r["verify_url"] = (verify_url(plain(r.get("matn") or ""))
                           if r["kind"] == "hadith" else None)
        return r

    # A SURAH NAMED ON ITS OWN ("سورة الإخلاص") is a lookup, not a search: the judges' battery got
    # "nothing found" for it. Its verses come back in order; Jev is not asked.
    SURAH_FILLER = {"اقرا", "ابي", "ابغي", "عطني", "اعطني", "هات", "وش", "ايش", "اعرض", "نص",
                    "كامله", "كلها", "ابحث", "عن"}

    def named_surah(self, query):
        toks = normalize(query).split()
        cue = next((t for t in toks if t in ("سوره", "السوره")), None)
        if cue is None:
            return None
        if self._surahs is None:
            self._surahs = defaultdict(list)       # normalized name -> record indexes in order
            for i, r in enumerate(self.recs):
                if r["kind"] == "ayah" and r.get("surah_name"):
                    name = normalize(r["surah_name"])
                    for key in {name, name[2:] if name.startswith("ال") else name}:
                        self._surahs[key].append(i)
        at = toks.index(cue)
        after = toks[at + 1:]
        for n in (2, 1):
            key = " ".join(after[:n])
            if len(after) >= n and key in self._surahs:
                rest = toks[:at] + after[n:]
                if all(t in self.SURAH_FILLER or t in REQUEST_WORDS for t in rest):
                    idx = sorted(self._surahs[key], key=lambda i: self.recs[i]["ayah"])
                    return [self._full(i, 1.0, "ar", "ar", "ayah") for i in idx]
        return None
