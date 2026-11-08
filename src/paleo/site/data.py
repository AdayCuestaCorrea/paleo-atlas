"""Load the dbt marts once and shape them for the templates.

Everything is read into memory with a few queries instead of one query per page:
a few thousand taxa (the encyclopedia genera) fit easily.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property
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
    last_checked: dt.date | None = None  # last change detection (pipeline run log)
    stats: dict[str, Any] = field(default_factory=dict)  # verification figures (§12.1, §17)
    gbif: dict[str, Any] | None = None  # the GBIF download the specimens come from (cite it)
    # Kinship neighbourhood per genus page and level ('group', 'up'), §11.2 (H7).
    neighborhood: dict[str, dict[str, list[dict[str, Any]]]] = field(default_factory=dict)
    # Old URLs of pages folded into another one (known species into their genus).
    redirects: list[dict[str, Any]] = field(default_factory=list)
    # Lowercase country code -> (lat, lon): median of PBDB's occurrences there (home map).
    country_centroids: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Pipeline run log and source freshness, for the data status page.
    runs: list[dict[str, Any]] = field(default_factory=list)
    freshness: list[dict[str, Any]] = field(default_factory=list)
    # Glossary terms with their published definitions (§12.2).
    glossary: list[dict[str, Any]] = field(default_factory=list)
    # News articles that are not noise (Phase 5), newest first.
    news: list[dict[str, Any]] = field(default_factory=list)
    # Size comparator (§11.3): adult body length of each taxon with one (estimates parsed),
    # and what to compare them with (seed reference_objects).
    sizes: dict[str, dict[str, Any]] = field(default_factory=dict)
    refs: list[dict[str, Any]] = field(default_factory=list)

    @cached_property
    def silhouettes(self) -> dict[str, str]:
        """PhyloPic silhouettes of the genus itself (not of its clade) for the tree."""
        return {
            t["taxon_key"]: t["image_url"]
            for t in self.taxa
            if t.get("image_source") == "phylopic"
            and t.get("image_level") == "taxon"
            and t.get("image_url")
        }

    def kinship(self, taxon: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """The neighbourhood of a page: its own, or its genus's for a species page."""
        return self.neighborhood.get(taxon["taxon_key"]) or self.neighborhood.get(
            taxon.get("genus_key") or "", {}
        )

    @cached_property
    def by_key(self) -> dict[str, dict[str, Any]]:
        return {t["taxon_key"]: t for t in self.taxa}

    def all_events(self) -> list[dict[str, Any]]:
        """Events with an exact publication date, newest first (for "Latest" and the
        weekly recaps); vaguer dates and the history backwards (origin 'backfill')
        only appear in each taxon's history."""
        out = []
        for key, events in self.events.items():
            taxon = self.by_key.get(key)
            for event in events:
                if (
                    event.get("origin", "tracked") == "tracked"
                    and event["date_precision"] == "day"
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
                   e.study_id, e.changed_fields, e.subject_name, e.related_name,
                   e.attribution, e.source_title, e.origin,
                   s.doi, s.title, t.title_es, s.journal, s.publication_year, s.language,
                   s.reliability_status, s.is_peer_reviewed_journal, s.is_preprint,
                   s.is_retracted, s.is_corrected, s.in_trusted_journal, s.in_doaj
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
        stats = _rows(
            con,
            """
            select
                (select count(*) from main.dim_taxon where page_type = 'new') as new_taxa,
                (select count(*) from main.fct_taxon_text join main.dim_taxon using (taxon_key)
                 where page_type = 'new' and lang = 'en' and text_status = 'verified')
                    as verified_en,
                (select count(*) from main.fct_taxon_text join main.dim_taxon using (taxon_key)
                 where page_type = 'new' and lang = 'es' and text_status = 'verified')
                    as verified_es,
                (select count(*) from main.dim_taxon
                 where page_type = 'genus' and wikipedia_article is not null)
                    as genera_with_article,
                (select count(*) from main.fct_taxon_text join main.dim_taxon using (taxon_key)
                 where page_type = 'genus' and lang = 'en' and text_status = 'verified')
                    as genus_verified_en,
                (select count(*) from main.fct_taxon_text join main.dim_taxon using (taxon_key)
                 where page_type = 'genus' and lang = 'es' and text_status = 'verified')
                    as genus_verified_es,
                (select sum(facts_accepted) from main.stg_narrative__fact_counts) as facts_ok,
                (select sum(facts_rejected) from main.stg_narrative__fact_counts) as facts_bad,
                -- Studies cited only by the history backwards are not checked (H4).
                (select count(*) from main.dim_study where reliability_status <> 'unchecked')
                    as studies,
                (select count(*) from main.dim_study where reliability_status = 'unchecked')
                    as unchecked_studies,
                (select count(*) from main.dim_study
                 where reliability_status = 'peer_reviewed') as peer_reviewed,
                (select count(*) from main.dim_study where reliability_status = 'preprint')
                    as preprints,
                (select count(*) from main.dim_study where in_doaj) as in_doaj
            """,
        )[0]
        gbif = _rows(
            con,
            """
            select d.doi, d.citation, d.total_records, d.created_at::date as created_on,
                   (select sum(gbif_specimens) from main.dim_taxon) as specimens,
                   (select count(gbif_specimens) from main.dim_taxon) as genera
            from main.stg_gbif__downloads as d
            where d.doi in (select gbif_doi from main.dim_taxon)
            order by d.created_at desc
            limit 1
            """,
        )
        neighborhood: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for row in _rows(
            con,
            "select * from main.fct_taxon_neighborhood "
            "order by taxon_key, level, common_depth, member_name",
        ):
            neighborhood[row["taxon_key"]][row["level"]].append(row)
        redirects = _rows(con, "select * from main.dim_taxon_redirect order by from_key")
        centroids = {
            r["code"]: (r["lat"], r["lon"])
            for r in _rows(
                con,
                """
                select lower(country_code) as code, median(latitude) as lat,
                       median(longitude) as lon
                from main.stg_pbdb__occurrences
                where country_code is not null and latitude is not null
                  and longitude is not null
                group by 1
                """,
            )
        }
        runs = _rows(con, "select * from main.stg_pipeline__runs order by started_at")
        freshness = _rows(con, "select * from main.fct_source_freshness order by sort")
        news = _rows(
            con,
            """
            select news_key, outlet, lang, title, url, summary, category, story_key,
                   published_at, taxon_keys
            from main.fct_news
            where category in ('new_species', 'research', 'revision')
            order by published_at desc nulls last, news_key
            """,
        )
        glossary = _rows(
            con,
            """
            select * replace (list_filter(forms_en, lambda f: f <> '') as forms_en,
                              list_filter(forms_es, lambda f: f <> '') as forms_es)
            from main.dim_glossary_term
            where published_en or published_es
            order by term_id
            """,
        )
        sizes = {
            r["taxon_key"]: {**r, "estimates": json.loads(r["estimates"])}
            for r in _rows(con, "select * from main.fct_taxon_size")
        }
        refs = _rows(
            con,
            """
            select r.*, a.label as silhouette_license, a.license_url as silhouette_license_url
            from main.reference_objects as r
            left join main.license_allowlist as a on a.license_id = r.silhouette_license_id
            order by case r.kind when 'people' then 1 when 'animals' then 2 else 3 end, r.max_m
            """,
        )
        last_checked = con.execute(
            "select max(started_at)::date from main.stg_pipeline__runs"
        ).fetchone()[0]
    finally:
        con.close()
    return SiteData(
        taxa, dict(events), texts, dict(facts), dict(citations),
        images=dict(images), last_checked=last_checked, stats=stats,
        gbif=gbif[0] if gbif else None,
        neighborhood={k: dict(v) for k, v in neighborhood.items()},
        redirects=redirects, country_centroids=centroids, runs=runs, freshness=freshness,
        glossary=glossary, news=news, sizes=sizes, refs=refs,
    )  # fmt: skip


def history(events: list[dict[str, Any]]) -> dict[str, Any]:
    """A taxon's timeline: the events tracked since the project started, then the
    history backwards grouped by decade, newest first (both lists newest first)."""
    recent = [e for e in events if e.get("origin", "tracked") == "tracked"]
    decades: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for e in events:
        if e.get("origin", "tracked") != "tracked" and e["event_date"]:
            decades[e["event_date"].year // 10 * 10].append(e)
    return {
        "recent": recent,
        "decades": [(d, decades[d]) for d in sorted(decades, reverse=True)],
        "backfill": sum(len(v) for v in decades.values()),
    }


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


TOPIC_ORDER = ["diet", "growth", "locomotion_senses", "behavior", "health"]
MIN_SENTENCES_FOR_TOPICS = 6


def groups(sentences: list[dict[str, Any]]) -> list[tuple[str | None, list[dict[str, Any]]]]:
    """A section's sentences under sub-headings (topic, sentences) when it is long and
    at least two topics have two sentences each; otherwise one untitled group, so a
    sparse page never gets headings over single sentences."""
    by_topic: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for s in sentences:
        by_topic[s.get("topic") if s.get("topic") in TOPIC_ORDER else None].append(s)
    rich = [t for t in TOPIC_ORDER if len(by_topic.get(t, [])) >= 2]
    if len(sentences) < MIN_SENTENCES_FOR_TOPICS or len(rich) < 2:
        return [(None, sentences)]
    out: list[tuple[str | None, list[dict[str, Any]]]] = []
    if by_topic.get(None):
        out.append((None, by_topic[None]))
    out += [(t, by_topic[t]) for t in TOPIC_ORDER if by_topic.get(t)]
    return out


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
            topic = sentence.get("topic")
            sentences.append({"text": sentence["text"], "refs": sorted(set(refs)), "topic": topic})
        sections.append(
            {"section": section["section"], "sentences": sentences, "groups": groups(sentences)}
        )
    sources = [_source(numbers[w], chunks_of[w], lang) for w in numbers]
    return {"sections": sections, "sources": sources, "generator": text["generator"]}
