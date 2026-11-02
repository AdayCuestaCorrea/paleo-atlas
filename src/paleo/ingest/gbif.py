"""GBIF fossil specimens (F3, ALCANCE.md §5): one filtered download a month.

GBIF's taxonomy has no node for most clades of §4 (no Dinosauria, Archosauria or
Placodermi; many fossil genera have no class at all), so the server-side filter is
broad: fossil specimens (basisOfRecord = FOSSIL_SPECIMEN) of the taxa marked
"include" in dbt/seeds/gbif_taxa.csv minus those marked "exclude" (mammals and
turtles: big and outside §4). The Spark/DuckDB job then reduces it to the genera of
the PBDB catalog (paleo.gbif_job).

The download itself (hundreds of MB) stays in the local cache (decision A11): only
its record (key, DOI, filter, size, licence) is versioned, so the DOI can be cited
and the download reproduced. Credentials come from the environment (GBIF_USERNAME,
GBIF_PASSWORD, GBIF_MAIL; the repo's .env is loaded like the LLM keys) and are never
printed or stored.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from paleo.config import get_paths, project_root
from paleo.http import HttpError, get_json
from paleo.store import RawStore

GBIF_API = "https://api.gbif.org/v1"
FORMATS = ("SIMPLE_PARQUET", "SIMPLE_CSV")  # preferred first
DONE = {"SUCCEEDED"}
FAILED = {"FAILED", "KILLED", "CANCELLED", "FILE_ERASED"}
log = logging.getLogger(__name__)


class GbifError(RuntimeError):
    pass


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str
    mail: str


def credentials() -> Credentials:
    """GBIF account from the environment (and the repo's .env)."""
    from paleo.llm import load_dotenv

    load_dotenv()
    names = ("GBIF_USERNAME", "GBIF_PASSWORD", "GBIF_MAIL")
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise GbifError(f"missing {', '.join(missing)} (set them in .env)")
    return Credentials(*(os.environ[n] for n in names))


def store(raw_root: Path | None = None) -> RawStore:
    return RawStore("gbif", "downloads", raw_root=raw_root)


def taxa_filter(seed: Path | None = None) -> tuple[list[int], list[int]]:
    """(included, excluded) GBIF taxon keys from the seed."""
    path = seed or project_root() / "dbt" / "seeds" / "gbif_taxa.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    keep = [int(r["gbif_key"]) for r in rows if r["role"] == "include"]
    drop = [int(r["gbif_key"]) for r in rows if r["role"] == "exclude"]
    return keep, drop


def predicate(included: list[int], excluded: list[int]) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [
        {"type": "equals", "key": "BASIS_OF_RECORD", "value": "FOSSIL_SPECIMEN"},
        {"type": "in", "key": "TAXON_KEY", "values": [str(k) for k in included]},
    ]
    if excluded:
        parts.append({"type": "not", "predicate": {
            "type": "in", "key": "TAXON_KEY", "values": [str(k) for k in excluded]}})  # fmt: skip
    return {"type": "and", "predicates": parts}


def request_download(
    client: httpx.Client, creds: Credentials, pred: dict[str, Any], fmt: str = FORMATS[0]
) -> str:
    """Ask GBIF for a download; returns its key (GBIF prepares it asynchronously)."""
    body = {
        "creator": creds.username,
        "notificationAddresses": [creds.mail],
        "sendNotification": True,
        "format": fmt,
        "predicate": pred,
    }
    response = client.post(
        f"{GBIF_API}/occurrence/download/request",
        json=body,
        auth=(creds.username, creds.password),
        timeout=60,
    )
    if response.status_code not in (200, 201):
        raise GbifError(
            f"download request refused: HTTP {response.status_code} {response.text[:300]}"
        )
    return response.text.strip()


def download_status(client: httpx.Client, key: str) -> dict[str, Any]:
    return get_json(client, f"{GBIF_API}/occurrence/download/{key}")


def wait_download(
    client: httpx.Client,
    key: str,
    *,
    max_wait_s: float = 6 * 3600,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Poll until GBIF finishes the download (minutes to hours)."""
    start, wait = clock(), 30.0
    while True:
        status = download_status(client, key)
        if status.get("status") in DONE:
            return status
        if status.get("status") in FAILED:
            raise GbifError(f"download {key} ended {status.get('status')}")
        if clock() - start > max_wait_s:
            raise GbifError(f"download {key} not ready after {max_wait_s / 3600:.1f} h")
        log.info(
            "GBIF download %s is %s; checking again in %.0f s", key, status.get("status"), wait
        )
        sleep(wait)
        wait = min(wait * 2, 600)


def fetch_file(client: httpx.Client, url: str, target: Path) -> Path:
    """Stream the (large) zip to the local cache."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    with client.stream("GET", url, follow_redirects=True, timeout=600) as response:
        response.raise_for_status()
        with partial.open("wb") as f:
            for chunk in response.iter_bytes(1 << 20):
                f.write(chunk)
    partial.replace(target)
    return target


def cache_dir(key: str) -> Path:
    return get_paths().data / "cache" / "gbif" / key


def record(status: dict[str, Any], pred: dict[str, Any], fmt: str) -> dict[str, Any]:
    """What is versioned about a download: enough to cite and reproduce it."""
    return {
        "key": status.get("key"),
        "doi": status.get("doi"),
        "format": fmt,
        "predicate": pred,
        "status": status.get("status"),
        "created": status.get("created"),
        "modified": status.get("modified"),
        "total_records": status.get("totalRecords"),
        "number_datasets": status.get("numberDatasets"),
        "size_bytes": status.get("size"),
        "license": status.get("license"),
        "citation": f"GBIF.org ({str(status.get('created', ''))[:10]}) GBIF Occurrence Download "
        f"https://doi.org/{status.get('doi')}",
    }


def extract(
    client: httpx.Client,
    *,
    raw_root: Path | None = None,
    today: dt.date | None = None,
    key: str | None = None,
    wait: Callable[..., dict[str, Any]] = wait_download,
) -> tuple[dict[str, Any], Path]:
    """Request (or resume, with ``key``) the monthly download, wait for it, fetch it."""
    creds = credentials()
    keep, drop = taxa_filter()
    pred = predicate(keep, drop)
    fmt = FORMATS[0]
    if key is None:
        try:
            key = request_download(client, creds, pred, fmt)
        except GbifError as exc:
            if "format" not in str(exc).lower():
                raise
            fmt = FORMATS[1]  # older API: no Parquet
            key = request_download(client, creds, pred, fmt)
    log.info("GBIF download %s requested", key)
    status = wait(client, key)
    target = fetch_file(client, status["downloadLink"], cache_dir(key) / f"{key}.zip")
    rec = record(status, pred, fmt)
    store(raw_root).save_if_changed(key, rec, today)
    store(raw_root).flush()
    return rec, target


__all__ = ["GbifError", "HttpError", "extract", "predicate", "taxa_filter"]
