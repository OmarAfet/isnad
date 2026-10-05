#!/usr/bin/env python3
"""Stage the API for Vercel: only what the service reads at runtime, in deploy/api/.

WHY A STAGE. The repository holds the corpus pipeline, the evaluation, the web app and about
2 GB of raw and intermediate data; the service reads 1.2 GB of it. Vercel's free plan refuses any
single uploaded file over 100 MB (measured 2026-10-05: one 150 MB file failed with "File size
limit exceeded (100 MB)", two 60 MB files deployed). Two runtime files are larger - display.db
(314 MB) and the int8 model (279 MB) - so they travel in 90 MB parts, and build.py joins them on
Vercel's build machine, checking each against the SHA-256 recorded here, before the function is
packaged.

The service runs without PyTorch: queries are encoded by the model author's int8 ONNX export
(src/search.py, ISNAD_ENCODER=onnx), measured against PyTorch in eval/compare_encoders.py.

Usage: python scripts/stage_api.py [--out deploy/api]
Then:  cd deploy/api && vercel deploy --scope omar-afet
"""
import hashlib, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "deploy", "api")
if "--out" in sys.argv:
    OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])

PART = 90 * 1024 * 1024
LIMIT = 100 * 1000 * 1000      # the per-file upload limit, read conservatively

# Pinned to the versions measured in .venv. No torch, no sentence-transformers.
DEPENDENCIES = [
    "fastapi==0.142.2",
    "pydantic==2.13.5",
    "numpy==2.5.3",
    "onnxruntime==1.30.0",
    "tokenizers==0.23.2",
    "typesafe-sdk==0.7.2",
]

FILES = (
    ["api/app.py"]
    + [f"src/{m}.py" for m in ("search", "cascade", "decide", "knockout")]
    + [f"scripts/{m}.py" for m in ("_arabic", "_dorar", "_lang", "_surfaces", "_common")]
    # No saved answers: every answer the deployed service gives comes from the deployed code.
    + ["data/translators.json",
       "data/models/e5-base-onnx/onnx/model_qint8_avx512_vnni.onnx",
       "data/models/e5-base-onnx/onnx/tokenizer.json"]
    + sorted(f"data/index/{f}" for f in os.listdir(os.path.join(ROOT, "data", "index")))
)

PYPROJECT = """[project]
name = "isnad-api"
version = "1.0.0"
requires-python = ">=3.13,<3.14"
dependencies = [
{deps}
]

[tool.vercel]
entrypoint = "service.app:app"

[tool.vercel.scripts]
build = "python build.py"
"""

BUILD = '''"""Runs on Vercel's build machine after dependencies install, before the function is packaged.
Joins the files uploaded in parts - the free plan refuses any single upload over 100 MB - and
checks each against the SHA-256 recorded by scripts/stage_api.py. A mismatch fails the build."""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for rel, info in json.load(open(os.path.join(HERE, "parts.json"))).items():
    h = hashlib.sha256()
    with open(os.path.join(HERE, rel), "wb") as out:
        for part in info["parts"]:
            p = os.path.join(HERE, part)
            with open(p, "rb") as f:
                while chunk := f.read(1 << 20):
                    out.write(chunk)
                    h.update(chunk)
            os.remove(p)
    if h.hexdigest() != info["sha256"]:
        sys.exit(f"build.py: {rel} does not match its recorded SHA-256")
    print(f"build.py: joined {rel} from {len(info['parts'])} parts, SHA-256 verified")
'''


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def target(rel):
    # The FastAPI app lives in service/, not api/: Vercel gives a top-level api/ directory its own
    # meaning (one function per file), and the entrypoint is named explicitly in pyproject.toml.
    return "service/app.py" if rel == "api/app.py" else rel


def main():
    print(f"RAN: python scripts/stage_api.py --out {os.path.relpath(OUT, ROOT)}")
    link = os.path.join(OUT, ".vercel")            # the project link survives a re-stage
    kept = os.path.join(os.path.dirname(OUT), ".vercel-api-link")
    if os.path.isdir(link):
        shutil.rmtree(kept, ignore_errors=True)
        shutil.move(link, kept)
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    if os.path.isdir(kept):
        shutil.move(kept, link)
    parts, total = {}, 0
    for rel in FILES:
        src = os.path.join(ROOT, rel)
        dst = os.path.join(OUT, target(rel))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        size = os.path.getsize(src)
        total += size
        if size <= LIMIT:
            # Data files are hard-linked: instant, no second gigabyte on disk, and nobody edits
            # them by hand. Code is copied, so an edit made while an upload is running cannot
            # change a file the upload is reading.
            try:
                if rel.endswith(".py"):
                    raise OSError
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
            continue
        names = []
        with open(src, "rb") as f:
            i = 0
            while chunk := f.read(PART):
                name = f"{target(rel)}.part{i:02d}"
                with open(os.path.join(OUT, name), "wb") as out:
                    out.write(chunk)
                names.append(name)
                i += 1
        parts[target(rel)] = {"sha256": sha256(src), "size": size, "parts": names}
        print(f"split  {rel}  {size / 1e6:6.1f} MB -> {len(names)} parts")
    open(os.path.join(OUT, "service", "__init__.py"), "w").close()
    json.dump(parts, open(os.path.join(OUT, "parts.json"), "w"), indent=1)
    open(os.path.join(OUT, "build.py"), "w").write(BUILD)
    open(os.path.join(OUT, ".python-version"), "w").write("3.13\n")
    # Named, not detected: a project made with `vercel project add` has no framework, and the
    # first deploy (2026-10-05) was served as static files - /api/health 404, pyproject.toml 200.
    json.dump({"$schema": "https://openapi.vercel.sh/vercel.json", "framework": "fastapi"},
              open(os.path.join(OUT, "vercel.json"), "w"), indent=1)
    # `vercel link` and `vercel env pull` write secrets to .env.local; it must never be uploaded.
    open(os.path.join(OUT, ".vercelignore"), "w").write(".env*\n")
    open(os.path.join(OUT, "pyproject.toml"), "w").write(
        PYPROJECT.format(deps="\n".join(f'  "{d}",' for d in DEPENDENCIES)))
    biggest = max(os.path.getsize(os.path.join(d, f))
                  for d, _, fs in os.walk(OUT) for f in fs)
    print(f"staged {len(FILES)} files, {total / 1e6:.0f} MB, largest upload {biggest / 1e6:.1f} MB"
          f" -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
