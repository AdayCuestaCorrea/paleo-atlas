"""Study metadata from Crossref: type, journal, ISSN, retractions and corrections.

Crossref metadata is free to use, but abstracts may be copyrighted by their
publishers (ALCANCE.md §5). They are therefore removed before anything is
written to the versioned raw store, and kept only in a local cache
(``data/cache``, never committed) as input for fact extraction.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from paleo.config import CONTACT_EMAIL, get_paths
from paleo.http import HttpError, get_json
from paleo.interim import latest_rows
from paleo.store import RawStore, _atomic_write, safe_key

CROSSREF_WORKS = "https://api.crossref.org/works/"
REFRESH_DAYS = 30  # retractions are re-checked monthly (or with --refresh)
VOLATILE = {"indexed", "score", "is-referenced-by-count", "deposited", "reference"}
PRIVATE_FIELDS = {"abstract"}


@dataclass(frozen=True)
class CrossrefResult:
    requested: int
    skipped_fresh: int
    found: int
    not_found: int
    new_versions: int


def store(raw_root: Path | None = None) -> RawStore:
    return RawStore("crossref", "works", volatile=VOLATILE, raw_root=raw_root)


def dois_of_interest(interim_root: Path) -> list[str]:
    """DOIs cited by new taxa and research items in the latest parse."""
    dois = set()
    for kind in ("new_taxa", "research"):
        for row in latest_rows(interim_root, kind):
            for ref in row.get("references") or []:
                if ref.get("doi"):
                    dois.add(ref["doi"].strip().lower())
    return sorted(dois)


def split_private(message: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(public metadata, private fields such as the abstract)."""
    public = {k: v for k, v in message.items() if k not in PRIVATE_FIELDS}
    private = {k: v for k, v in message.items() if k in PRIVATE_FIELDS}
    return public, private


def _cache_private(doi: str, private: dict[str, Any], cache_root: Path) -> None:
    if not private:
        return
    folder = cache_root / "crossref_abstracts"
    folder.mkdir(parents=True, exist_ok=True)
    _atomic_write(folder / f"{safe_key(doi)}.json", json.dumps({"doi": doi, **private}) + "\n")


def ensure_private(client: httpx.Client, doi: str, cache_root: Path) -> bool:
    """Fetch the abstract of an already stored work when the local cache lacks it
    (e.g. on a fresh CI runner). Returns True if a request was made."""
    if (cache_root / "crossref_abstracts" / f"{safe_key(doi)}.json").exists():
        return False
    message = fetch_work(client, doi)
    if message is not None:
        _cache_private(doi, split_private(message)[1], cache_root)
    return True


def fetch_work(client: httpx.Client, doi: str) -> dict[str, Any] | None:
    """Crossref ``message`` for ``doi``, or None when Crossref does not know it."""
    try:
        body = get_json(client, CROSSREF_WORKS + quote(doi, safe="/()"), {"mailto": CONTACT_EMAIL})
    except HttpError as exc:
        if exc.status_code == 404:
            return None  # e.g. a DataCite DOI, or a typo on Wikipedia
        raise
    return body.get("message")


def ingest_dois(
    client: httpx.Client,
    dois: list[str],
    *,
    raw_root: Path | None = None,
    cache_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> CrossrefResult:
    works = store(raw_root)
    cache_root = cache_root if cache_root is not None else get_paths().data / "cache"
    pending = [d for d in dois if refresh or not works.is_fresh(d, REFRESH_DAYS, today)]
    found = not_found = new_versions = 0
    for i, doi in enumerate(pending, start=1):
        message = fetch_work(client, doi)
        if message is None:
            payload: dict[str, Any] = {"doi": doi, "found": False}
            not_found += 1
        else:
            public, private = split_private(message)
            _cache_private(doi, private, cache_root)
            payload = {"doi": doi, "found": True, "work": public}
            found += 1
        if works.save_if_changed(doi, payload, today).created:
            new_versions += 1
        if i % 25 == 0:
            works.flush()  # keep progress on long first runs
    works.flush()
    return CrossrefResult(len(dois), len(dois) - len(pending), found, not_found, new_versions)
