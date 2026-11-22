"""Age of each genus as English Wikipedia's taxobox gives it (``fossil_range``).

PBDB's first and last appearance spans every occurrence ever filed under a genus,
including isolated teeth later reassigned and synonyms, so it is often far too wide
(*Stegosaurus* 161.5-93.9 Ma; Wikipedia: Kimmeridgian-Tithonian, 155-145 Ma). The
taxobox range is curated and comes from the same article revision the page's text
cites, so the site shows it first and keeps PBDB's as "fossil record in PBDB"
(ALCANCE.md, Phase 7). Read from the local cache of genus articles
(``paleo ingest genus-texts``) and written to ``derived/ranges/fossil_ranges.json``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import mwparserfromhell as mw

# ICS stages (oldest Ma, youngest Ma, English), International Chronostratigraphic Chart
# 2023/09, with the same period boundaries as paleo.site.terms.TIME_UNITS.
STAGES: list[tuple[float, float, str]] = [
    (486.85, 477.1, "Tremadocian"), (477.1, 471.3, "Floian"), (471.3, 469.4, "Dapingian"),
    (469.4, 458.2, "Darriwilian"), (458.2, 452.8, "Sandbian"), (452.8, 445.2, "Katian"),
    (445.2, 443.1, "Hirnantian"), (443.1, 440.5, "Rhuddanian"), (440.5, 438.6, "Aeronian"),
    (438.6, 432.9, "Telychian"), (432.9, 430.6, "Sheinwoodian"), (430.6, 426.7, "Homerian"),
    (426.7, 425.0, "Gorstian"), (425.0, 422.7, "Ludfordian"), (422.7, 419.62, "Pridoli"),
    (419.62, 413.02, "Lochkovian"), (413.02, 410.62, "Pragian"), (410.62, 393.47, "Emsian"),
    (393.47, 387.95, "Eifelian"), (387.95, 382.31, "Givetian"), (382.31, 372.15, "Frasnian"),
    (372.15, 358.86, "Famennian"), (358.86, 346.7, "Tournaisian"), (346.7, 330.9, "Visean"),
    (330.9, 323.4, "Serpukhovian"), (323.4, 315.2, "Bashkirian"), (315.2, 307.0, "Moscovian"),
    (307.0, 303.7, "Kasimovian"), (303.7, 298.9, "Gzhelian"), (298.9, 293.52, "Asselian"),
    (293.52, 290.1, "Sakmarian"), (290.1, 283.3, "Artinskian"), (283.3, 274.4, "Kungurian"),
    (274.4, 266.9, "Roadian"), (266.9, 264.28, "Wordian"), (264.28, 259.51, "Capitanian"),
    (259.51, 254.14, "Wuchiapingian"), (254.14, 251.902, "Changhsingian"),
    (251.902, 249.9, "Induan"), (249.9, 247.2, "Olenekian"), (247.2, 241.464, "Anisian"),
    (241.464, 237.0, "Ladinian"), (237.0, 227.3, "Carnian"), (227.3, 205.7, "Norian"),
    (205.7, 201.4, "Rhaetian"), (201.4, 199.5, "Hettangian"), (199.5, 192.9, "Sinemurian"),
    (192.9, 184.2, "Pliensbachian"), (184.2, 174.7, "Toarcian"), (174.7, 170.9, "Aalenian"),
    (170.9, 168.2, "Bajocian"), (168.2, 165.3, "Bathonian"), (165.3, 161.5, "Callovian"),
    (161.5, 154.8, "Oxfordian"), (154.8, 149.2, "Kimmeridgian"), (149.2, 145.0, "Tithonian"),
    (145.0, 137.05, "Berriasian"), (137.05, 132.6, "Valanginian"),
    (132.6, 125.77, "Hauterivian"), (125.77, 121.4, "Barremian"), (121.4, 113.2, "Aptian"),
    (113.2, 100.5, "Albian"), (100.5, 93.9, "Cenomanian"), (93.9, 89.8, "Turonian"),
    (89.8, 86.3, "Coniacian"), (86.3, 83.6, "Santonian"), (83.6, 72.1, "Campanian"),
    (72.1, 66.0, "Maastrichtian"), (66.0, 61.6, "Danian"), (61.6, 59.2, "Selandian"),
    (59.2, 56.0, "Thanetian"), (56.0, 47.8, "Ypresian"), (47.8, 41.2, "Lutetian"),
    (41.2, 37.71, "Bartonian"), (37.71, 33.9, "Priabonian"), (33.9, 27.82, "Rupelian"),
    (27.82, 23.03, "Chattian"), (23.03, 20.44, "Aquitanian"), (20.44, 15.98, "Burdigalian"),
    (15.98, 13.82, "Langhian"), (13.82, 11.63, "Serravallian"), (11.63, 7.246, "Tortonian"),
    (7.246, 5.333, "Messinian"), (5.333, 3.6, "Zanclean"), (3.6, 2.58, "Piacenzian"),
    (2.58, 1.8, "Gelasian"), (1.8, 0.774, "Calabrian"), (0.774, 0.129, "Chibanian"),
]  # fmt: skip
_STAGE = {name.lower(): (old, young, name) for old, young, name in STAGES}
_STAGE_RE = re.compile(
    r"\b(?:(early|middle|late|lower|upper)\s+)?(" + "|".join(n for _, _, n in STAGES) + r")\b",
    re.IGNORECASE,
)
_QUALIFIER = {"lower": "Early", "upper": "Late", "early": "Early", "middle": "Middle",
              "late": "Late"}  # fmt: skip
_RANGE_TEMPLATES = {"fossil range", "fossilrange", "geological range", "geologic range"}
_TAXOBOXES = ("taxobox", "speciesbox", "subspeciesbox", "infraspeciesbox")
# "(possible Albian records)", "Possible middle Campanian record": doubtful extensions
# the taxobox names but does not count.
_DOUBT = re.compile(r"\(?\bpossib(?:le|ly)\b[^)\n]*\)?", re.IGNORECASE)


def _number(value: str) -> float | None:
    try:
        ma = float(value.strip().lstrip("~").replace(",", ""))
    except ValueError:
        return None
    return ma if 0 <= ma <= 540 else None


def _units() -> dict[str, tuple[float, float]]:
    """Periods and epochs by name (lower case) -> (oldest, youngest) Ma."""
    from paleo.site.terms import TIME_UNITS

    return {en.lower(): (old, young) for old, young, en, _ in TIME_UNITS}


def _stage_age(value: str) -> tuple[float, float] | None:
    """Boundaries of a stage, epoch or period named in place of a number."""
    value = mw.parse(value).strip_code().strip().lower()
    if stage := _STAGE.get(value):
        return stage[0], stage[1]
    return _units().get(value)


def _units_in(text: str) -> tuple[float, float] | None:
    """Oldest and youngest Ma of the epochs and periods a label names ("Late
    Jurassic", "Pliocene - Pleistocene"); doubtful records left out."""
    units = _units()
    names = sorted(units, key=len, reverse=True)
    text = _DOUBT.sub(" ", text).lower().replace("upper ", "late ").replace("lower ", "early ")
    found = [units[n] for n in names if re.search(rf"\b{re.escape(n)}\b", text)]
    # "late jurassic" also contains "jurassic": keep the narrowest units only
    found = [
        u
        for u in found
        if not any(
            o != u and u[0] >= o[0] and u[1] <= o[1] and (u[0] - u[1]) > (o[0] - o[1])
            for o in found
        )
    ]
    if not found:
        return None
    return max(u[0] for u in found), min(u[1] for u in found)


def _range_from_template(t: Any) -> tuple[float | None, float | None]:
    """(oldest, youngest) Ma of {{Fossil range|oldest|youngest|...}}; a stage name in
    place of a number stands for that stage's boundaries."""
    positional = [str(p.value).strip() for p in t.params if not p.showkey]
    values: list[float] = []
    for i, raw in enumerate(positional[:2]):
        if (ma := _number(raw)) is not None:
            values.append(ma)
        elif ages := _stage_age(raw):
            values.append(ages[0] if i == 0 else ages[1])
        else:
            break
    if not values:
        return None, None
    if len(values) == 1 and len(positional) == 1 and (ages := _stage_age(positional[0])):
        return ages  # {{Fossil range|Quaternary}}: the whole unit
    oldest = values[0]
    youngest = values[1] if len(values) > 1 else values[0]
    return (oldest, youngest) if oldest >= youngest else (youngest, oldest)


def _stages_in(text: str) -> list[str]:
    """Stage names in the label, oldest first, with their qualifier ("Late
    Maastrichtian"); doubtful records left out."""
    found: list[tuple[float, str]] = []
    for q, name in _STAGE_RE.findall(_DOUBT.sub(" ", text)):
        old, _, canonical = _STAGE[name.lower()]
        found.append((old, f"{_QUALIFIER[q.lower()]} {canonical}" if q else canonical))
    found.sort(key=lambda x: -x[0])
    return [name for _, name in found]


_PARAM = re.compile(r"^\s*\|\s*fossil_range\s*=(.*?)(?=^\s*\||^\s*\}\})", re.M | re.S)


def _fossil_range_values(wikitext: str) -> list[Any]:
    """The taxobox's ``fossil_range`` value, parsed. Some taxoboxes have markup the
    parser can't close (an unbalanced template further down): then the parameter is
    read from its own lines."""
    code = mw.parse(wikitext)
    for box in code.filter_templates(recursive=True):
        name = str(box.name).strip().lower()
        if any(name.endswith(t) for t in _TAXOBOXES) and box.has("fossil_range"):
            return [box.get("fossil_range").value]
    if m := _PARAM.search(wikitext):
        return [mw.parse(m.group(1))]
    return []


def parse_fossil_range(wikitext: str) -> dict[str, Any] | None:
    """The taxobox's fossil range: oldest and youngest Ma, the oldest and youngest
    stage its label names (None when it names none) and the label as plain text."""
    for value in _fossil_range_values(wikitext):
        oldest = youngest = None
        label_parts: list[str] = []
        for node in value.nodes:
            if isinstance(node, mw.nodes.Template):
                tname = str(node.name).strip().lower().replace("_", " ").removesuffix("/linked")
                if tname in _RANGE_TEMPLATES and oldest is None:
                    oldest, youngest = _range_from_template(node)
                    # stage names in place of numbers name the interval too
                    named = [mw.parse(str(p.value)).strip_code().strip()
                             for p in node.params if not p.showkey][:2]  # fmt: skip
                    label_parts.extend(n for n in named if n.lower() in _STAGE)
                    # a fourth positional argument is the label to display
                    extra = [str(p.value) for p in node.params if not p.showkey][2:3]
                    label_parts.extend(mw.parse(x).strip_code() for x in extra)
            elif isinstance(node, mw.nodes.Tag):
                continue  # <ref>, <br />
            else:
                label_parts.append(mw.parse(str(node)).strip_code())
        label = re.sub(r"\s+", " ", " ".join(label_parts)).strip(" ,;~")
        stages = _stages_in(label)
        if oldest is None and stages:
            oldest = _STAGE[stages[0].split()[-1].lower()][0]
            youngest = _STAGE[stages[-1].split()[-1].lower()][1]
        if oldest is None and (units := _units_in(label)):
            oldest, youngest = units
        if oldest is None:
            return None
        return {
            "max_ma": oldest,
            "min_ma": youngest,
            "early_interval": stages[0] if stages else None,
            "late_interval": stages[-1] if stages else None,
            "label": label or None,
        }
    return None


def fossil_ranges(cache_root: Path | None = None) -> list[dict[str, Any]]:
    """One row per genus whose stored English article has a parsable fossil range."""
    from paleo.ingest.genus_articles import text_store

    store = text_store("en", cache_root)
    rows = []
    for genus in store.stored_keys():
        latest = store.latest(genus)
        payload = latest["payload"] if latest else {}
        if not payload.get("found") or not payload.get("wikitext"):
            continue
        if parsed := parse_fossil_range(payload["wikitext"]):
            rows.append({"taxon_name": genus, **parsed, "title": payload.get("title"),
                         "revid": payload.get("revid")})  # fmt: skip
    return rows


def ranges_path(derived_root: Path) -> Path:
    return derived_root / "ranges" / "fossil_ranges.json"


def write_ranges(rows: list[dict[str, Any]], derived_root: Path) -> Path:
    path = ranges_path(derived_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path
