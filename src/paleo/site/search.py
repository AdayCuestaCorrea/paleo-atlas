"""Search index of the site, one JSON file per language (read by static/search.js).

Every taxon carries weighted fields in both languages (a Spanish page also finds
"Late Cretaceous"), Spanish and English forms of its scientific names, and the
facets the results can be filtered by. Matching (accents, plurals, prefixes and
typos) happens in the browser.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from paleo.site import terms

# Field -> weight: a match in the name counts more than one in the authors.
WEIGHTS = {"name": 10, "alias": 8, "clade": 6, "group": 5, "time": 4, "place": 3, "people": 2}


def _both(fn: Callable[[str | None, str], str | None], value: str | None) -> list[str]:
    return [v for v in {value, fn(value, "es"), fn(value, "en")} if v]


def card_meta(taxon: dict[str, Any], lang: str) -> str:
    """The line under a card's name: group · age · first country."""
    age = terms.age(taxon.get("age_text"), lang) or terms.interval(
        taxon.get("early_interval"), lang
    )
    country = (taxon.get("countries") or [None])[0]
    values = (terms.group(taxon.get("taxon_group"), lang), age, terms.place(country, lang))
    return " · ".join(v for v in values if v)


def entry(taxon: dict[str, Any], lang: str, url: str) -> dict[str, Any]:
    name = taxon["taxon_name"]
    genus = taxon.get("genus_name") or name.split(" ")[0]
    clades = [
        c for c in (taxon.get("family_name"), taxon.get("order_name"), taxon.get("class_name")) if c
    ]
    units = terms.time_units(
        taxon.get("first_appearance_max_ma"), taxon.get("last_appearance_min_ma")
    )
    group_key = taxon.get("taxon_group")
    groups = [g for lg in ("es", "en") for g in terms.GROUPS.get(group_key, {}).get(lg, ())]
    time = [
        *_both(terms.age, taxon.get("age_text")),
        *_both(terms.interval, taxon.get("early_interval")),
        *_both(terms.interval, taxon.get("late_interval")),
        *[u for pair in units for u in pair],
    ]
    places = [p for c in (taxon.get("countries") or []) for p in _both(terms.place, c)]
    places += [p for r in (taxon.get("regions") or []) for p in _both(terms.place, r)]
    places += _both(terms.locality, taxon.get("type_locality"))
    people = [str(v) for v in (taxon.get("name_authors"), taxon.get("naming_year")) if v]
    fields = {
        "name": [name, genus],
        "alias": terms.genus_aliases(genus),
        "clade": clades + [a for c in clades for a in terms.clade_aliases(c)],
        "group": groups,
        "time": time,
        "place": places,
        "people": people,
    }
    periods = [u for u in units if u[0] in terms.PERIODS]
    if not periods and taxon.get("age_text"):  # dated only in words
        periods = [
            (en, es) for _, _, en, es in terms.TIME_UNITS
            if en in terms.PERIODS and en in taxon["age_text"]
        ]  # fmt: skip
        time += [name for pair in periods for name in pair]
    country = (taxon.get("countries") or [None])[0]
    return {
        "n": name,
        "u": url,
        "img": taxon.get("image_url"),
        "sil": taxon.get("image_source") == "phylopic",
        "new": taxon.get("page_type") == "new",
        "meta": card_meta(taxon, lang),
        "f": {k: sorted(set(v)) for k, v in fields.items() if v},
        "facets": {
            "clade": taxon.get("family_name") or taxon.get("order_name"),
            "group": terms.group(group_key, lang, plural=True),
            "time": [es if lang == "es" else en for en, es in periods] or None,
            "place": terms.place(country, lang),
        },
    }


FACETS = ["clade", "group", "time", "place"]
# Image URLs share a few long prefixes: stored as "<prefix number>|<rest>".
IMAGE_PREFIXES = [
    "https://images.phylopic.org/images/",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/",
    "https://upload.wikimedia.org/wikipedia/commons/",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/",  # appended: older ids stay valid
]


def _page_key(name: str) -> str:
    """The dbt macro taxon_key: lowercase, every run of other characters as "-"."""
    return re.sub(r"[^A-Za-z0-9]+", "-", name.strip()).lower()


def _short_image(url: str) -> str:
    for i, prefix in enumerate(IMAGE_PREFIXES):
        if url.startswith(prefix):
            return f"{i}|{url[len(prefix) :]}"
    return url


class _Terms:
    """Shared string table: the index stores each distinct text once (group names,
    periods, silhouettes and meta lines repeat across thousands of taxa)."""

    def __init__(self) -> None:
        self.ids: dict[str, int] = {}

    def __call__(self, text: str | None) -> int | None:
        if text is None:
            return None
        if text not in self.ids:
            self.ids[text] = len(self.ids)
        return self.ids[text]

    def many(self, texts: list[str] | None) -> list[int]:
        return [] if texts is None else [self(t) for t in texts]

    def table(self) -> list[str]:
        return list(self.ids)


def _compact(e: dict[str, Any], key: str, terms_: _Terms) -> list[Any]:
    """[name, meta, image, flags, fields, facets, key?] with every text as a term id;
    fields and facets in the order of WEIGHTS and FACETS. flags: 1 silhouette, 2 new."""
    facets = []
    for k in FACETS:
        v = e["facets"].get(k)
        facets.append(terms_.many(v) if isinstance(v, list) else terms_(v))
    out = [
        e["n"],
        terms_(e["meta"] or None),
        terms_(_short_image(e["img"])) if e["img"] else None,
        (1 if e["sil"] else 0) + (2 if e["new"] else 0),
        [terms_.many(e["f"].get(field)) for field in WEIGHTS],
        facets,
    ]
    if key != _page_key(e["n"]):
        out.append(key)
    return out


def build_index(taxa: list[dict[str, Any]], lang: str, url: Callable[[str], str]) -> dict[str, Any]:
    """Compact index (format 2): texts in one shared table, fields by position, URLs
    as page keys (left out when they follow from the name). search.js expands it."""
    terms_ = _Terms()
    prefix, suffix = url("KEY").split("KEY")
    entries = [_compact(entry(t, lang, url(t["taxon_key"])), t["taxon_key"], terms_) for t in taxa]
    return {
        "v": 2,
        "weights": WEIGHTS,
        "fields": list(WEIGHTS),
        "facets": FACETS,
        "images": IMAGE_PREFIXES,
        "url": [prefix, suffix],
        "terms": terms_.table(),
        "taxa": entries,
    }
