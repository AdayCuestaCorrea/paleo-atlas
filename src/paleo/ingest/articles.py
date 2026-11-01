"""Wikipedia articles (EN, and ES when it exists) for every new taxon.

They are the main source for the narrative pages. The text is CC BY-SA 4.0:
it is only read to extract facts, never copied (ALCANCE.md §12.1, §19).
Each article is stored as a versioned snapshot keyed by taxon name.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from paleo.http import get_json
from paleo.interim import latest_rows
from paleo.store import RawStore

LANGUAGES = ("en", "es")
API = "https://{lang}.wikipedia.org/w/api.php"
BATCH = 50  # MediaWiki returns content for up to 50 titles per request
REFRESH_DAYS = 7


@dataclass(frozen=True)
class ArticleResult:
    taxa: int
    skipped_fresh: int
    found: dict[str, int]
    new_versions: int


def store(lang: str, raw_root: Path | None = None) -> RawStore:
    return RawStore("wikipedia_articles", lang, raw_root=raw_root)


def new_taxa_titles(interim_root: Path) -> dict[str, str]:
    """Taxon name -> English article title (the wikilink of the table row)."""
    out = {}
    for row in latest_rows(interim_root, "new_taxa"):
        name = row.get("name")
        if name:
            out[name] = row.get("name_link") or name
    return out


def _batches(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def fetch_articles(
    client: httpx.Client, lang: str, titles: list[str], *, with_langlinks: bool = False
) -> dict[str, dict[str, Any]]:
    """Latest wikitext of each title (following redirects), keyed by requested title."""
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "maxlag": "5",
        "redirects": "1",
        "prop": "revisions|langlinks" if with_langlinks else "revisions",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "titles": "|".join(titles),
    }
    if with_langlinks:
        params |= {"lllang": "es", "lllimit": "max"}
    body = get_json(client, API.format(lang=lang), params)
    query = body.get("query", {})
    # requested title -> final title, through normalization and redirects
    final = {t: t for t in titles}
    for step in ("normalized", "redirects"):
        mapping = {m["from"]: m["to"] for m in query.get(step, [])}
        final = {t: mapping.get(f, f) for t, f in final.items()}
    pages = {p["title"]: p for p in query.get("pages", [])}
    out = {}
    for requested, title in final.items():
        page = pages.get(title)
        if not page or page.get("missing") or not page.get("revisions"):
            out[requested] = {"title": title, "found": False}
            continue
        rev = page["revisions"][0]
        out[requested] = {
            "title": page["title"],
            "found": True,
            "pageid": page.get("pageid"),
            "revid": rev["revid"],
            "timestamp": rev["timestamp"],
            "wikitext": rev["slots"]["main"]["content"],
            "es_title": next((ll["title"] for ll in page.get("langlinks", [])), None),
            "license": "CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/",
        }
    return out


def ingest_articles(
    client: httpx.Client,
    interim_root: Path,
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> ArticleResult:
    titles = new_taxa_titles(interim_root)
    en, es = store("en", raw_root), store("es", raw_root)
    pending = [t for t in titles if refresh or not en.is_fresh(t, REFRESH_DAYS, today)]
    found = {"en": 0, "es": 0}
    new_versions = 0
    es_titles: dict[str, str] = {}

    for batch in _batches(pending, BATCH):
        by_title = fetch_articles(client, "en", [titles[t] for t in batch], with_langlinks=True)
        for taxon in batch:
            article = by_title[titles[taxon]]
            new_versions += en.save_if_changed(taxon, {"taxon": taxon, **article}, today).created
            found["en"] += article["found"]
            if article.get("es_title"):
                es_titles[taxon] = article["es_title"]
    en.flush()

    taxa = list(es_titles)
    for batch in _batches(taxa, BATCH):
        by_title = fetch_articles(client, "es", [es_titles[t] for t in batch])
        for taxon in batch:
            article = by_title[es_titles[taxon]]
            article.pop("es_title", None)
            new_versions += es.save_if_changed(taxon, {"taxon": taxon, **article}, today).created
            found["es"] += article["found"]
    es.flush()
    return ArticleResult(len(titles), len(titles) - len(pending), found, new_versions)
