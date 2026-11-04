"""Home page (ALCANCE.md §11, page 2): the curiosity carousel and the explorer.

The explorer filters every page of the atlas by period, group and country in the
browser. One rule decides those three facets for every page (``facets``); for the
genus pages it gives exactly what the encyclopedia indices list (indices.py), so a
figure on the home page and the index it links to agree.

The data goes in a small JSON per language (``build_explore``), read by
static/home.js. The first state (this year's new taxa) is also drawn in the HTML,
so the page works without JavaScript and without downloading the JSON.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

from paleo.site import terms
from paleo.site.indices import unit_key
from paleo.site.search import IMAGE_PREFIXES, _page_key, _short_image, _Terms, card_meta

# Periods, oldest first: (key, English, Spanish, oldest Ma, youngest Ma).
PERIODS = [
    (unit_key(en), en, es, old, young)
    for old, young, en, es in terms.TIME_UNITS
    if en in terms.PERIODS
]
PERIOD_KEYS = [p[0] for p in PERIODS]
# Symbols of the International Chronostratigraphic Chart, for narrow segments.
PERIOD_SYMBOLS = dict(
    zip(PERIOD_KEYS, ["O", "S", "D", "C", "P", "Tr", "J", "K", "Pg", "N", "Q"], strict=True)
)

# Card flags in the JSON (bits).
SILHOUETTE, NEW, CURIOSITIES, PHOTO = 1, 2, 4, 8

CAROUSEL_SIZE = 8
MAX_SENTENCE = 240  # characters: a slide shows one or two lines of large type
CARD_WIDTH = 330  # Commons thumbnail width for cards (the pages store 960 px)

_THUMB = re.compile(r"^(https://[^/]+/wikipedia/commons/thumb/\w/\w\w/[^/]+)/\d+px-([^?]+)(\?.*)?$")


def thumb(url: str | None, width: int = CARD_WIDTH) -> str | None:
    """A Wikimedia Commons thumbnail at ``width`` pixels, without the tracking query
    the API adds. Other URLs (PhyloPic, originals) are returned unchanged."""
    if not url:
        return url
    match = _THUMB.match(url)
    if not match:
        return url
    return f"{match.group(1)}/{width}px-{match.group(2)}"


def is_photo(taxon: dict[str, Any]) -> bool:
    """A Commons image (photo, drawing or skeletal), not a PhyloPic silhouette."""
    return bool(taxon.get("image_url")) and taxon.get("image_source") != "phylopic"


def facets(taxon: dict[str, Any]) -> tuple[list[str], str | None, list[str]]:
    """(period keys, group, lowercase country codes) of a page.

    Periods: those its fossil record overlaps (PBDB ages in Ma), as in the indices;
    a page dated only in words ("Early Cretaceous (Albian)") takes the periods its
    age names. Countries: PBDB's country codes; a page without them (the new taxa)
    takes the countries of its description, by name."""
    keys = [
        unit_key(en)
        for en, _ in terms.time_units(
            taxon.get("first_appearance_max_ma"), taxon.get("last_appearance_min_ma")
        )
        if en in terms.PERIODS
    ]
    if not keys and taxon.get("age_text"):
        keys = [key for key, en, *_ in PERIODS if en in taxon["age_text"]]
    codes = [c.lower() for c in taxon.get("country_codes") or []]
    if not codes:
        codes = [c for c in map(terms.country_code, taxon.get("countries") or []) if c]
    return keys, taxon.get("taxon_group"), list(dict.fromkeys(codes))


def new_order(taxa: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, int]:
    """Rank of each new taxon, newest first: by the date its description was seen
    (the tracked events), then by name; those without such an event go last."""
    seen: dict[str, dt.date] = {}
    for e in events:  # newest first
        if e["event_type"] == "description":
            seen.setdefault(e["taxon_key"], e["event_date"])
    new = [t for t in taxa if t.get("page_type") == "new"]
    new.sort(key=lambda t: (t["taxon_key"] not in seen, t["taxon_name"]))
    new.sort(key=lambda t: seen.get(t["taxon_key"], dt.date.min), reverse=True)
    return {t["taxon_key"]: i for i, t in enumerate(new)}


# ------------------------------------------------------------------ curiosities


def _sentence(text: dict[str, Any] | None, genus: str) -> str | None:
    """The sentence a slide shows: the first curiosity that names the genus and is
    short enough; otherwise the first one short enough."""
    if not text:
        return None
    sentences = [
        s["text"]
        for section in text["sections"]
        if section["section"] == "curiosities"
        for s in section["sentences"]
        if len(s["text"]) <= MAX_SENTENCE
    ]
    named = [s for s in sentences if genus in s]
    return (named or sentences or [None])[0]


def pick_curiosities(
    taxa: list[dict[str, Any]],
    texts: dict[tuple[str, str], dict[str, Any]],
    built_on: dt.date,
    n: int = CAROUSEL_SIZE,
) -> list[dict[str, Any]]:
    """The carousel: ``n`` genera with a curiosity in both languages and a credited
    Commons image, the same in Spanish and English. The pool is in a fixed order and
    the build date picks where it starts, so the first slide (the curiosity of the
    day) changes with every daily build."""
    pool = []
    for t in sorted(taxa, key=lambda t: t["taxon_key"]):
        if t.get("page_type") != "genus" or not is_photo(t):
            continue
        if not (t.get("image_author") and t.get("image_license")):
            continue
        genus = t["taxon_name"]
        text = {lang: _sentence(texts.get((t["taxon_key"], lang)), genus) for lang in ("es", "en")}
        if text["es"] and text["en"]:
            pool.append({"taxon": t, "text": text})
    if not pool:
        return []
    start = built_on.toordinal() % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(min(n, len(pool)))]


def group_pictures(
    taxa: list[dict[str, Any]], texts: dict[tuple[str, str], dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """One picture per group: the genus with the longest verified text that has a
    credited Commons image (the best documented animal of the group)."""

    def sentences(t: dict[str, Any]) -> int:
        text = texts.get((t["taxon_key"], "es")) or {"sections": []}
        return sum(len(s["sentences"]) for s in text["sections"])

    best: dict[str, dict[str, Any]] = {}
    for t in taxa:
        group = t.get("taxon_group")
        if t.get("page_type") != "genus" or not group or not is_photo(t):
            continue
        if not t.get("image_author"):
            continue
        rank = (sentences(t), t["taxon_name"])
        current = best.get(group)
        if current is None or rank > (sentences(current), current["taxon_name"]):
            best[group] = t
    return best


# --------------------------------------------------------------------- explorer


def explore_entries(
    taxa: list[dict[str, Any]],
    *,
    groups: list[str],
    curiosities: set[str],
    ranks: dict[str, int],
) -> list[dict[str, Any]]:
    """Every page with its facets, flags and new-taxon rank (language independent)."""
    out = []
    for t in taxa:
        periods, group, countries = facets(t)
        flags = (
            (SILHOUETTE if t.get("image_source") == "phylopic" else 0)
            | (NEW if t.get("page_type") == "new" else 0)
            | (CURIOSITIES if t["taxon_key"] in curiosities else 0)
            | (PHOTO if is_photo(t) else 0)
        )
        out.append({
            "taxon": t, "periods": periods, "countries": countries, "flags": flags,
            "group": group if group in groups else None, "rank": ranks.get(t["taxon_key"]),
        })  # fmt: skip
    return out


def build_explore(
    entries: list[dict[str, Any]],
    lang: str,
    url: Callable[[str], str],
    *,
    groups: list[str],
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    """Compact JSON of the explorer for one language (read by static/home.js):

    taxa: [name, meta, image, flags, group, periods, countries, rank, key?] where
    meta and image are ids into ``terms``, group an index into ``groups``, periods
    a bit mask over ``periods`` (oldest first), countries indices into
    ``countries`` and rank the order of a new taxon (newest first) or null."""
    terms_ = _Terms()
    prefix, suffix = url("KEY").split("KEY")
    used = Counter(c for e in entries for c in e["countries"])
    codes = [c for c in sorted(used) if c in centroids]
    index = {c: i for i, c in enumerate(codes)}
    rows = []
    for e in entries:
        t = e["taxon"]
        image = thumb(t.get("image_url"))
        row: list[Any] = [
            t["taxon_name"],
            terms_(card_meta(t, lang) or None),
            terms_(_short_image(image)) if image else None,
            e["flags"],
            groups.index(e["group"]) if e["group"] else None,
            sum(1 << PERIOD_KEYS.index(k) for k in e["periods"]),
            [index[c] for c in e["countries"] if c in index],
            e["rank"],
        ]
        if t["taxon_key"] != _page_key(t["taxon_name"]):
            row.append(t["taxon_key"])
        rows.append(row)
    return {
        "v": 1,
        "periods": [
            [k, es if lang == "es" else en, old, young] for k, en, es, old, young in PERIODS
        ],
        "groups": [[g, terms.group(g, lang, plural=True) or g] for g in groups],
        "countries": [
            [c, terms.country_name(c, lang), *[round(v, 2) for v in centroids[c]]] for c in codes
        ],
        "images": IMAGE_PREFIXES,
        "url": [prefix, suffix],
        "terms": terms_.table(),
        "taxa": rows,
    }


def initial_counts(entries: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    """Counts per period, group and country of this year's new taxa: the explorer's
    first state, drawn in the HTML."""
    out: dict[str, Counter[str]] = {"time": Counter(), "group": Counter(), "place": Counter()}
    for e in entries:
        if not e["flags"] & NEW:
            continue
        out["time"].update(e["periods"])
        if e["group"]:
            out["group"][e["group"]] += 1
        out["place"].update(e["countries"])
    return out
