"""Download yearly Wikipedia paleontology pages and store them raw.

Each stored file is keyed by the page revision id, so ingestion is idempotent:
the same revision is never written twice, and every revision we have seen stays
on disk as an auditable snapshot (ALCANCE.md, decisions D3 and D9).

The pages of past years (Phase 3, H4) go to their own folder, ``raw/wikipedia_past``:
they only feed each taxon's history, never the new taxa, studies or texts of the year.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from paleo.config import WIKIPEDIA_API, WikipediaPage, get_paths, slugify_title
from paleo.http import get_json

CURRENT = "wikipedia"
PAST = "wikipedia_past"
PAST_REFRESH_DAYS = 30

# maxlag keeps automated reads gentle when Wikimedia replicas are lagging.
BASE_PARAMS = {"format": "json", "formatversion": "2", "maxlag": "5"}


@dataclass(frozen=True)
class Revision:
    title: str
    pageid: int
    revid: int
    timestamp: str


@dataclass(frozen=True)
class IngestResult:
    revision: Revision
    path: Path
    created: bool  # False when that revision was already stored


def _first_page(body: dict[str, Any], title: str) -> dict[str, Any]:
    pages = body.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        raise LookupError(f"Wikipedia page not found: {title!r}")
    return pages[0]


def latest_revision(client: httpx.Client, title: str) -> Revision:
    """Metadata of the latest revision (one cheap request, no content)."""
    body = get_json(
        client,
        WIKIPEDIA_API,
        {
            **BASE_PARAMS,
            "action": "query",
            "prop": "revisions",
            "rvprop": "ids|timestamp",
            "titles": title,
        },
    )
    page = _first_page(body, title)
    rev = page["revisions"][0]
    return Revision(page["title"], page["pageid"], rev["revid"], rev["timestamp"])


def fetch_wikitext(client: httpx.Client, title: str) -> tuple[Revision, str]:
    """Latest revision of ``title`` together with its wikitext."""
    body = get_json(
        client,
        WIKIPEDIA_API,
        {
            **BASE_PARAMS,
            "action": "query",
            "prop": "revisions",
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "titles": title,
        },
    )
    page = _first_page(body, title)
    rev = page["revisions"][0]
    revision = Revision(page["title"], page["pageid"], rev["revid"], rev["timestamp"])
    return revision, rev["slots"]["main"]["content"]


def page_dir(title: str, raw_root: Path | None = None, folder: str = CURRENT) -> Path:
    root = raw_root if raw_root is not None else get_paths().raw
    return root / folder / slugify_title(title)


def stored_revids(title: str, raw_root: Path | None = None, folder: str = CURRENT) -> list[int]:
    """Revision ids already on disk for ``title``, oldest first."""
    directory = page_dir(title, raw_root, folder)
    if not directory.is_dir():
        return []
    return sorted(int(p.stem) for p in directory.glob("*.json") if p.stem.isdigit())


def has_new_revision(client: httpx.Client, title: str, raw_root: Path | None = None) -> bool:
    """True when Wikipedia has a revision we have not stored yet."""
    known = stored_revids(title, raw_root)
    return not known or latest_revision(client, title).revid > known[-1]


def ingest_page(
    client: httpx.Client, title: str, raw_root: Path | None = None, folder: str = CURRENT
) -> IngestResult:
    """Store the latest revision of ``title`` unless it is already on disk."""
    latest = latest_revision(client, title)
    path = page_dir(title, raw_root, folder) / f"{latest.revid}.json"
    if path.exists():
        return IngestResult(latest, path, created=False)

    revision, wikitext = fetch_wikitext(client, title)
    # The page may have been edited between both calls: store what we got.
    path = page_dir(title, raw_root, folder) / f"{revision.revid}.json"
    if path.exists():
        return IngestResult(revision, path, created=False)

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "source": "wikipedia",
        "title": revision.title,
        "pageid": revision.pageid,
        "revid": revision.revid,
        "timestamp": revision.timestamp,
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "license": "CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/",
        "wikitext": wikitext,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)  # atomic: a half-written file never looks like a stored revision
    return IngestResult(revision, path, created=True)


def load_raw(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --- Past years (history, Phase 3 H4) ---------------------------------------------


@dataclass(frozen=True)
class PastResult:
    pages: int
    skipped_fresh: int
    missing: int
    new_revisions: int


def past_titles(pages: list[WikipediaPage], year: int) -> list[str]:
    """Yearly pages from each block's first year up to the year before ``year``."""
    return [p.title(y) for p in pages for y in range(p.first_year, year)]


def _checked_path(raw_root: Path) -> Path:
    return raw_root / PAST / "_checked.json"


def ingest_past(
    client: httpx.Client,
    pages: list[WikipediaPage],
    year: int,
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> PastResult:
    """Store the latest revision of every past yearly page, checked once a month.

    Past pages change little (late corrections); only their latest revision is
    parsed, so a new revision replaces the old one in the history."""
    root = raw_root if raw_root is not None else get_paths().raw
    today = today or dt.date.today()
    marker = _checked_path(root)
    checked: dict[str, str] = json.loads(marker.read_text()) if marker.exists() else {}
    titles = past_titles(pages, year)
    fresh = missing = created = 0
    for title in titles:
        last = checked.get(title)
        if not refresh and last and (today - dt.date.fromisoformat(last)).days < PAST_REFRESH_DAYS:
            fresh += 1
            continue
        try:
            created += ingest_page(client, title, root, PAST).created
        except LookupError:
            missing += 1
        checked[title] = today.isoformat()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(checked, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return PastResult(len(titles), fresh, missing, created)
