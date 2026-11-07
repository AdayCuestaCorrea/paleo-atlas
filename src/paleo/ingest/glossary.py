"""The source of each glossary term: the lead of its Wikipedia article (§12.2, Phase 5).

For each term of ``dbt/seeds/glossary_terms.csv`` the English article named like the
term (after redirects) is looked up, and its Spanish counterpart through the language
links. A lead is accepted only if the article is not a disambiguation page and its
lead names the term or one of its forms: otherwise the term has no source and gets no
definition.

The lead text (CC BY-SA) stays in the local cache (data/cache/wikimedia/), like the
genus articles; the versioned raw store keeps what was found: titles and revision ids
(oldid), so every definition can cite the exact revision it was written from.
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from paleo.config import get_paths, project_root
from paleo.glossary.terms import LATIN, form_pattern
from paleo.http import HttpError, get_json
from paleo.store import RawStore

API = "https://{lang}.wikipedia.org/w/api.php"
BATCH = 20  # the most leads the API returns in one request (exlimit)
REFRESH_DAYS = 30
log = logging.getLogger(__name__)


@dataclass
class GlossarySourcesResult:
    terms: int = 0
    skipped_fresh: int = 0
    accepted: dict[str, int] = field(default_factory=lambda: {"en": 0, "es": 0})
    new_versions: int = 0
    failed: int = 0


def index_store(raw_root: Path | None = None) -> RawStore:
    return RawStore("wikimedia", "glossary", raw_root=raw_root)


def lead_store(lang: str, cache_root: Path | None = None) -> RawStore:
    root = cache_root if cache_root is not None else get_paths().data / "cache"
    return RawStore("wikimedia", f"glossary_lead_{lang}", raw_root=root)


def load_terms(seed: Path | None = None) -> list[dict[str, Any]]:
    path = seed or project_root() / "dbt" / "seeds" / "glossary_terms.csv"
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for lang in ("en", "es"):
            r[f"all_{lang}"] = [r[f"term_{lang}"], *filter(None, r[f"forms_{lang}"].split("|"))]
    return rows


def _batches(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def fetch_leads(client: httpx.Client, lang: str, titles: list[str]) -> dict[str, dict[str, Any]]:
    """Asked title -> {title, revid, lead, disambiguation, es_title} (title None if the
    page does not exist)."""
    params = {
        "action": "query", "format": "json", "formatversion": 2, "redirects": 1,
        "titles": "|".join(titles), "prop": "extracts|revisions|pageprops|langlinks",
        "exintro": 1, "explaintext": 1, "exlimit": "max", "rvprop": "ids",
        "lllang": "es", "lllimit": "max",
    }  # fmt: skip
    body = get_json(client, API.format(lang=lang), params=params)
    query = body.get("query", {})
    final = {t: t for t in titles}
    for step in ("normalized", "redirects"):
        moves = {m["from"]: m["to"] for m in query.get(step, [])}
        final = {t: moves.get(f, f) for t, f in final.items()}
    pages = {p["title"]: p for p in query.get("pages", [])}
    out = {}
    for asked in titles:
        page = pages.get(final[asked], {})
        if not page or page.get("missing") or page.get("invalid"):
            out[asked] = {"title": None}
            continue
        links = page.get("langlinks") or []
        out[asked] = {
            "title": page["title"],
            "revid": (page.get("revisions") or [{}])[0].get("revid"),
            "lead": (page.get("extract") or "").strip(),
            "disambiguation": "disambiguation" in (page.get("pageprops") or {}),
            "es_title": links[0]["title"] if links else None,
        }
    return out


def accepted(page: dict[str, Any], forms: list[str]) -> bool:
    """A real article whose lead names the term, or a group's article named in Latin
    after it (nodosaurid -> Nodosauridae, whose lead uses the Latin name)."""
    if not (page.get("title") and page.get("lead") and not page.get("disambiguation")):
        return False
    title = page["title"].lower()
    same_root = LATIN.search(title) is not None and any(
        len(f) >= 7 and title.startswith(f.lower()[:7]) for f in forms
    )
    return bool(form_pattern(forms).search(page["lead"]) or same_root)


def ingest_glossary_sources(
    client: httpx.Client,
    terms: list[dict[str, Any]],
    *,
    raw_root: Path | None = None,
    cache_root: Path | None = None,
    refresh: bool = False,
    today: dt.date | None = None,
) -> GlossarySourcesResult:
    index = index_store(raw_root)
    leads = {lang: lead_store(lang, cache_root) for lang in ("en", "es")}
    pending = [t for t in terms
               if refresh or not index.is_fresh(t["term_id"], REFRESH_DAYS, today)]  # fmt: skip
    result = GlossarySourcesResult(terms=len(terms), skipped_fresh=len(terms) - len(pending))
    found: dict[str, dict[str, dict[str, Any]]] = {t["term_id"]: {} for t in pending}
    for batch in _batches(pending, BATCH):
        asked = {t["term_id"]: t.get("source_en") or t["term_en"][:1].upper() + t["term_en"][1:]
                 for t in batch}  # fmt: skip
        try:
            en = fetch_leads(client, "en", sorted(set(asked.values())))
        except HttpError as exc:
            log.warning("Glossary leads (en) of %d terms failed: %s", len(batch), exc)
            result.failed += len(batch)
            continue
        for key, title in asked.items():
            found[key]["en"] = en[title]
        es_titles = {key: en[title]["es_title"] for key, title in asked.items()
                     if en[title].get("es_title")}  # fmt: skip
        if es_titles:
            try:
                es = fetch_leads(client, "es", sorted(set(es_titles.values())))
            except HttpError as exc:
                log.warning("Glossary leads (es) failed: %s", exc)
                es = {}
            for key, title in es_titles.items():
                if title in es:
                    found[key]["es"] = es[title]
    for t in pending:
        pages = found[t["term_id"]]
        if not pages:
            continue
        summary: dict[str, Any] = {"term_id": t["term_id"]}
        for lang in ("en", "es"):
            page = pages.get(lang) or {"title": None}
            ok = accepted(page, t[f"all_{lang}"])
            result.accepted[lang] += ok
            summary[lang] = {"title": page.get("title"), "revid": page.get("revid"),
                             "accepted": ok}  # fmt: skip
            if ok:
                leads[lang].save_if_changed(t["term_id"], {
                    "term_id": t["term_id"], "title": page["title"], "revid": page["revid"],
                    "lead": page["lead"],
                }, today)  # fmt: skip
        result.new_versions += index.save_if_changed(t["term_id"], summary, today).created
    index.flush()
    for store in leads.values():
        store.flush()
    return result
