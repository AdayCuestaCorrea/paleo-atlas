"""Load the dbt marts once and shape them for the templates.

The dataset is small (hundreds of taxa), so everything is read into memory with
a few queries instead of one query per page.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import duckdb


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cursor = con.execute(sql)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


@dataclass
class SiteData:
    taxa: list[dict[str, Any]]
    events: dict[str, list[dict[str, Any]]]  # taxon_key -> events, newest first
    texts: dict[tuple[str, str], dict[str, Any]]  # (taxon_key, lang) -> text
    facts: dict[str, dict[str, dict[str, Any]]]  # taxon_key -> fact_id -> fact
    citations: dict[str, dict[str, dict[str, Any]]]  # taxon_key -> chunk_id -> citation
    built_on: dt.date = field(default_factory=dt.date.today)
    images: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # gallery per taxon

    @property
    def by_key(self) -> dict[str, dict[str, Any]]:
        return {t["taxon_key"]: t for t in self.taxa}

    def all_events(self) -> list[dict[str, Any]]:
        """Events with an exact publication date, newest first (for "Latest" and the
        weekly recaps); vaguer dates only appear in each taxon's history."""
        out = []
        for key, events in self.events.items():
            taxon = self.by_key.get(key)
            for event in events:
                if (
                    event["date_precision"] == "day"
                    and event["event_date"]
                    and event["event_date"] <= self.built_on
                ):
                    out.append({**event, "taxon": taxon})
        return sorted(out, key=lambda e: (e["event_date"], e["taxon_key"]), reverse=True)


def load(warehouse: Path) -> SiteData:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        taxa = _rows(
            con,
            """
            select t.*, s.publication_year as naming_year
            from main.dim_taxon as t
            left join main.dim_study as s on s.doi = t.naming_doi
            order by t.page_type desc, t.taxon_name
            """,
        )
        events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in _rows(
            con,
            """
            select e.taxon_key, e.event_type, e.event_date, e.date_is_publication, e.date_precision,
                   e.study_id,
                   s.doi, s.title, t.title_es, s.journal, s.publication_year,
                   s.reliability_status, s.is_peer_reviewed_journal, s.is_preprint,
                   s.is_retracted, s.is_corrected, s.in_trusted_journal
            from main.fct_taxon_event as e
            left join main.dim_study as s using (study_id)
            left join main.stg_narrative__study_titles as t on t.doi = s.doi
            order by e.event_date desc nulls last, e.event_type
            """,
        ):
            events[row["taxon_key"]].append(row)
        texts = {
            (r["taxon_key"], r["lang"]): {**r, "sections": json.loads(r["sections"])}
            for r in _rows(
                con,
                "select taxon_key, lang, sections, generator, generated_at "
                "from main.fct_taxon_text where text_status = 'verified'",
            )
        }
        facts: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in _rows(con, "select * from main.stg_narrative__facts"):
            facts[row["taxon_key"]][row["fact_id"]] = row
        citations: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in _rows(con, "select * from main.stg_narrative__citations"):
            citations[row["taxon_key"]][row["chunk_id"]] = row
        images: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in _rows(con, "select * from main.fct_taxon_image order by taxon_key, image_rank"):
            images[row["taxon_key"]].append(row)
    finally:
        con.close()
    return SiteData(taxa, dict(events), texts, dict(facts), dict(citations), images=dict(images))


def _work(citation: dict[str, Any]) -> tuple[str, str]:
    """(work id, title) of a cited chunk. The sections and language editions of a
    Wikipedia article are one work, and so are a study and its abstract."""
    source, title = citation["source"], citation["title"] or ""
    if source == "wikipedia_article":
        return "wikipedia", title.split(" (")[0]
    if source == "crossref":
        return f"doi:{citation['doi']}", title.removesuffix(" (abstract)")
    return f"{source}:{citation['url']}", title


def _source(number: int, chunks: list[dict[str, Any]], lang: str) -> dict[str, Any]:
    """One numbered source with its links, the page's language first."""
    first = chunks[0]
    _, title = _work(first)
    if first["source"] == "crossref":
        study = next((c for c in chunks if not c["title"].endswith("(abstract)")), None)
        title = study["title"] if study else title  # "(Journal, year)" when known
    links: dict[str, str] = {}
    for c in chunks:
        url = c["url"] or ""
        edition = (urlparse(url).hostname or "").split(".")[0]  # es.wikipedia.org -> es
        links.setdefault(edition if edition in ("es", "en") else "", url)
    ordered = sorted(links.items(), key=lambda kv: (kv[0] != lang, kv[0]))
    licenses = sorted({c["license"] for c in chunks if c["license"]})
    return {
        "number": number,
        "source": first["source"],
        "title": title,
        "doi": first.get("doi"),
        "links": [{"lang": k, "url": v} for k, v in ordered if v],
        "license": " · ".join(licenses) if first["source"] != "crossref" else None,
    }


def numbered_text(data: SiteData, taxon_key: str, lang: str) -> dict[str, Any] | None:
    """Sections whose sentences carry citation numbers, plus the numbered sources.

    Facts from the same work share a number; numbers follow first appearance.
    """
    text = data.texts.get((taxon_key, lang))
    if not text:
        return None
    facts = data.facts.get(taxon_key, {})
    citations = data.citations.get(taxon_key, {})
    numbers: dict[str, int] = {}
    chunks_of: dict[str, list[dict[str, Any]]] = {}
    sections = []
    for section in text["sections"]:
        sentences = []
        for sentence in section["sentences"]:
            refs = []
            for fact_id in sentence["fact_ids"]:
                chunk = facts.get(fact_id, {}).get("chunk_id")
                if chunk is None or chunk not in citations:
                    continue
                work, _ = _work(citations[chunk])
                if work not in numbers:
                    numbers[work] = len(numbers) + 1
                    chunks_of[work] = []
                if citations[chunk] not in chunks_of[work]:
                    chunks_of[work].append(citations[chunk])
                refs.append(numbers[work])
            sentences.append({"text": sentence["text"], "refs": sorted(set(refs))})
        sections.append({"section": section["section"], "sentences": sentences})
    sources = [_source(numbers[w], chunks_of[w], lang) for w in numbers]
    return {"sections": sections, "sources": sources, "generator": text["generator"]}
