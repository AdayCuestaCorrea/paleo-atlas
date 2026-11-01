"""Freely licensed images for every taxon with a page.

Two sources, both recorded with author and license so the site can credit
them (ALCANCE.md §5, §19):

* **Wikimedia Commons** — the files listed in the "Images" column of the
  Wikipedia tables (skeletal diagrams, reconstructions, fossil photos).
* **PhyloPic** — silhouettes, looked up by species, then genus, then clade.
* **Gallery** — per taxon, the files its Wikipedia articles show and the files
  of its Commons category (fossils, teeth, reconstructions...).

Everything found is stored; license filtering (allowlist, no NC/ND) and the
choice of the best image per taxon happen in dbt, where they are tested.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import mwparserfromhell as mw

from paleo.http import HttpError, get_json
from paleo.ingest.articles import store as articles_store
from paleo.ingest.pbdb import looks_like_taxon
from paleo.ingest.pbdb import store as pbdb_store
from paleo.interim import latest_rows
from paleo.names import mentions_other_taxon
from paleo.store import RawStore

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
PHYLOPIC_API = "https://api.phylopic.org"
PHYLOPIC_ACCEPT = "application/vnd.phylopic.v2+json"
COMMONS_BATCH = 50
REFRESH_DAYS = 7


@dataclass(frozen=True)
class ImageResult:
    commons_files: int
    phylopic_queries: int
    phylopic_found: int
    new_versions: int


def commons_store(raw_root: Path | None = None) -> RawStore:
    return RawStore("commons", "files", raw_root=raw_root)


def phylopic_store(raw_root: Path | None = None) -> RawStore:
    # The build number changes whenever PhyloPic republishes; it is not content.
    return RawStore("phylopic", "nodes", volatile={"build"}, raw_root=raw_root)


# --------------------------------------------------------------------------- inputs


def commons_files(interim_root: Path) -> list[str]:
    """File names from the "Images" column of the new-taxa tables."""
    files = {f.strip() for row in latest_rows(interim_root, "new_taxa") for f in row["images"]}
    return sorted(f for f in files if f)


def phylopic_queries(interim_root: Path, raw_root: Path | None = None) -> list[str]:
    """Names to look up on PhyloPic: each taxon, its genus and candidate clades.

    * New taxa: name, genus, and the groups linked in their notes
      ("A member of the family Peirosauridae").
    * Known taxa (found in PBDB): name, genus, parent clade, family and order
      (PBDB leaves family/order unspecified for many dinosaurs, so the parent
      clade is often the only usable fallback).
    """
    names: set[str] = set()
    for row in latest_rows(interim_root, "new_taxa"):
        name = row.get("name") or ""
        names.update({name, name.split(" ")[0], *(row.get("note_links") or [])})
    taxa = pbdb_store(raw_root)
    for key in taxa.stored_keys():
        latest = taxa.latest(key)
        if not latest or not latest["payload"]["found"]:
            continue
        names.add(key)
        for record in latest["payload"]["records"]:
            for field in ("genus", "parent_name", "family", "order"):
                value = record.get(field)
                if value and not value.startswith("NO_"):
                    names.add(value)
    return sorted(n for n in names if n and looks_like_taxon(n))


def gallery_store(raw_root: Path | None = None) -> RawStore:
    """Per taxon: files its Wikipedia articles use and files in its Commons category."""
    return RawStore("commons", "taxon_files", raw_root=raw_root)


_FILE_LINK = re.compile(r"\[\[\s*(?:File|Image|Archivo|Imagen)\s*:\s*([^|\]]+)", re.IGNORECASE)
_FILE_PARAM = re.compile(
    r"^\s*\|\s*(?:image\d*|imagen\d*|skeleton|life_image)\s*=\s*([^|\n<]+)",
    re.IGNORECASE | re.MULTILINE,
)
_GALLERY_LINE = re.compile(
    r"^\s*(?:(?:File|Image|Archivo|Imagen)\s*:)?\s*([^|\n<>]+\.(?:jpe?g|png|svg|gif|webp|tiff?))\s*(?:\||$)",
    re.IGNORECASE | re.MULTILINE,
)


def article_files(wikitext: str, taxon: str) -> list[str]:
    """Image files of the taxon in its Wikipedia article: links, infobox parameters
    and galleries; not the relatives drawn in cladograms nor files named after
    another taxon."""
    code = mw.parse(wikitext)
    for template in code.filter_templates(recursive=False):
        if str(template.name).strip().lower().startswith(("clade", "cladogram")):
            code.remove(template)
    wikitext = str(code)
    found: list[str] = []
    galleries = re.findall(r"<gallery[^>]*>(.*?)</gallery>", wikitext, re.DOTALL | re.IGNORECASE)
    for match in [
        *_FILE_PARAM.findall(wikitext),
        *_FILE_LINK.findall(wikitext),
        *(m for g in galleries for m in _GALLERY_LINE.findall(g)),
    ]:
        name = " ".join(match.replace("_", " ").split())
        name = name.removeprefix("File:").removeprefix("Archivo:")
        is_image = re.search(r"\.(?:jpe?g|png|svg|gif|webp|tiff?)$", name, re.IGNORECASE)
        if is_image and name not in found and not mentions_other_taxon(name, taxon):
            found.append(name)
    return found


def new_taxa_names(interim_root: Path) -> set[str]:
    return {row["name"] for row in latest_rows(interim_root, "new_taxa") if row.get("name")}


def gallery_taxa(interim_root: Path, raw_root: Path | None = None) -> dict[str, list[str]]:
    """Every taxon with a page -> files used by its Wikipedia articles (EN, then ES)."""
    out: dict[str, list[str]] = {}
    for row in latest_rows(interim_root, "new_taxa"):
        if row.get("name"):
            out.setdefault(row["name"], [])
    taxa = pbdb_store(raw_root)
    for key in taxa.stored_keys():
        latest = taxa.latest(key)
        if latest and latest["payload"]["found"]:
            out.setdefault(key, [])
    for lang in ("en", "es"):
        store = articles_store(lang, raw_root)
        for key in store.stored_keys():
            latest = store.latest(key)
            payload = latest["payload"] if latest else {}
            taxon = payload.get("taxon")
            if taxon in out and payload.get("wikitext"):
                files = article_files(payload["wikitext"], taxon)
                out[taxon] += [f for f in files if f not in out[taxon]]
    return out


def _category_members(client: httpx.Client, category: str, kinds: str, limit: int) -> list[str]:
    body = get_json(
        client,
        COMMONS_API,
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": kinds,
            "cmlimit": str(limit),
        },
    )
    return [m["title"] for m in body.get("query", {}).get("categorymembers", [])]


def fetch_category_files(
    client: httpx.Client,
    taxon: str,
    *,
    genus_fallback: bool = False,
    limit: int = 50,
    subcategories: int = 6,
    per_sub: int = 10,
) -> list[str]:
    """Files of the Commons category named after the taxon, plus a few from its
    subcategories that start with the same name ("Tyrannosaurus rex skulls").

    Commons often files a well-known species under its genus ("Tyrannosaurus rex"
    is empty, "Tyrannosaurus" is not). ``genus_fallback`` then uses the genus
    category; only for known taxa, never for a new species of a known genus.
    Files named after another taxon are left out.
    """
    names = [taxon]
    genus = taxon.split(" ")[0]
    if genus_fallback and genus != taxon:
        names.append(genus)
    files: list[str] = []
    for name in names:
        members = _category_members(client, f"Category:{name}", "file|subcat", limit)
        found = [m.split(":", 1)[1] for m in members if m.startswith("File:")]
        subs = [m for m in members if m.startswith(f"Category:{name} ")][:subcategories]
        for sub in subs:
            found += [m.split(":", 1)[1] for m in _category_members(client, sub, "file", per_sub)]
        for file in found:
            if file not in files and not mentions_other_taxon(file, taxon):
                files.append(file)
        if files:
            break
    return files


# --------------------------------------------------------------------------- Commons


def fetch_commons(client: httpx.Client, files: list[str]) -> dict[str, dict[str, Any]]:
    """Commons metadata (license, author, URLs) for up to 50 files.

    Files missing on Commons (e.g. local non-free uploads) come back with
    ``found: False`` and are never used.
    """
    body = get_json(
        client,
        COMMONS_API,
        {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "maxlag": "5",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": "800",
            "titles": "|".join(f"File:{f}" for f in files),
        },
    )
    query = body.get("query", {})
    # MediaWiki normalizes titles ("File:A_b.png" -> "File:A b.png").
    normalized = {n["to"]: n["from"] for n in query.get("normalized", [])}
    out: dict[str, dict[str, Any]] = {f: {"file": f, "found": False} for f in files}
    for page in query.get("pages", []):
        title = normalized.get(page["title"], page["title"])
        requested = title.split(":", 1)[1] if ":" in title else title
        if requested not in out or page.get("missing") or not page.get("imageinfo"):
            continue
        info = page["imageinfo"][0]
        meta = {k: v.get("value") for k, v in (info.get("extmetadata") or {}).items()}
        out[requested] = {
            "file": requested,
            "found": True,
            "title": page["title"],
            "url": info.get("url"),
            "thumb_url": info.get("thumburl"),
            "description_url": info.get("descriptionurl"),
            "mime": info.get("mime"),
            "width": info.get("width"),
            "height": info.get("height"),
            "license_short_name": meta.get("LicenseShortName"),
            "license_url": meta.get("LicenseUrl"),
            "usage_terms": meta.get("UsageTerms"),
            "artist_html": meta.get("Artist"),
            "credit_html": meta.get("Credit"),
            "attribution_required": meta.get("AttributionRequired"),
            "restrictions": meta.get("Restrictions"),
            "description_html": meta.get("ImageDescription"),
            "categories": meta.get("Categories"),
        }
    return out


# --------------------------------------------------------------------------- PhyloPic


def phylopic_build(client: httpx.Client) -> int:
    """Current PhyloPic build: the API root redirects to ``/?build=<n>``."""
    response = client.get(PHYLOPIC_API + "/", headers={"Accept": PHYLOPIC_ACCEPT})
    build = parse_qs(urlparse(str(response.url)).query).get("build")
    if not build:
        raise RuntimeError("PhyloPic did not report a build number")
    return int(build[0])


def _phylopic_image(image: dict[str, Any]) -> dict[str, Any]:
    links = image.get("_links", {})

    def href(name: str) -> str | None:
        value = links.get(name)
        return value.get("href") if isinstance(value, dict) else None

    raster = links.get("rasterFiles") or []
    return {
        "uuid": image.get("uuid"),
        "attribution": image.get("attribution"),
        "contributor": (links.get("contributor") or {}).get("title"),
        "license_url": href("license"),
        "vector_url": href("vectorFile"),
        "raster_url": raster[0].get("href") if raster else None,
        "page_url": f"https://www.phylopic.org/images/{image.get('uuid')}",
    }


def _phylopic_nodes(client: httpx.Client, name: str, build: int) -> dict[str, Any]:
    return get_json(
        client,
        PHYLOPIC_API + "/nodes",
        {
            "build": build,
            "filter_name": name.lower(),
            "page": 0,
            "embed_items": "true",
            "embed_primaryImage": "true",
        },
        headers={"Accept": PHYLOPIC_ACCEPT},
    )


def fetch_phylopic(client: httpx.Client, name: str, build: int) -> dict[str, Any]:
    """Primary silhouette of the PhyloPic node named exactly ``name``."""
    try:
        body = _phylopic_nodes(client, name, build)
    except HttpError as exc:
        if exc.status_code == 404:  # PhyloPic answers 404 when nothing matches
            return {"name": name, "found": False, "build": build}
        raise
    items = body.get("_embedded", {}).get("items", [])
    node = next(
        (
            n
            for n in items
            if any(
                part.get("class") == "scientific" and part.get("text", "").lower() == name.lower()
                for part in (n.get("names") or [[]])[0]
            )
        ),
        None,
    )
    if node is None:
        return {"name": name, "found": False, "build": build}
    image = node.get("_embedded", {}).get("primaryImage")
    return {
        "name": name,
        "found": image is not None,
        "build": build,
        "node_uuid": node.get("uuid"),
        "image": _phylopic_image(image) if image else None,
    }


# --------------------------------------------------------------------------- entry


def _batches(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def ingest_images(
    client: httpx.Client,
    interim_root: Path,
    *,
    raw_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> ImageResult:
    new_versions = 0

    gallery = gallery_store(raw_root)
    gallery_files: set[str] = set()
    new_taxa = new_taxa_names(interim_root)
    for taxon, from_articles in gallery_taxa(interim_root, raw_root).items():
        # Article files come from raw data we already have, so they are always
        # recomputed; only the Commons category is fetched when it is stale.
        latest = gallery.latest(taxon)
        fetch = refresh or latest is None or not gallery.is_fresh(taxon, REFRESH_DAYS, today)
        category = (
            fetch_category_files(client, taxon, genus_fallback=taxon not in new_taxa)
            if fetch
            else latest["payload"]["category_files"]
        )
        payload = {"taxon": taxon, "article_files": from_articles, "category_files": category}
        saved = gallery.save_if_changed(taxon, payload, today, mark_checked=fetch)
        new_versions += saved.created
        gallery_files.update(from_articles, category)
    gallery.flush()

    commons = commons_store(raw_root)
    files = [
        f
        for f in sorted(set(commons_files(interim_root)) | gallery_files)
        if refresh or not commons.is_fresh(f, REFRESH_DAYS, today)
    ]
    for batch in _batches(files, COMMONS_BATCH):
        for file, payload in fetch_commons(client, batch).items():
            new_versions += commons.save_if_changed(file, payload, today).created
    commons.flush()

    phylopic = phylopic_store(raw_root)
    queries = [
        n
        for n in phylopic_queries(interim_root, raw_root)
        if refresh or not phylopic.is_fresh(n, REFRESH_DAYS, today)
    ]
    found = 0
    if queries:
        build = phylopic_build(client)
        for i, name in enumerate(queries, start=1):
            payload = fetch_phylopic(client, name, build)
            found += payload["found"]
            new_versions += phylopic.save_if_changed(name, payload, today).created
            if i % 50 == 0:
                phylopic.flush()
    phylopic.flush()
    return ImageResult(len(files), len(queries), found, new_versions)
