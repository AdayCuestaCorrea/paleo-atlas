"""Resolve taxon names against the Paleobiology Database (PBDB, CC BY 4.0).

Names come from the parsed Wikipedia pages: new taxa (and their genus), taxa
mentioned in the notes ("A member of the family Peirosauridae") and taxa linked
or italicised in research items. Each name gets its own versioned snapshot in
the raw store, including "not found" — new taxa usually take weeks to reach
PBDB, and that lag is measured and tested downstream (ALCANCE.md §16).

The encyclopedia (Phase 3) also needs every extinct genus of the clades in scope:
`ingest_catalog` downloads them with one request per clade of the
`dbt/seeds/scope_clades.csv` seed, the single definition of the scope (§4).
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from paleo.config import project_root
from paleo.http import get_json
from paleo.interim import latest_rows
from paleo.store import RawStore

PBDB_TAXA_LIST = "https://paleobiodb.org/data1.2/taxa/list.json"
BATCH_SIZE = 100
REFRESH_DAYS = 7
CATALOG_REFRESH_DAYS = 30
CATALOG_SHOW = "attr,app,class,parent,size"
PBDB_OCCS_LIST = "https://paleobiodb.org/data1.2/occs/list.json"
OCCURRENCES_SHOW = "loc,coords"

_NAME = re.compile(r"^[A-Z][A-Za-zë-]+(?: [a-z][a-z-]+){0,2}$")


@dataclass(frozen=True)
class PbdbResult:
    requested: int
    skipped_fresh: int
    found: int
    not_found: int
    new_versions: int


def store(raw_root: Path | None = None) -> RawStore:
    return RawStore("pbdb", "taxa", volatile={"elapsed_time"}, raw_root=raw_root)


def looks_like_taxon(name: str) -> bool:
    """Cheap filter before asking PBDB: "Spinosaurus", "Tyrannosaurus rex"…"""
    return bool(_NAME.match(name)) and len(name) <= 80


# Words that wikilinks and italics on the yearly pages often start with but that are
# never genera: formations and places ("Morrison", "Brazil"), stages ("Albian"),
# common names ("Arabian ostrich") and glossary terms ("Nomen dubium").
_NOT_GENERA = {
    "Axis", "Basal", "Convergent", "Crown", "Cuban", "Dinosaur", "Early", "East", "El",
    "Fourier", "Gondwana", "Homology", "La",
    "Late", "Laramidia", "Last", "Lower", "Manus", "Middle", "Nomen", "North", "Pangaea",
    "Pes", "PhyloCode", "Plesiomorphy", "Radius", "Santa", "South", "Upper", "West",
}  # fmt: skip
_ADJECTIVE = re.compile(r"[A-Z][a-z]+(?:ian|ean|ese|ish)")


def _never_a_genus(word: str) -> bool:
    from paleo.site.terms import COUNTRIES_ES, TIME_UNITS

    stages = {w for _, _, en, _ in TIME_UNITS for w in en.split(" ")}
    return (
        word in _NOT_GENERA
        or word in COUNTRIES_ES
        or word in stages
        or bool(_ADJECTIVE.fullmatch(word))
    )


def looks_like_linked_taxon(name: str) -> bool:
    """Stricter filter for names taken from links and italics in the prose: the
    first word must be able to be a genus (epithets are too varied to check: rex, xui)."""
    return looks_like_taxon(name) and not _never_a_genus(name.split(" ")[0])


def names_of_interest(interim_root: Path) -> list[str]:
    """Candidate taxon names from the latest parse of every Wikipedia page."""
    names: list[str] = []  # the new taxa themselves: always asked
    linked: list[str] = []  # names in links and italics: only if they look like taxa
    for row in latest_rows(interim_root, "new_taxa"):
        for value in (row.get("name"), row.get("name_link")):
            if value:
                names.append(value)
                names.append(value.split(" ")[0])  # genus of a binomial
        linked.extend(row.get("note_links") or [])
    for item in latest_rows(interim_root, "research"):
        linked.extend([*(item.get("links") or []), *(item.get("italic_names") or [])])
    for value in (n.strip() for n in linked if n):
        if looks_like_linked_taxon(value):
            names.append(value)
            if " " in value:
                names.append(value.split(" ")[0])  # genus of a binomial
    cleaned = (n.strip() for n in names if n)
    return sorted({n for n in cleaned if looks_like_taxon(n)})


def _batches(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def fetch_batch(client: httpx.Client, names: list[str]) -> dict[str, list[dict[str, Any]]]:
    """PBDB records for each requested name (empty list = not found).

    A name may match several records (homonyms in different groups); all are
    kept and the choice is made in dbt.
    """
    body = get_json(
        client,
        PBDB_TAXA_LIST,
        {"name": ",".join(names), "vocab": "pbdb", "show": "attr,app,class,parent"},
    )
    by_name: dict[str, list[dict[str, Any]]] = {n: [] for n in names}
    lookup = {n.lower(): n for n in names}
    for record in body.get("records", []):
        requested = lookup.get(str(record.get("taxon_name", "")).lower())
        if requested is not None:
            by_name[requested].append(record)
    return by_name


def ingest_names(
    client: httpx.Client,
    names: list[str],
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> PbdbResult:
    """Snapshot PBDB records for ``names``, skipping recently checked ones."""
    taxa = store(raw_root)
    # Never-checked names are always pending; the rest are re-checked weekly.
    pending = [n for n in names if refresh or not taxa.is_fresh(n, REFRESH_DAYS, today)]
    found = not_found = new_versions = 0
    for batch in _batches(pending, BATCH_SIZE):
        for name, records in fetch_batch(client, batch).items():
            payload = {"name": name, "found": bool(records), "records": records}
            if taxa.save_if_changed(name, payload, today).created:
                new_versions += 1
            found += bool(records)
            not_found += not records
        taxa.flush()  # keep progress if a later batch fails
    taxa.flush()
    return PbdbResult(len(names), len(names) - len(pending), found, not_found, new_versions)


# --- Encyclopedia catalog: every extinct genus and species of the clades in scope ----


@dataclass(frozen=True)
class ScopeClade:
    block: str
    taxon_group: str
    pbdb_base_name: str
    priority: int
    enabled: bool
    block_root: bool = False
    wikidata_item: str | None = None
    pbdb_query: str | None = None  # "seed:<name>": the genera of that seed

    def base_names(self, seeds: Path | None = None) -> str:
        """Value of PBDB's base_name parameter: the clade, or a seed's genus list."""
        if not self.pbdb_query or not self.pbdb_query.startswith("seed:"):
            return self.pbdb_base_name
        folder = seeds or project_root() / "dbt" / "seeds"
        with (folder / f"{self.pbdb_query[5:]}.csv").open(encoding="utf-8", newline="") as f:
            return ",".join(r["genus"].strip() for r in csv.DictReader(f) if r["genus"].strip())


@dataclass(frozen=True)
class CatalogResult:
    clades: int
    skipped_fresh: int
    records: int
    new_versions: int


def scope_clades(seed: Path | None = None, *, enabled_only: bool = True) -> list[ScopeClade]:
    """Rows of the scope seed (ALCANCE.md §4); only the enabled blocks by default."""
    path = seed or project_root() / "dbt" / "seeds" / "scope_clades.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = [
            ScopeClade(
                r["block"],
                r["taxon_group"],
                r["pbdb_base_name"],
                int(r["priority"]),
                r["enabled"].strip().lower() == "true",
                (r.get("block_root") or "").strip().lower() == "true",
                (r.get("wikidata_item") or "").strip() or None,
                (r.get("pbdb_query") or "").strip() or None,
            )
            for r in csv.DictReader(f)
        ]
    return [r for r in rows if r.enabled or not enabled_only]


def catalog_store(raw_root: Path | None = None) -> RawStore:
    return RawStore("pbdb", "catalog", volatile={"elapsed_time"}, raw_root=raw_root)


def fetch_catalog(client: httpx.Client, base_name: str) -> list[dict[str, Any]]:
    """Accepted extinct genera and species under ``base_name`` (one request, a few MB).

    ``accepted``, not ``valid``: PBDB counts junior synonyms as valid, so "valid"
    would list Manospondylus gigas as a species of Tyrannosaurus and give the
    synonym genus a page of its own."""
    body = get_json(
        client,
        PBDB_TAXA_LIST,
        {
            "base_name": base_name,
            "rank": "genus,species",
            "extant": "no",
            "taxon_status": "accepted",
            "vocab": "pbdb",
            "show": CATALOG_SHOW,
        },
    )
    return body.get("records", [])


def ingest_catalog(
    client: httpx.Client,
    clades: list[ScopeClade],
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> CatalogResult:
    """Snapshot the catalog of each clade, re-downloaded monthly."""
    catalog = catalog_store(raw_root)
    pending = [
        c
        for c in clades
        if refresh or not catalog.is_fresh(c.pbdb_base_name, CATALOG_REFRESH_DAYS, today)
    ]
    records = new_versions = 0
    for clade in pending:
        rows = fetch_catalog(client, clade.base_names())
        payload = {"base_name": clade.pbdb_base_name, "show": CATALOG_SHOW, "records": rows}
        new_versions += catalog.save_if_changed(clade.pbdb_base_name, payload, today).created
        records += len(rows)
        catalog.flush()
    return CatalogResult(len(clades), len(clades) - len(pending), records, new_versions)


# --- Occurrences: where each genus was found (countries now, the map later) ----------


@dataclass(frozen=True)
class OccurrencesResult:
    blocks: int
    skipped_fresh: int
    records: int
    new_versions: int


def occurrences_store(raw_root: Path | None = None) -> RawStore:
    return RawStore("pbdb", "occurrences", volatile={"elapsed_time"}, raw_root=raw_root)


def fetch_occurrences(client: httpx.Client, base_name: str) -> list[dict[str, Any]]:
    """Occurrences identified at least to genus under ``base_name``, with country and
    coordinates. Compact field names (vocab=com): the block is tens of thousands
    of records, and the full names would double the size kept in git."""
    body = get_json(
        client,
        PBDB_OCCS_LIST,
        {"base_name": base_name, "idreso": "genus", "vocab": "com", "show": OCCURRENCES_SHOW},
    )
    return body.get("records", [])


def ingest_occurrences(
    client: httpx.Client,
    clades: list[ScopeClade],
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> OccurrencesResult:
    """Snapshot the occurrences of each block once a month (one request per block root)."""
    store_ = occurrences_store(raw_root)
    roots = [c for c in clades if c.block_root]
    pending = [
        c
        for c in roots
        if refresh or not store_.is_fresh(c.pbdb_base_name, CATALOG_REFRESH_DAYS, today)
    ]
    records = new_versions = 0
    for clade in pending:
        rows = fetch_occurrences(client, clade.base_names())
        payload = {"base_name": clade.pbdb_base_name, "show": OCCURRENCES_SHOW, "records": rows}
        new_versions += store_.save_if_changed(clade.pbdb_base_name, payload, today).created
        records += len(rows)
        store_.flush()
    return OccurrencesResult(len(roots), len(roots) - len(pending), records, new_versions)
