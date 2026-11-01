"""Parse yearly Wikipedia paleontology pages into structured rows.

Two kinds of content are extracted from a page such as
"2026 in archosaur paleontology":

* **New taxa** — rows of the ``wikitable`` under each "New … taxa" heading.
* **Research items** — bullets under each "… research" heading: one study each,
  with its reference (usually with a DOI) and the wikilinks to the animals it
  is about. They become "new study" events in each taxon's history.

The bullet prose is Wikipedia text (CC BY-SA 4.0). It is kept only as an
internal source for fact extraction and is never published (ALCANCE.md §19).

The parser never fails silently: every anomaly is recorded in the row's
``parse_warnings`` so it can be counted and reviewed.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import mwparserfromhell as mw
from mwparserfromhell.nodes import Tag, Template
from mwparserfromhell.wikicode import Wikicode

from paleo.config import slugify_title

# Table header label -> field name. Unknown headers produce a warning.
COLUMN_MAP = {
    "name": "name",
    "novelty": "novelty",
    "status": "status",
    "authors": "authors",
    "age": "age",
    "type locality": "type_locality",
    "location": "type_locality",
    "country": "country",
    "notes": "notes",
    "images": "images",
}

DEFAULT_COLUMNS = (
    "name",
    "novelty",
    "status",
    "authors",
    "age",
    "type_locality",
    "country",
    "notes",
    "images",
)

CITE_FIELDS_YEAR = ("year", "date")
CITE_FIELDS_VENUE = ("journal", "website", "work", "publisher", "series")

# Italic text without a link that looks like a scientific name: "Tyrannosaurus",
# "Saurosuchus galilei", "Pinacosaurus hilwitnorum" (abbreviations like "T. rex"
# are skipped: they cannot be resolved without context).
_ITALIC_TEXT = re.compile(r"(?<!')''(?!')([^'\[\]{}<>|\n]+?)''(?!')")
_SCIENTIFIC_NAME = re.compile(r"^[A-Z][a-zë-]+(?: [a-z][a-z-]+){0,2}$")
_ITALIC_LINK = re.compile(r"''\s*\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]\s*''")
_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class Reference:
    template: str | None = None  # e.g. "cite journal", "cite biorxiv"
    doi: str | None = None
    title: str | None = None
    venue: str | None = None
    year: int | None = None
    url: str | None = None
    authors: list[str] = field(default_factory=list)
    ref_name: str | None = None


@dataclass
class NewTaxonRow:
    page_title: str
    revid: int
    section_path: list[str]
    row_index: int  # position within its table, 1-based
    table_index: int  # position of the table within the page, 1-based
    name: str | None = None
    name_link: str | None = None
    novelty: str | None = None
    status: str | None = None
    authors: str | None = None
    age: str | None = None
    age_links: list[str] = field(default_factory=list)
    type_locality: str | None = None
    type_locality_links: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)  # state/province in parentheses
    notes: str | None = None
    note_links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    revision_timestamp: str | None = None


@dataclass
class ResearchItem:
    page_title: str
    revid: int
    research_id: str
    section_path: list[str]
    text: str  # plain text, internal use only (CC BY-SA, never published)
    links: list[str] = field(default_factory=list)
    italic_links: list[str] = field(default_factory=list)  # most likely taxa
    italic_names: list[str] = field(default_factory=list)  # italic, unlinked names
    references: list[Reference] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    revision_timestamp: str | None = None


@dataclass
class ParsedPage:
    page_title: str
    revid: int
    new_taxa: list[NewTaxonRow]
    research: list[ResearchItem]
    revision_timestamp: str | None = None

    def warning_count(self) -> int:
        return sum(len(r.parse_warnings) for r in [*self.new_taxa, *self.research])


# --------------------------------------------------------------------------- helpers


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


# Inline templates whose text belongs to the sentence (glossary links, units…).
# Value: which positional parameter holds the text (-1 = the last one).
_TEXT_TEMPLATES = {
    "dinogloss": -1,
    "gloss": -1,
    "glossary link": -1,
    "nowrap": 0,
    "noitalic": 0,
    "small": 0,
    "sic": -1,
    "ill": 0,
    "lang": 1,
    "transl": -1,
    "taxon italics": 0,
    "taxon": 0,
    "nobold": 0,
}
_SYMBOL_TEMPLATES = {
    "nbsp": " ",
    "ndash": "\u2013",
    "mdash": "\u2014",
    "snd": " \u2013 ",
    "spaced ndash": " \u2013 ",
}
_CONVERT_TEMPLATES = {"convert", "cvt"}


def _template_text(template: Template) -> str | None:
    """Text a content template renders to, or None to drop the template."""
    name = _template_name(template)
    positional = [_clean(str(p.value)) for p in template.params if not p.showkey]
    if name in _SYMBOL_TEMPLATES:
        return _SYMBOL_TEMPLATES[name]
    if name in _CONVERT_TEMPLATES and len(positional) >= 2:
        # {{convert|8|m|ft}} -> "8 m"; {{convert|1|to|1.5|m}} -> "1 to 1.5 m"
        if len(positional) >= 4 and positional[1] in {"to", "-", "\u2013", "and", "or"}:
            return f"{positional[0]} {positional[1]} {positional[2]} {positional[3]}"
        return f"{positional[0]} {positional[1]}"
    if name in {"mya", "ma"} and positional:
        return f"{positional[0]} million years ago"
    if name.startswith("lang-") and positional:
        return positional[-1]
    if name in _TEXT_TEMPLATES and positional:
        index = _TEXT_TEMPLATES[name]
        return positional[index] if len(positional) > index else positional[-1]
    return None


def _plain(code: Wikicode | str) -> str:
    """Readable text: refs, files and markup removed; content templates expanded."""
    code = mw.parse(str(code))
    for tag in code.filter_tags(matches=lambda n: n.tag.lower() == "ref"):
        _safe_remove(code, tag)
    for template in code.filter_templates(recursive=False):
        text = _template_text(template)
        if text is not None:
            with contextlib.suppress(ValueError):
                code.replace(template, text)
    for link in code.filter_wikilinks():
        if str(link.title).strip().lower().startswith(("file:", "image:")):
            _safe_remove(code, link)
    return _clean(
        code.strip_code(normalize=True, collapse=True).replace("'''", "").replace("''", "")
    )


def _safe_remove(code: Wikicode, node: Any) -> None:
    with contextlib.suppress(ValueError):  # already removed together with its parent
        code.remove(node)


def _link_targets(code: Wikicode) -> list[str]:
    targets = []
    for link in code.filter_wikilinks():
        title = _clean(str(link.title).split("#")[0])
        if title and not title.lower().startswith(("file:", "image:", "category:")):
            targets.append(title)
    return list(dict.fromkeys(targets))


def _attr(tag: Tag, name: str) -> str | None:
    for attr in tag.attributes:
        if str(attr.name).strip().lower() == name:
            return _clean(str(attr.value)).strip("\"'") or None
    return None


def _template_name(template: Template) -> str:
    return _clean(str(template.name)).lower()


def _param(template: Template, *names: str) -> str | None:
    for name in names:
        if template.has(name):
            value = _plain(template.get(name).value)
            if value:
                return value
    return None


def _parse_cite(template: Template) -> Reference:
    ref = Reference(template=_template_name(template))
    ref.doi = _param(template, "doi")
    if ref.doi:
        ref.doi = ref.doi.lower()
    ref.title = _param(template, "title")
    ref.venue = _param(template, *CITE_FIELDS_VENUE)
    year_text = _param(template, *CITE_FIELDS_YEAR)
    if year_text and (match := _YEAR.search(year_text)):
        ref.year = int(match.group(1))
    ref.url = _param(template, "url")
    for i in range(1, 60):
        last = _param(template, f"last{i}", *(("last", "author") if i == 1 else ()))
        if not last:
            break
        ref.authors.append(last)
    return ref


class RefRegistry:
    """Named references, so ``<ref name=X />`` reuses resolve to their content."""

    def __init__(self, code: Wikicode) -> None:
        self._by_name: dict[str, str] = {}
        for tag in code.filter_tags(matches=lambda n: n.tag.lower() == "ref"):
            name = _attr(tag, "name")
            if name and tag.contents and str(tag.contents).strip():
                self._by_name.setdefault(name, str(tag.contents))

    def references(self, code: Wikicode, warnings: list[str]) -> list[Reference]:
        refs: list[Reference] = []
        for tag in code.filter_tags(matches=lambda n: n.tag.lower() == "ref"):
            name = _attr(tag, "name")
            contents = str(tag.contents) if tag.contents else ""
            if not contents.strip():
                if name and name in self._by_name:
                    contents = self._by_name[name]
                else:
                    warnings.append(f"unresolved named ref: {name!r}")
                    continue
            refs.extend(_refs_from_contents(contents, name, warnings))
        return refs


def _refs_from_contents(contents: str, name: str | None, warnings: list[str]) -> list[Reference]:
    code = mw.parse(contents)
    cites = [
        t for t in code.filter_templates(recursive=False) if _template_name(t).startswith("cite")
    ]
    if not cites:
        warnings.append("reference without a cite template")
        return [Reference(title=_plain(code) or None, ref_name=name)]
    out = []
    for cite in cites:
        ref = _parse_cite(cite)
        ref.ref_name = name
        out.append(ref)
    return out


# --------------------------------------------------------------------------- sections


def iter_sections(code: Wikicode) -> Iterator[tuple[list[str], Wikicode]]:
    """Each section's own content (subsections excluded) with its heading path."""
    stack: list[tuple[int, str]] = []
    for section in code.get_sections(flat=True, include_lead=False):
        headings = section.filter_headings(recursive=False)
        if not headings:
            continue
        heading = headings[0]
        title = _plain(heading.title)
        while stack and stack[-1][0] >= heading.level:
            stack.pop()
        stack.append((heading.level, title))
        body = mw.parse(str(section)[len(str(heading)) :])
        yield [t for _, t in stack], body


# --------------------------------------------------------------------------- new taxa


def _header_fields(cells: list[Tag], warnings: list[str]) -> list[str | None]:
    fields = []
    for cell in cells:
        label = _plain(cell.contents).lower()
        mapped = COLUMN_MAP.get(label)
        if mapped is None:
            warnings.append(f"unknown column {label!r}")
        fields.append(mapped)
    return fields


def _row_cells(row: Tag) -> list[Tag]:
    return [c for c in row.contents.filter_tags(recursive=False) if c.tag in ("td", "th")]


def _fill_name(row: NewTaxonRow, cell: Wikicode) -> None:
    links = [
        link
        for link in cell.filter_wikilinks()
        if not str(link.title).strip().lower().startswith(("file:", "image:"))
    ]
    row.name = _plain(cell) or None
    if links:
        row.name_link = _clean(str(links[0].title).split("#")[0])
    if not row.name:
        row.parse_warnings.append("empty name")


_FLAG = re.compile(r"\{\{\s*flag[a-z]*\s*\|\s*([^{}|]+?)\s*(?:\|[^{}]*)?\}\}", re.I)
_REFS = re.compile(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", re.I | re.S)


def _fill_countries(row: NewTaxonRow, cell: Wikicode) -> None:
    """Countries from ``{{Flag|X}}``; flags inside parentheses are subdivisions.

    ``{{flag|United States}}<br/>({{flag|Montana}}<br/>{{flag|Wyoming}})`` ->
    country "United States", regions "Montana" and "Wyoming".
    """
    text = _REFS.sub("", str(cell))
    for match in _FLAG.finditer(text):
        before = text[: match.start()]
        inside_parentheses = before.count("(") > before.count(")")
        target = row.regions if inside_parentheses else row.countries
        target.append(_clean(match.group(1)))
    if not row.countries and not row.regions:
        plain = _plain(cell)
        row.countries = [c.strip() for c in re.split(r",|/| and ", plain) if c.strip()]
    elif not row.countries:
        row.parse_warnings.append("region without country")


def _parse_table(
    table: Tag, page: str, revid: int, path: list[str], table_index: int, refs: RefRegistry
) -> list[NewTaxonRow]:
    rows: list[NewTaxonRow] = []
    fields: list[str | None] | None = None
    header_warnings: list[str] = []
    data_index = 0
    children = table.contents.filter_tags(recursive=False)
    # Header cells written before the first "|-" are direct children of the table.
    leading_th = []
    for node in children:
        if node.tag != "th":
            break
        leading_th.append(node)
    if leading_th:
        fields = _header_fields(leading_th, header_warnings)
    for tr in children:
        if tr.tag != "tr":
            continue
        cells = _row_cells(tr)
        if not cells:
            continue
        if fields is None and all(c.tag == "th" for c in cells):
            fields = _header_fields(cells, header_warnings)
            continue
        if fields is None:
            header_warnings.append("table without header row; assuming standard columns")
            fields = list(DEFAULT_COLUMNS)
        data_index += 1
        row = NewTaxonRow(page, revid, path, data_index, table_index)
        row.parse_warnings.extend(header_warnings)
        if len(cells) != len(fields):
            row.parse_warnings.append(f"{len(cells)} cells for {len(fields)} columns")
        for name, cell in zip(fields, cells, strict=False):
            content = cell.contents
            match name:
                case "name":
                    _fill_name(row, content)
                    row.references = refs.references(content, row.parse_warnings)
                case "age":
                    row.age = _plain(content) or None
                    row.age_links = _link_targets(content)
                case "type_locality":
                    row.type_locality = _plain(content) or None
                    row.type_locality_links = _link_targets(content)
                case "country":
                    _fill_countries(row, content)
                case "notes":
                    row.notes = _plain(content) or None
                    row.note_links = _link_targets(content)
                case "images":
                    row.images = [
                        _clean(str(link.title)).split(":", 1)[1]
                        for link in content.filter_wikilinks()
                        if str(link.title).strip().lower().startswith(("file:", "image:"))
                    ]
                case "novelty" | "status" | "authors":
                    setattr(row, name, _plain(content) or None)
        if not row.references:
            row.parse_warnings.append("no reference")
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- research


def _bullets(body: Wikicode) -> Iterator[str]:
    """Top-level bullets of a section (tables excluded), joined across lines."""
    text = str(body)
    for table in body.filter_tags(recursive=False, matches=lambda n: n.tag == "table"):
        text = text.replace(str(table), "\n")
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("*"):
            if current:
                yield "\n".join(current)
            current = [line.lstrip("*").strip()]
        elif current and line.strip() and not line.startswith(("=", "{|", "|", "!")):
            current.append(line)  # continuation (e.g. a multi-line <ref>)
        elif current:
            yield "\n".join(current)
            current = []
    if current:
        yield "\n".join(current)


def _italic_names(bullet: str, linked: set[str]) -> list[str]:
    """Italic, unlinked text that looks like a genus or species name."""
    without_refs = _REFS.sub("", bullet)
    names = []
    for match in _ITALIC_TEXT.finditer(without_refs):
        name = _clean(match.group(1))
        if name not in linked and _SCIENTIFIC_NAME.match(name):
            names.append(name)
    return list(dict.fromkeys(names))


def _research_id(page: str, refs: list[Reference], text: str) -> str:
    doi = next((r.doi for r in refs if r.doi), None)
    key = f"doi:{doi}" if doi else f"text:{page}:{_clean(text)[:300]}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _parse_research(
    body: Wikicode, page: str, revid: int, path: list[str], refs: RefRegistry
) -> list[ResearchItem]:
    items = []
    for bullet in _bullets(body):
        code = mw.parse(bullet)
        warnings: list[str] = []
        references = refs.references(code, warnings)
        if not references:
            warnings.append("no reference")
        elif not any(r.doi for r in references):
            warnings.append("no DOI")
        text = _plain(code)
        italic = list(dict.fromkeys(_clean(m.group(1)) for m in _ITALIC_LINK.finditer(bullet)))
        unlinked = _italic_names(bullet, set(italic))
        items.append(
            ResearchItem(
                page_title=page,
                revid=revid,
                research_id=_research_id(page, references, text),
                section_path=path,
                text=text,
                links=_link_targets(code),
                italic_links=italic,
                italic_names=unlinked,
                references=references,
                parse_warnings=warnings,
            )
        )
    return items


def _merge_duplicate_research(items: list[ResearchItem]) -> list[ResearchItem]:
    """One study may be listed under several headings: keep one item per id."""
    merged: dict[str, ResearchItem] = {}
    for item in items:
        if item.research_id not in merged:
            merged[item.research_id] = item
            continue
        kept = merged[item.research_id]
        kept.links = list(dict.fromkeys([*kept.links, *item.links]))
        kept.italic_links = list(dict.fromkeys([*kept.italic_links, *item.italic_links]))
        kept.italic_names = list(dict.fromkeys([*kept.italic_names, *item.italic_names]))
        kept.parse_warnings.append(f"also listed under: {' > '.join(item.section_path)}")
    return list(merged.values())


# --------------------------------------------------------------------------- entry point


def parse_page(
    page_title: str, revid: int, wikitext: str, revision_timestamp: str | None = None
) -> ParsedPage:
    code = mw.parse(wikitext)
    refs = RefRegistry(code)
    new_taxa: list[NewTaxonRow] = []
    research: list[ResearchItem] = []
    table_index = 0
    for path, body in iter_sections(code):
        heading = path[-1].lower()
        if heading in {"references", "see also", "external links", "notes"}:
            continue
        tables = body.filter_tags(recursive=False, matches=lambda n: n.tag == "table")
        for table in tables:
            table_index += 1
            new_taxa.extend(_parse_table(table, page_title, revid, path, table_index, refs))
        if "research" in heading:
            research.extend(_parse_research(body, page_title, revid, path, refs))
    research = _merge_duplicate_research(research)
    for row in [*new_taxa, *research]:
        row.revision_timestamp = revision_timestamp
    return ParsedPage(page_title, revid, new_taxa, research, revision_timestamp)


def to_records(rows: list[NewTaxonRow] | list[ResearchItem]) -> list[dict[str, Any]]:
    return [asdict(r) for r in rows]


def write_interim(parsed: ParsedPage, interim_root: Path) -> Path:
    """Write ``new_taxa.jsonl``, ``research.jsonl`` and a small parse report.

    Output goes to ``<interim>/wikipedia/<slug>/<revid>/``; re-running for the
    same revision overwrites it with identical content (idempotent).
    """
    out = interim_dir(parsed.page_title, parsed.revid, interim_root)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("new_taxa", parsed.new_taxa), ("research", parsed.research)):
        lines = (json.dumps(r, ensure_ascii=False, sort_keys=True) for r in to_records(rows))
        (out / f"{name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {
        "page_title": parsed.page_title,
        "revid": parsed.revid,
        "revision_timestamp": parsed.revision_timestamp,
        "new_taxa": len(parsed.new_taxa),
        "research": len(parsed.research),
        "warnings": parsed.warning_count(),
    }
    (out / "parse_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return out


def interim_dir(page_title: str, revid: int, interim_root: Path) -> Path:
    return interim_root / "wikipedia" / slugify_title(page_title) / str(revid)


def plain_text(code: Wikicode | str) -> str:
    """Readable text of wikicode (refs, templates, files and markup removed)."""
    return _plain(code)
