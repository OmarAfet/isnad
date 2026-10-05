"""Surah names and verse counts, loaded from cached authoritative metadata.

Deliberately not hardcoded: a hand-written list of 114 names is easy to get wrong, and this is a
tool about textual precision. The cache comes from the Quran.com API (api.quran.com v4
/chapters?language=ar) and carries verses_count, which 02_normalize.py uses to verify that the
downloaded Quran text has exactly the expected number of ayahs in every surah.
"""
import json, os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "raw", "quran-chapters.json")
_CACHE = None


def _load():
    global _CACHE
    if _CACHE is None:
        with open(_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        ch = raw["chapters"] if isinstance(raw, dict) else raw
        _CACHE = {c["id"]: {"name": c["name_arabic"], "verses": c["verses_count"]} for c in ch}
        if len(_CACHE) != 114:
            raise SystemExit(f"expected 114 surahs in {_PATH}, found {len(_CACHE)}")
    return _CACHE


def surah_name(n):
    return _load()[n]["name"]


def verses_count(n):
    return _load()[n]["verses"]


def all_surahs():
    return _load()
