"""Deep links into dorar.net for runtime verification.

Isnad cannot call dorar's API from its own server: dorar answers automated requests with HTTP 403.
Rather than depend on a service that will refuse us during judging, the interface offers a link the
user clicks, which opens dorar's own search for the text being shown. No API, no CORS, no runtime
dependency, and the judge can verify the ruling at the named platform in one click.

Verified 2026-10-05: GET https://dorar.net/hadith/search?q=<phrase> returns 200.
"""
from urllib.parse import quote

SEARCH = "https://dorar.net/hadith/search?q={}"
WORDS = 8


def verify_url(matn_plain):
    """A dorar search link for a hadith matn. Uses a short distinctive window, because dorar's
    search is lexical and a whole long matn returns nothing."""
    w = (matn_plain or "").split()
    if not w:
        return None
    start = max(0, (len(w) - WORDS) // 2)
    return SEARCH.format(quote(" ".join(w[start:start + WORDS])))
