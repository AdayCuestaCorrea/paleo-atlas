"""Resolve taxon names against the Paleobiology Database (PBDB, CC BY 4.0).

Names come from the parsed Wikipedia pages: new taxa (and their genus), taxa
mentioned in the notes ("A member of the family Peirosauridae") and taxa linked
or italicised in research items. Each name gets its own versioned snapshot in
the raw store, including "not found" — new taxa usually take weeks to reach
PBDB, and that lag is measured and tested downstream (ALCANCE.md §16).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from paleo.http import get_json
from paleo.interim import latest_rows
from paleo.store import RawStore

PBDB_TAXA_LIST = "https://paleobiodb.org/data1.2/taxa/list.json"
BATCH_SIZE = 100
REFRESH_DAYS = 7

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


def names_of_interest(interim_root: Path) -> list[str]:
    """Candidate taxon names from the latest parse of every Wikipedia page."""
    names: list[str] = []
    for row in latest_rows(interim_root, "new_taxa"):
        for value in (row.get("name"), row.get("name_link")):
            if value:
                names.append(value)
                names.append(value.split(" ")[0])  # genus of a binomial
        names.extend(row.get("note_links") or [])
    for item in latest_rows(interim_root, "research"):
        for value in [*(item.get("links") or []), *(item.get("italic_names") or [])]:
            names.append(value)
            if " " in value:
                names.append(value.split(" ")[0])
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
