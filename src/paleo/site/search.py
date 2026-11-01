"""Search index of the site, one JSON file per language (read by static/search.js).

Every taxon carries weighted fields in both languages (a Spanish page also finds
"Late Cretaceous"), Spanish and English forms of its scientific names, and the
facets the results can be filtered by. Matching (accents, plurals, prefixes and
typos) happens in the browser.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from paleo.site import terms

# Field -> weight: a match in the name counts more than one in the authors.
WEIGHTS = {"name": 10, "alias": 8, "clade": 6, "group": 5, "time": 4, "place": 3, "people": 2}


def _both(fn: Callable[[str | None, str], str | None], value: str | None) -> list[str]:
    return [v for v in {value, fn(value, "es"), fn(value, "en")} if v]


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
    age = terms.age(taxon.get("age_text"), lang) or terms.interval(
        taxon.get("early_interval"), lang
    )
    country = (taxon.get("countries") or [None])[0]
    return {
        "n": name,
        "u": url,
        "img": taxon.get("image_url"),
        "sil": taxon.get("image_source") == "phylopic",
        "new": taxon.get("page_type") == "new",
        "meta": " · ".join(
            v for v in (terms.group(group_key, lang), age, terms.place(country, lang)) if v
        ),
        "f": {k: sorted(set(v)) for k, v in fields.items() if v},
        "facets": {
            "clade": taxon.get("family_name") or taxon.get("order_name"),
            "group": terms.group(group_key, lang, plural=True),
            "time": [es if lang == "es" else en for en, es in periods] or None,
            "place": terms.place(country, lang),
        },
    }


def build_index(taxa: list[dict[str, Any]], lang: str, url: Callable[[str], str]) -> dict[str, Any]:
    return {
        "weights": WEIGHTS,
        "taxa": [entry(t, lang, url(t["taxon_key"])) for t in taxa],
    }
