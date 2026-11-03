"""Citable source chunks for one taxon.

Every fact the pipeline writes must come from one of these chunks, and every
chunk knows its citation and license. ``public_quote`` says whether a verbatim
snippet of it may be published: yes for Wikipedia (CC BY-SA) and PBDB (CC BY),
no for publisher abstracts, which may be copyrighted (ALCANCE.md §19).
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mwparserfromhell as mw

from paleo.ingest import articles, crossref, pbdb
from paleo.interim import latest_rows
from paleo.parse.wikipedia import plain_text, strip_block_markup
from paleo.store import safe_key

MAX_CHUNK_CHARS = 6_000  # ~1,500 tokens: several chunks fit under Groq's 8K tokens/minute
SKIP_SECTIONS = {
    "references",
    "external links",
    "see also",
    "notes",
    "further reading",
    "bibliography",
    "gallery",
    "referencias",
    "enlaces externos",
    "véase también",
    "notas",
    "bibliografía",
    "galería",
}
TAXOBOX = re.compile(r"(taxobox|speciesbox|automatic taxobox|ficha de taxón)", re.I)


def taxon_key(name: str) -> str:
    """Same key as the dbt `taxon_key` macro: "Tyrannosaurus rex" -> "tyrannosaurus-rex"."""
    return re.sub(r"[^A-Za-z0-9]+", "-", name.strip()).lower()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str  # wikipedia_table | wikipedia_article | wikipedia_research | pbdb | crossref
    lang: str
    title: str
    url: str | None
    license: str
    public_quote: bool
    text: str
    doi: str | None = None

    def citation(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "doi": self.doi,
            "license": self.license,
        }


def _split(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split on paragraph (then sentence) boundaries so no piece exceeds ``limit``."""
    pieces: list[str] = []
    current = ""
    for para in re.split(r"\n\s*\n", text):
        units = [para] if len(para) <= limit else re.split(r"(?<=[.!?])\s+", para)
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            if len(current) + len(unit) + 2 > limit and current:
                pieces.append(current)
                current = ""
            current = f"{current}\n\n{unit}".strip() if current else unit[:limit]
    if current:
        pieces.append(current)
    return pieces


def _taxobox_text(code: mw.wikicode.Wikicode) -> str:
    for template in code.filter_templates(recursive=False):
        if TAXOBOX.search(str(template.name)):
            lines = []
            for param in template.params:
                value = plain_text(param.value)
                if value and not str(param.name).strip().lower().startswith(("image", "imagen")):
                    lines.append(f"{str(param.name).strip()}: {value}")
            return "\n".join(lines)
    return ""


def article_chunks(taxon: str, lang: str, record: dict[str, Any]) -> list[Chunk]:
    """Sections of a Wikipedia article as chunks (references and boilerplate removed)."""
    if not record.get("found"):
        return []
    code = mw.parse(record["wikitext"])
    title = record["title"]
    url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}?oldid={record['revid']}"
    license_ = "CC BY-SA 4.0"
    key = taxon_key(taxon)
    chunks: list[Chunk] = []

    def add(label: str, text: str) -> None:
        for i, piece in enumerate(_split(text), start=1):
            chunks.append(
                Chunk(
                    f"{key}:{lang}wiki:{len(chunks) + 1}",
                    "wikipedia_article",
                    lang,
                    f"{title} ({label}{f', part {i}' if i > 1 else ''})",
                    url,
                    license_,
                    True,
                    piece,
                )
            )

    if taxobox := _taxobox_text(code):
        add("taxobox", taxobox)
    for section in code.get_sections(include_lead=True, flat=True):
        headings = section.filter_headings(recursive=False)
        label = plain_text(headings[0].title) if headings else "introduction"
        if label.lower() in SKIP_SECTIONS:
            continue
        body = str(section)[len(str(headings[0])) :] if headings else str(section)
        body_code = mw.parse(body)
        for template in body_code.filter_templates(recursive=False):
            if TAXOBOX.search(str(template.name)):
                body_code.remove(template)
        text = _paragraph_text(body_code)
        if len(text) > 40:
            add(label, text)
    return chunks


def _paragraph_text(code: mw.wikicode.Wikicode) -> str:
    """Plain text keeping paragraph breaks (``plain_text`` collapses whitespace)."""
    cleaned = str(strip_block_markup(code))  # templates/refs may span several paragraphs
    return "\n\n".join(p for p in (plain_text(par) for par in re.split(r"\n\s*\n", cleaned)) if p)


def table_chunk(row: dict[str, Any]) -> Chunk:
    """The row of the yearly Wikipedia table, as text."""
    fields = [
        ("Name", row.get("name")),
        ("Novelty", row.get("novelty")),
        ("Status", row.get("status")),
        ("Authors", row.get("authors")),
        ("Age", row.get("age")),
        ("Type locality", row.get("type_locality")),
        ("Country", ", ".join(row.get("countries") or [])),
        ("Region", ", ".join(row.get("regions") or [])),
        ("Notes", row.get("notes")),
    ]
    page = row["page_title"]
    return Chunk(
        f"{taxon_key(row['name'])}:table:1",
        "wikipedia_table",
        "en",
        f"{page} (table of new taxa)",
        f"https://en.wikipedia.org/wiki/{page.replace(' ', '_')}?oldid={row['revid']}",
        "CC BY-SA 4.0",
        True,
        "\n".join(f"{k}: {v}" for k, v in fields if v),
    )


def pbdb_chunk(taxon: str, raw_root: Path | None) -> Chunk | None:
    """PBDB record of the taxon, or of its genus for a new species of a known genus."""
    taxa = pbdb.store(raw_root)
    for name in dict.fromkeys([taxon, taxon.split(" ")[0]]):
        latest = taxa.latest(name)
        if not latest or not latest["payload"]["found"]:
            continue
        r = latest["payload"]["records"][0]
        lines = [
            f"PBDB name: {r.get('taxon_name')} ({r.get('taxon_rank')}), {r.get('taxon_attr', '')}",
            f"Parent group: {r.get('parent_name')}",
            f"Family: {r.get('family')}",
            f"Class: {r.get('class')}",
            f"Time range: {r.get('early_interval')} to "
            f"{r.get('late_interval') or r.get('early_interval')} "
            f"({r.get('firstapp_max_ma')} to {r.get('lastapp_min_ma')} million years ago)",
            f"Fossil occurrences recorded: {r.get('n_occs')}",
        ]
        if name != taxon:
            lines.insert(
                0,
                f"NOTE: PBDB has no record for {taxon} yet. This record describes its genus "
                f"{name}; nothing here is specific to {taxon}.",
            )
        text = "\n".join(line for line in lines if "None" not in line and "NO_" not in line)
        return Chunk(
            f"{taxon_key(taxon)}:pbdb:1",
            "pbdb",
            "en",
            f"Paleobiology Database: {r.get('taxon_name')}",
            f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_no={r.get('taxon_no')}",
            "CC BY 4.0",
            True,
            text,
        )
    return None


def study_title(work: dict[str, Any]) -> str:
    """Plain-text title of a Crossref work (tags removed, entities decoded)."""
    raw = " ".join((work.get("title") or [""])[0].split())
    return re.sub(r"<[^>]+>", "", html.unescape(html.unescape(raw)))


def crossref_chunks(
    taxon: str, doi: str | None, raw_root: Path | None, cache_root: Path
) -> list[Chunk]:
    """Naming study metadata (public) and its abstract (local cache, never quoted)."""
    if not doi:
        return []
    latest = crossref.store(raw_root).latest(doi)
    if not latest or not latest["payload"].get("found"):
        return []
    work = latest["payload"]["work"]
    title = study_title(work)
    journal = html.unescape((work.get("container-title") or [""])[0])
    year = ((work.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    authors = ", ".join(
        f"{a.get('given', '')} {a.get('family', '')}".strip() for a in work.get("author", [])[:12]
    )
    url = f"https://doi.org/{doi}"
    key = taxon_key(taxon)
    chunks = [
        Chunk(
            f"{key}:study:1",
            "crossref",
            "en",
            f"{title} ({journal}, {year})",
            url,
            "metadata (Crossref)",
            True,
            f"Study title: {title}\nJournal: {journal}\nYear: {year}\nAuthors: {authors}",
            doi,
        )
    ]
    path = cache_root / "crossref_abstracts" / f"{safe_key(doi)}.json"
    if path.exists():
        abstract = json.loads(path.read_text(encoding="utf-8")).get("abstract", "")
        abstract = " ".join(re.sub(r"<[^>]+>", " ", abstract).split())
        if abstract:
            chunks.append(
                Chunk(
                    f"{key}:abstract:1",
                    "crossref",
                    "en",
                    f"{title} (abstract)",
                    url,
                    "publisher copyright",
                    False,  # facts allowed, verbatim quotes never published
                    abstract[:MAX_CHUNK_CHARS],
                    doi,
                )
            )
    return chunks


def research_chunks(taxon: str, interim_root: Path) -> list[Chunk]:
    """Research bullets of the yearly page that mention the taxon."""
    genus = taxon.split(" ")[0]
    out = []
    for item in latest_rows(interim_root, "research"):
        mentioned = set(item.get("links") or []) | set(item.get("italic_names") or [])
        if taxon not in mentioned and not (genus != taxon and genus in mentioned):
            continue
        ref = next((r for r in item.get("references") or [] if r.get("doi")), None)
        doi = ref["doi"] if ref else None
        out.append(
            Chunk(
                f"{taxon_key(taxon)}:research:{len(out) + 1}",
                "wikipedia_research",
                "en",
                f"{item['page_title']} (research: {item['section_path'][-1]})",
                f"https://doi.org/{doi}" if doi else None,
                "CC BY-SA 4.0",
                True,
                item["text"][:MAX_CHUNK_CHARS],
                doi,
            )
        )
    return out


def chunks_for(
    taxon: str,
    *,
    interim_root: Path,
    raw_root: Path | None = None,
    cache_root: Path,
) -> list[Chunk]:
    """All citable chunks for a new taxon, in a stable order."""
    row = next((r for r in latest_rows(interim_root, "new_taxa") if r.get("name") == taxon), None)
    if row is None:
        raise LookupError(f"{taxon!r} is not a new taxon of the parsed pages")
    chunks = [table_chunk(row)]
    for lang in articles.LANGUAGES:
        latest = articles.store(lang, raw_root).latest(taxon)
        if latest:
            chunks.extend(article_chunks(taxon, lang, latest["payload"]))
    if c := pbdb_chunk(taxon, raw_root):
        chunks.append(c)
    doi = next((r["doi"] for r in row.get("references") or [] if r.get("doi")), None)
    chunks.extend(crossref_chunks(taxon, doi, raw_root, cache_root))
    chunks.extend(research_chunks(taxon, interim_root))
    return chunks


# --- Genera of the encyclopedia (Phase 3, H6) -----------------------------------------

# Per language, characters of article text a genus page reads at most (taxobox, lead and
# the first sections, in that order): the long articles (Tyrannosaurus) would otherwise
# take an hour of local GPU each, and the writer uses 24 facts at most anyway.
GENUS_SOURCE_CHARS = {"en": 30_000, "es": 10_000}


def catalog_index(raw_root: Path | None) -> dict[str, dict[str, Any]]:
    key = str(raw_root)
    if key not in _CATALOGS:
        catalog = pbdb.catalog_store(raw_root)
        index: dict[str, dict[str, Any]] = {}
        for clade in pbdb.scope_clades():
            latest = catalog.latest(clade.pbdb_base_name)
            for r in (latest or {}).get("payload", {}).get("records", []):
                index.setdefault(r.get("taxon_name") or "", r)
        _CATALOGS[key] = index
    return _CATALOGS[key]


_CATALOGS: dict[str, dict[str, dict[str, Any]]] = {}


def catalog_chunk(genus: str, raw_root: Path | None) -> Chunk | None:
    """The genus in the PBDB catalog of its clade (CC BY), as text."""
    r = catalog_index(raw_root).get(genus)
    if r is None:
        return None
    lines = [
        f"PBDB name: {r.get('taxon_name')} (genus), {r.get('taxon_attr', '')}",
        f"Parent group: {r.get('parent_name')}",
        f"Family: {r.get('family')}",
        f"Class: {r.get('class')}",
        f"Type species: {r.get('type_taxon')}",
        f"Time range: {r.get('early_interval')} to "
        f"{r.get('late_interval') or r.get('early_interval')} "
        f"({r.get('firstapp_max_ma')} to {r.get('lastapp_min_ma')} million years ago)",
        f"Fossil occurrences recorded: {r.get('n_occs')}",
    ]
    text = "\n".join(line for line in lines if "None" not in line and "NO_" not in line)
    return Chunk(
        f"{taxon_key(genus)}:pbdb:1",
        "pbdb",
        "en",
        f"Paleobiology Database: {r.get('taxon_name')}",
        f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_no={r.get('taxon_no')}",
        "CC BY 4.0",
        True,
        text,
    )


def _capped(chunks: list[Chunk], limit: int) -> list[Chunk]:
    out, used = [], 0
    for c in chunks:
        if used + len(c.text) > limit and out:
            break
        out.append(c)
        used += len(c.text)
    return out


def genus_chunks_for(
    genus: str, *, interim_root: Path, raw_root: Path | None = None, cache_root: Path | None = None
) -> list[Chunk]:
    """All citable chunks for a genus page: its Wikipedia articles (capped), its PBDB
    catalog record and the research items of the yearly pages that mention it."""
    from paleo.ingest.genus_articles import text_store

    chunks: list[Chunk] = []
    for lang in articles.LANGUAGES:
        latest = text_store(lang, cache_root).latest(genus)
        if latest:
            found = article_chunks(genus, lang, latest["payload"])
            chunks.extend(_capped(found, GENUS_SOURCE_CHARS[lang]))
    if not chunks:
        raise LookupError(f"{genus!r} has no stored Wikipedia article")
    if c := catalog_chunk(genus, raw_root):
        chunks.append(c)
    chunks.extend(research_chunks(genus, interim_root))
    return chunks
