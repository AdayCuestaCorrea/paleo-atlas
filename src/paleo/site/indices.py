"""Encyclopedia indices (ALCANCE.md §11, page 5): genera by group, by period and by
country. Built from the taxa already loaded for the site; no extra queries.

A genus is listed under every period and epoch its fossil record overlaps (from the
PBDB first and last appearances), and under every country where PBDB has an
occurrence of it.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from paleo.site import terms


def unit_key(english: str) -> str:
    return re.sub(r"[^a-z]+", "-", english.lower()).strip("-")


# terms.TIME_UNITS lists each period followed by its epochs.
_NAMES: dict[str, tuple[str, str]] = {}  # key -> (English, Spanish)
_PERIOD_EPOCHS: dict[str, list[str]] = {}  # period key -> epoch keys, oldest first
_period = ""
for _old, _young, _en, _es in terms.TIME_UNITS:
    _NAMES[unit_key(_en)] = (_en, _es)
    if _en in terms.PERIODS:
        _period = unit_key(_en)
        _PERIOD_EPOCHS[_period] = []
    else:
        _PERIOD_EPOCHS[_period].append(unit_key(_en))


def unit_name(key: str, lang: str) -> str:
    en, es = _NAMES[key]
    return es if lang == "es" else en


def is_genus_page(taxon: dict[str, Any]) -> bool:
    return taxon.get("page_type") == "genus" or (
        taxon.get("taxon_rank") == "genus" and taxon.get("page_type") == "new"
    )


@dataclass
class Indices:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = field(default_factory=dict)
    periods: dict[str, list[tuple[str, list[dict[str, Any]]]]] = field(default_factory=dict)
    countries: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    genera: int = 0

    def group_count(self, key: str) -> int:
        return sum(len(v) for v in self.groups.get(key, {}).values())

    def period_count(self, key: str) -> int:
        return len({t["taxon_key"] for _, taxa in self.periods.get(key, []) for t in taxa})


def build_indices(taxa: list[dict[str, Any]], group_order: list[str]) -> Indices:
    """Indices of the genus pages. ``group_order`` lists the groups as in the scope seed."""
    genera = sorted((t for t in taxa if is_genus_page(t)), key=lambda t: t["taxon_name"])
    out = Indices(genera=len(genera))

    by_group: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for t in genera:
        if t.get("taxon_group"):
            by_group[t["taxon_group"]][t.get("family_name") or ""].append(t)
    for key in [g for g in group_order if g in by_group] + sorted(set(by_group) - set(group_order)):
        families = by_group[key]
        # Families alphabetically; genera without a family in PBDB at the end.
        out.groups[key] = {f: families[f] for f in sorted(families, key=lambda f: (f == "", f))}

    by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in genera:
        for en, _ in terms.time_units(
            t.get("first_appearance_max_ma"), t.get("last_appearance_min_ma")
        ):
            by_unit[unit_key(en)].append(t)
    for period, epochs in _PERIOD_EPOCHS.items():
        sections = [(e, by_unit[e]) for e in epochs if by_unit.get(e)]
        if sections:
            out.periods[period] = sections

    by_country: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in genera:
        for code in t.get("country_codes") or []:
            by_country[code.lower()].append(t)
    out.countries = dict(sorted(by_country.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    return out
