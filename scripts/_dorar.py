"""Deep links into dorar.net for runtime verification.

Isnad cannot call dorar's API from its own server: dorar answers automated requests with HTTP 403.
Rather than depend on a service that will refuse us during judging, the interface offers a link the
user clicks, which opens dorar's own search for the text being shown. No API, no CORS, no runtime
dependency, and the judge can verify the ruling at the named platform in one click.

Verified 2026-10-05: GET https://dorar.net/hadith/search?q=<phrase> returns 200.
"""
import re
from urllib.parse import quote

SEARCH = "https://dorar.net/hadith/search?q={}"
WORDS = 8

# The fiqh encyclopedia the Reference Framework approves for general fiqh ("أي كتاب معتمد في الفقه
# على أحد المذاهب الفقهية الأربعة أو منصة dorar.net/feqhia"). A ruling question is referred there;
# Isnad states no ruling itself. URL pattern from the encyclopedia's own search form,
# <form action="/feqhia/search" method="get"> with field q (Internet Archive copy of
# dorar.net/feqhia, 2025), the same pattern as the hadith search verified above.
FIQH_HOME = "https://dorar.net/feqhia"
FIQH_SEARCH = "https://dorar.net/feqhia/search?q={}"
# Words a ruling question is phrased with. They name no subject, and dorar's search is lexical:
# "ماحكم الزنا" would otherwise search for the word "ماحكم".
RULING_WORDS = {"ما", "ماهو", "ماهي", "هو", "هي", "حكم", "ماحكم", "الحكم", "هل", "يجوز", "يحل",
                "يحرم", "لي", "لنا", "في", "عن", "الشرع", "الشرعي", "شرعا", "الإسلام", "الاسلام",
                "حلال", "حرام", "أو", "او"}
ARABIC_WORD = re.compile(r"[ء-يً-ْ]+")


def fiqh_url(question):
    """A search for the subject of a ruling question in the fiqh encyclopedia; its home page when
    the question has no Arabic subject words, because the encyclopedia is in Arabic."""
    words = [w for w in ARABIC_WORD.findall(question or "") if w not in RULING_WORDS]
    if not words:
        return FIQH_HOME
    return FIQH_SEARCH.format(quote(" ".join(words[:6])))


def verify_url(matn_plain):
    """A dorar search link for a hadith matn. Uses a short distinctive window, because dorar's
    search is lexical and a whole long matn returns nothing."""
    w = (matn_plain or "").split()
    if not w:
        return None
    start = max(0, (len(w) - WORDS) // 2)
    return SEARCH.format(quote(" ".join(w[start:start + WORDS])))
