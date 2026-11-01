"""Download yearly Wikipedia paleontology pages and store them raw.

Each stored file is keyed by the page revision id, so ingestion is idempotent:
the same revision is never written twice, and every revision we have seen stays
on disk as an auditable snapshot (ALCANCE.md, decisions D3 and D9).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from paleo.config import WIKIPEDIA_API, get_paths, slugify_title
from paleo.http import get_json

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


def page_dir(title: str, raw_root: Path | None = None) -> Path:
    root = raw_root if raw_root is not None else get_paths().raw
    return root / "wikipedia" / slugify_title(title)


def stored_revids(title: str, raw_root: Path | None = None) -> list[int]:
    """Revision ids already on disk for ``title``, oldest first."""
    directory = page_dir(title, raw_root)
    if not directory.is_dir():
        return []
    return sorted(int(p.stem) for p in directory.glob("*.json") if p.stem.isdigit())


def has_new_revision(client: httpx.Client, title: str, raw_root: Path | None = None) -> bool:
    """True when Wikipedia has a revision we have not stored yet."""
    known = stored_revids(title, raw_root)
    return not known or latest_revision(client, title).revid > known[-1]


def ingest_page(client: httpx.Client, title: str, raw_root: Path | None = None) -> IngestResult:
    """Store the latest revision of ``title`` unless it is already on disk."""
    latest = latest_revision(client, title)
    path = page_dir(title, raw_root) / f"{latest.revid}.json"
    if path.exists():
        return IngestResult(latest, path, created=False)

    revision, wikitext = fetch_wikitext(client, title)
    # The page may have been edited between both calls: store what we got.
    path = page_dir(title, raw_root) / f"{revision.revid}.json"
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
