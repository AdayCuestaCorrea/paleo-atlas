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
                   s.doi, s.title, s.journal, s.publication_year, s.reliability_status,
                   s.is_peer_reviewed_journal, s.is_preprint, s.is_retracted,
                   s.is_corrected, s.in_trusted_journal
            from main.fct_taxon_event as e
            left join main.dim_study as s using (study_id)
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
    finally:
        con.close()
    return SiteData(taxa, dict(events), texts, dict(facts), dict(citations))


def numbered_text(data: SiteData, taxon_key: str, lang: str) -> dict[str, Any] | None:
    """Sections whose sentences carry citation numbers, plus the numbered sources.

    Facts from the same source share a number; numbers follow first appearance.
    """
    text = data.texts.get((taxon_key, lang))
    if not text:
        return None
    facts = data.facts.get(taxon_key, {})
    citations = data.citations.get(taxon_key, {})
    numbers: dict[str, int] = {}
    sources: list[dict[str, Any]] = []
    sections = []
    for section in text["sections"]:
        sentences = []
        for sentence in section["sentences"]:
            refs = []
            for fact_id in sentence["fact_ids"]:
                chunk = facts.get(fact_id, {}).get("chunk_id")
                if chunk is None or chunk not in citations:
                    continue
                if chunk not in numbers:
                    numbers[chunk] = len(numbers) + 1
                    sources.append({"number": numbers[chunk], **citations[chunk]})
                refs.append(numbers[chunk])
            sentences.append({"text": sentence["text"], "refs": sorted(set(refs))})
        sections.append({"section": section["section"], "sentences": sentences})
    return {"sections": sections, "sources": sources, "generator": text["generator"]}
