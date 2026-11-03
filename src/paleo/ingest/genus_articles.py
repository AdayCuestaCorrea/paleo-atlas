"""Wikipedia articles of the encyclopedia genera, and their lead images (Phase 3, H2).

A genus name is not enough to find its article: "Coloradia" is also a moth. For each
genus of the PBDB catalog this module stores what Wikipedia and Wikidata say:

1. English Wikipedia, 50 titles per request: the article the name leads to (after
   redirects), whether it is a disambiguation page, its Wikidata item and its lead
   image when the image is free (``pageimages``, ``pilicense=free``);
2. Wikidata, 100 items per SPARQL query: the PBDB taxon ids of the item (P842,
   "Fossilworks taxon ID"), its Spanish Wikipedia article, and which block roots of
   the scope seed it descends from (P171, parent taxon).

Whether the article really is about the PBDB genus is decided in dbt
(int_genus_wikipedia): P842 must be the genus or one of its species, and the item
must descend from the block root. Both are needed: the Wikidata item of the moth
Coloradia carries, by mistake, the PBDB id of the dinosaur. Nothing is linked
otherwise. Wikidata is CC0; article titles and file names are facts.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx

from paleo.http import HttpError, get_json, request_json
from paleo.ingest import pbdb
from paleo.store import RawStore

WIKIPEDIA_EN_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
TITLES_PER_REQUEST = 50
ITEMS_PER_QUERY = 100
PICTURE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "svg", "webp", "tif", "tiff"}
SPARQL_TIMEOUT = 70.0  # the query service gives up at 60 s
log = logging.getLogger(__name__)
REFRESH_DAYS = 30
BUDGET = 600  # genera looked up per run: the first full pass takes a few days


@dataclass(frozen=True)
class GenusArticlesResult:
    genera: int
    skipped_fresh: int
    looked_up: int
    with_article: int
    new_versions: int
    failed: int = 0  # genera whose lookup failed this run (retried on the next one)


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


def _sparql(client: httpx.Client, query: str) -> list[dict[str, Any]]:
    body = request_json(
        client, "POST", WIKIDATA_SPARQL, data={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"}, timeout=SPARQL_TIMEOUT,
    )  # fmt: skip
    return body.get("results", {}).get("bindings", [])


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def lookup_wikidata(
    client: httpx.Client, items: list[str], roots: list[str]
) -> dict[str, dict[str, Any]]:
    """PBDB taxon ids (P842), Spanish Wikipedia title and the block roots (``roots``,
    Wikidata items of the scope seed) each item descends from.

    The ancestry check asks for every ancestor of the items (P171+, walking up from
    each item: about 70 per genus) and compares them here. Asking Wikidata whether
    an item descends from a root walks down from the root instead, and a root like
    Vertebrata has a subtree too big to answer in time."""
    values = " ".join(f"wd:{q}" for q in items)
    out: dict[str, dict[str, Any]] = {
        q: {"pbdb_ids": [], "es_title": None, "scope_roots": [], "in_scope_tree": False}
        for q in items
    }
    for row in _sparql(client, f"""
        SELECT ?item ?pbdb ?es WHERE {{
          VALUES ?item {{ {values} }}
          OPTIONAL {{ ?item wdt:P842 ?pbdb }}
          OPTIONAL {{ ?es schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }}
        }}"""):  # fmt: skip
        q = _qid(row["item"]["value"])
        if q not in out:
            continue
        if "pbdb" in row and row["pbdb"]["value"] not in out[q]["pbdb_ids"]:
            out[q]["pbdb_ids"].append(row["pbdb"]["value"])
        if "es" in row:  # https://es.wikipedia.org/wiki/T%C3%ADtulo -> Título
            title = unquote(row["es"]["value"].rsplit("/wiki/", 1)[-1])
            out[q]["es_title"] = title.replace("_", " ")
    wanted = set(roots)
    for row in _sparql(
        client,
        f"""
        SELECT ?item ?anc WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P171+ ?anc . }}""",
    ):
        q, anc = _qid(row["item"]["value"]), _qid(row["anc"]["value"])
        if q in out and anc in wanted and anc not in out[q]["scope_roots"]:
            out[q]["scope_roots"].append(anc)
    for value in out.values():
        value["pbdb_ids"].sort(key=lambda v: (len(v), v))
        value["scope_roots"].sort()
        value["in_scope_tree"] = bool(value["scope_roots"])
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
    """Look up the stalest ``budget`` genera (never looked up first).

    A batch that fails (Wikipedia or Wikidata down, a query timing out) is left out
    and logged: those genera stay stale and are looked up on the next run. One
    failing service never stops the pipeline."""
    articles = store(raw_root)
    stale = [g for g in genera if refresh or not articles.is_fresh(g, REFRESH_DAYS, today)]
    # Never looked up first, then the oldest checks.
    stale.sort(key=lambda g: (articles.checked_on(g) is not None, articles.checked_on(g) or "", g))
    todo = stale[:budget]
    found: dict[str, dict[str, Any]] = {}
    failed = 0
    for batch in _batches(todo, TITLES_PER_REQUEST):
        try:
            found.update(lookup_titles(client, batch))
        except HttpError as exc:
            failed += len(batch)
            log.warning(
                "Wikipedia lookup of %d genera failed, retried next run: %s", len(batch), exc
            )
    roots = [c.wikidata_item for c in pbdb.scope_clades() if c.block_root and c.wikidata_item]
    items = sorted({v["wikidata_item"] for v in found.values() if v["wikidata_item"]})
    wikidata: dict[str, dict[str, Any]] = {}
    for batch in _batches(items, ITEMS_PER_QUERY):
        try:
            wikidata.update(lookup_wikidata(client, batch, roots))
        except HttpError as exc:
            log.warning("Wikidata lookup of %d items failed, retried next run: %s", len(batch), exc)
    new_versions = with_article = 0
    empty = {"pbdb_ids": [], "es_title": None, "scope_roots": [], "in_scope_tree": False}
    for i, (name, payload) in enumerate(sorted(found.items()), start=1):
        item = payload["wikidata_item"]
        if item and item not in wikidata:  # its Wikidata batch failed: not saved
            failed += 1
            continue
        payload |= wikidata.get(item or "", empty)
        with_article += payload["en_title"] is not None
        new_versions += articles.save_if_changed(name, payload, today).created
        if i % 200 == 0:
            articles.flush()
    articles.flush()
    return GenusArticlesResult(
        len(genera),
        len(genera) - len(stale),
        len(todo) - failed,
        with_article,
        new_versions,
        failed,
    )


def lead_images(raw_root: Path | None = None) -> list[str]:
    """Lead image files of the stored lookups (their metadata comes from Commons)."""
    articles = store(raw_root)
    files = set()
    for key in articles.stored_keys():
        latest = articles.latest(key)
        image = latest and latest["payload"].get("lead_image")
        # The "lead image" of an article can be a PDF (a paper): pictures only.
        if image and image.lower().rsplit(".", 1)[-1] in PICTURE_EXTENSIONS:
            files.add(image)
    return sorted(files)


# --- Article text of the genera, for the narrative pages (Phase 3, H6) ----------------

TEXT_BATCH = 20  # long articles: smaller batches keep the response under the API size cap
TEXT_REFRESH_DAYS = 30


@dataclass(frozen=True)
class GenusTextsResult:
    genera: int
    skipped_fresh: int
    found: dict[str, int]
    new_versions: int


def text_store(lang: str, raw_root: Path | None = None) -> RawStore:
    """Wikitext of the genus articles, apart from the new taxa's (raw/wikipedia_articles):
    the image and new-taxa steps read that store and must not change."""
    return RawStore("wikimedia", f"genus_text_{lang}", raw_root=raw_root)


def verified_titles(warehouse: Path) -> dict[str, tuple[str, str | None]]:
    """Genus -> (EN title, ES title) of the articles that int_genus_wikipedia accepted."""
    import duckdb

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(
            "select taxon_name, wikipedia_article, wikipedia_article_es from main.dim_taxon "
            "where page_type = 'genus' and wikipedia_article is not null order by 1"
        ).fetchall()
    finally:
        con.close()
    return {name: (en, es) for name, en, es in rows}


def _fetch_texts(client: httpx.Client, lang: str, titles: list[str]) -> dict[str, dict]:
    from paleo.ingest.articles import fetch_articles

    out = fetch_articles(client, lang, titles)
    # A page left without content (response size cap) is asked again on its own.
    for title in [t for t, a in out.items() if not a["found"]]:
        out[title] = fetch_articles(client, lang, [title])[title]
    return out


def ingest_genus_texts(
    client: httpx.Client,
    titles: dict[str, tuple[str, str | None]],
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> GenusTextsResult:
    """Store the EN (and ES) wikitext of each genus article, keyed by genus name."""
    stores = {lang: text_store(lang, raw_root) for lang in ("en", "es")}
    pending = [
        g for g in titles if refresh or not stores["en"].is_fresh(g, TEXT_REFRESH_DAYS, today)
    ]
    found = {"en": 0, "es": 0}
    new_versions = 0
    for lang, index in (("en", 0), ("es", 1)):
        todo = [g for g in pending if titles[g][index]]
        for batch in _batches(todo, TEXT_BATCH):
            try:
                by_title = _fetch_texts(client, lang, [titles[g][index] for g in batch])
            except HttpError as exc:
                log.warning("%s texts of %d genera failed: %s", lang, len(batch), exc)
                continue
            for genus in batch:
                article = by_title[titles[genus][index]]
                saved = stores[lang].save_if_changed(genus, {"taxon": genus, **article}, today)
                new_versions += saved.created
                found[lang] += article["found"]
            stores[lang].flush()
    return GenusTextsResult(len(titles), len(titles) - len(pending), found, new_versions)
