"""Open-access journals from DOAJ, a secondary reliability signal (ALCANCE.md §10).

DOAJ's public API needs no key. Every ISSN of the journals in Crossref is looked up
once a month; the answer ("listed" or "not listed") goes to the versioned raw store.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from paleo import __version__
from paleo.config import CONTACT_EMAIL, REPO_URL
from paleo.http import get_json
from paleo.ingest import crossref
from paleo.store import RawStore

DOAJ_SEARCH = "https://doaj.org/api/search/journals/"
REFRESH_DAYS = 30
# DOAJ answers 403 to User-Agents containing "bot" (the word Wikimedia asks for), so
# it gets the same project and contact details without it.
HEADERS = {"User-Agent": f"paleo-atlas/{__version__} ({REPO_URL}; {CONTACT_EMAIL})"}


@dataclass(frozen=True)
class DoajResult:
    requested: int
    skipped_fresh: int
    listed: int
    not_listed: int
    new_versions: int


def store(raw_root: Path | None = None) -> RawStore:
    return RawStore("doaj", "journals", raw_root=raw_root)


def issns_of_interest(raw_root: Path | None = None) -> list[str]:
    """Every ISSN of the works stored from Crossref."""
    works = crossref.store(raw_root)
    issns = set()
    for key in works.stored_keys():
        latest = works.latest(key)
        if latest and latest["payload"].get("found"):
            issns.update(i.strip().upper() for i in latest["payload"]["work"].get("ISSN") or [])
    return sorted(i for i in issns if i)


def fetch_journal(client: httpx.Client, issn: str) -> dict[str, Any]:
    body = get_json(
        client, DOAJ_SEARCH + quote(f"issn:{issn}"), params={"pageSize": 1}, headers=HEADERS
    )
    results = body.get("results") or []
    if not results:
        return {"issn": issn, "listed": False}
    bib = results[0].get("bibjson") or {}
    licenses = [lic.get("type") for lic in bib.get("license") or [] if lic.get("type")]
    return {
        "issn": issn,
        "listed": True,
        "doaj_id": results[0].get("id"),
        "title": bib.get("title"),
        "eissn": bib.get("eissn"),
        "pissn": bib.get("pissn"),
        "licenses": licenses,
    }


def ingest_issns(
    client: httpx.Client,
    issns: list[str],
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> DoajResult:
    journals = store(raw_root)
    pending = [i for i in issns if refresh or not journals.is_fresh(i, REFRESH_DAYS, today)]
    listed = new_versions = 0
    for n, issn in enumerate(pending, start=1):
        payload = fetch_journal(client, issn)
        listed += payload["listed"]
        new_versions += journals.save_if_changed(issn, payload, today).created
        if n % 25 == 0:
            journals.flush()
    journals.flush()
    return DoajResult(
        len(issns), len(issns) - len(pending), listed, len(pending) - listed, new_versions
    )
