"""Wikipedia articles of the encyclopedia genera, and their lead images (Phase 3, H2).

A genus name is not enough to find its article: "Coloradia" is also a moth. For each
genus of the PBDB catalog this module stores what Wikipedia and Wikidata say:

1. English Wikipedia, 50 titles per request: the article the name leads to (after
   redirects), whether it is a disambiguation page, its Wikidata item and its lead
   image when the image is free (``pageimages``, ``pilicense=free``);
2. Wikidata, 100 items per SPARQL query: the PBDB taxon ids of the item (P842,
   "Fossilworks taxon ID"), its Spanish Wikipedia article, and whether the item
   descends (P171, parent taxon) from the root of its block in the scope seed.

Whether the article really is about the PBDB genus is decided in dbt
(int_genus_wikipedia): P842 must be the genus or one of its species, and the item
must descend from the block root. Both are needed: the Wikidata item of the moth
Coloradia carries, by mistake, the PBDB id of the dinosaur. Nothing is linked
otherwise. Wikidata is CC0; article titles and file names are facts.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from paleo.http import get_json, request_json
from paleo.ingest import pbdb
from paleo.store import RawStore

WIKIPEDIA_EN_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
TITLES_PER_REQUEST = 50
ITEMS_PER_QUERY = 100  # the ancestry check makes bigger queries slow
REFRESH_DAYS = 30
BUDGET = 600  # genera looked up per run: the first full pass takes a few days


@dataclass(frozen=True)
class GenusArticlesResult:
    genera: int
    skipped_fresh: int
    looked_up: int
    with_article: int
    new_versions: int


def store(raw_root: Path | None = None) -> RawStore:
    # Its own source folder: raw/wikipedia/ holds one folder per yearly page.
    return RawStore("wikimedia", "genus_articles", raw_root=raw_root)


def catalog_genera(raw_root: Path | None = None) -> list[str]:
    """Genera of the latest catalog of every enabled clade (no ichnotaxa or form taxa)."""
    catalog = pbdb.catalog_store(raw_root)
    names: set[str] = set()
    for clade in pbdb.scope_clades():
        latest = catalog.latest(clade.pbdb_base_name)
        for record in (latest or {}).get("payload", {}).get("records", []):
            name = record.get("taxon_name") or ""
            if " " not in name and not set(record.get("flags") or "") & {"I", "F"}:
                names.add(name)
    return sorted(n for n in names if n)


def _batches(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def lookup_titles(client: httpx.Client, names: list[str]) -> dict[str, dict[str, Any]]:
    """English Wikipedia article, Wikidata item and free lead image of each name."""
    body = get_json(
        client,
        WIKIPEDIA_EN_API,
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
            "redirects": "1",
            "titles": "|".join(names),
            "prop": "pageprops|pageimages",
            "ppprop": "wikibase_item|disambiguation",
            "piprop": "name",
            "pilicense": "free",
        },
    )
    query = body.get("query", {})
    # name -> title it ended at, following normalization and redirects
    final = {n: n for n in names}
    for step in ("normalized", "redirects"):
        moves = {m["from"]: m["to"] for m in query.get(step, [])}
        final = {n: moves.get(t, t) for n, t in final.items()}
    pages = {p["title"]: p for p in query.get("pages", [])}
    out = {}
    for name in names:
        page = pages.get(final[name], {})
        exists = bool(page) and not page.get("missing") and not page.get("invalid")
        props = page.get("pageprops", {})
        out[name] = {
            "name": name,
            "en_title": page.get("title") if exists else None,
            "redirected": exists and page.get("title") != name,
            "disambiguation": "disambiguation" in props,
            "wikidata_item": props.get("wikibase_item"),
            "lead_image": page.get("pageimage"),
        }
    return out


def lookup_wikidata(
    client: httpx.Client, items: list[str], roots: list[str]
) -> dict[str, dict[str, Any]]:
    """PBDB taxon ids (P842), Spanish Wikipedia title and whether each Wikidata item
    descends from one of ``roots`` (the Wikidata items of the scope's block roots)."""
    values = " ".join(f"wd:{q}" for q in items)
    root_values = " ".join(f"wd:{q}" for q in roots) or "wd:Q0"
    query = f"""
        SELECT ?item ?pbdb ?es ?in_scope WHERE {{
          VALUES ?item {{ {values} }}
          OPTIONAL {{ ?item wdt:P842 ?pbdb }}
          OPTIONAL {{ ?es schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }}
          BIND(EXISTS {{ VALUES ?root {{ {root_values} }} ?item wdt:P171+ ?root }} AS ?in_scope)
        }}"""
    body = request_json(
        client, "POST", WIKIDATA_SPARQL, data={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
    )  # fmt: skip
    out: dict[str, dict[str, Any]] = {
        q: {"pbdb_ids": [], "es_title": None, "in_scope_tree": False} for q in items
    }
    for row in body.get("results", {}).get("bindings", []):
        q = row["item"]["value"].rsplit("/", 1)[-1]
        if q not in out:
            continue
        if "pbdb" in row and row["pbdb"]["value"] not in out[q]["pbdb_ids"]:
            out[q]["pbdb_ids"].append(row["pbdb"]["value"])
        if "es" in row:  # https://es.wikipedia.org/wiki/T%C3%ADtulo -> Título
            title = unquote(row["es"]["value"].rsplit("/wiki/", 1)[-1])
            out[q]["es_title"] = title.replace("_", " ")
        if row.get("in_scope", {}).get("value") == "true":
            out[q]["in_scope_tree"] = True
    for value in out.values():
        value["pbdb_ids"].sort(key=lambda v: (len(v), v))
    return out


def ingest_genus_articles(
    client: httpx.Client,
    genera: list[str],
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
    budget: int = BUDGET,
) -> GenusArticlesResult:
    """Look up the stalest ``budget`` genera (never looked up first)."""
    articles = store(raw_root)
    stale = [g for g in genera if refresh or not articles.is_fresh(g, REFRESH_DAYS, today)]
    # Never looked up first, then the oldest checks.
    stale.sort(key=lambda g: (articles.checked_on(g) is not None, articles.checked_on(g) or "", g))
    todo = stale[:budget]
    found: dict[str, dict[str, Any]] = {}
    for batch in _batches(todo, TITLES_PER_REQUEST):
        found.update(lookup_titles(client, batch))
    items = sorted({v["wikidata_item"] for v in found.values() if v["wikidata_item"]})
    roots = [c.wikidata_item for c in pbdb.scope_clades() if c.block_root and c.wikidata_item]
    wikidata: dict[str, dict[str, Any]] = {}
    for batch in _batches(items, ITEMS_PER_QUERY):
        wikidata.update(lookup_wikidata(client, batch, roots))
    new_versions = with_article = 0
    for i, (name, payload) in enumerate(sorted(found.items()), start=1):
        empty = {"pbdb_ids": [], "es_title": None, "in_scope_tree": False}
        payload |= wikidata.get(payload["wikidata_item"] or "", empty)
        with_article += payload["en_title"] is not None
        new_versions += articles.save_if_changed(name, payload, today).created
        if i % 200 == 0:
            articles.flush()
    articles.flush()
    return GenusArticlesResult(
        len(genera), len(genera) - len(stale), len(todo), with_article, new_versions
    )


def lead_images(raw_root: Path | None = None) -> list[str]:
    """Lead image files of the stored lookups (their metadata comes from Commons)."""
    articles = store(raw_root)
    files = set()
    for key in articles.stored_keys():
        latest = articles.latest(key)
        if latest and latest["payload"].get("lead_image"):
            files.add(latest["payload"]["lead_image"])
    return sorted(files)
