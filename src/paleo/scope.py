"""Taxonomic scope of the rows of the yearly Wikipedia pages (ALCANCE.md §4).

The single place that decides which new taxa and studies of the yearly pages are in
scope, and in which group. `paleo parse wikipedia` stores the result in every
interim row (``taxon_group``; None = out of scope), dbt reads it, and every Python
step (PBDB, Crossref, articles, images, facts and texts) only sees rows in scope:
no quota is spent on turtles or lizards.

* Archosaur page: every section, grouped by its first heading.
* Reptile page: ichthyosaurs, sauropterygians and, among the squamates, the
  mosasaurs (the row or study mentions them).
* Fish page: placoderms, cartilaginous fishes and the genera of the featured_fishes
  seed (a new taxon by its genus, a study by naming one of them).
"""

from __future__ import annotations

import csv
import re
from functools import cache

from paleo.config import WIKIPEDIA_PAGES, project_root

_ARCHOSAUR_SECTIONS = {
    "pseudosuchians": "pseudosuchians",
    "non-avian dinosaurs": "non_avian_dinosaurs",
    "birds": "birds",
    "pterosaurs": "pterosaurs",
    "other archosaurs": "other_archosaurs",
    "general research": "general",
}
# Headings (any level) of the reptile and fish pages -> candidate group.
_SECTIONS = {
    "ichthyosauromorphs": "ichthyosaurs",
    "ichthyosauromorph research": "ichthyosaurs",
    "sauropterygians": "sauropterygians",
    "sauropterygian research": "sauropterygians",
    "squamates": "squamates",
    "squamate research": "squamates",
    "placoderms": "placoderms",
    "placoderm research": "placoderms",
    "cartilaginous fishes": "cartilaginous_fishes",
    "cartilaginous fish research": "cartilaginous_fishes",
    "ray-finned fishes": "bony_fishes",
    "ray-finned fish research": "bony_fishes",
    "lobe-finned fishes": "bony_fishes",
    "lobe-finned fish research": "bony_fishes",
    "jawless vertebrates": "bony_fishes",
    "jawless vertebrate research": "bony_fishes",
    "other fishes": "bony_fishes",
    "other fish research": "bony_fishes",
}
_ALWAYS = {"ichthyosaurs", "sauropterygians", "placoderms", "cartilaginous_fishes"}
_MOSASAUR = re.compile(r"mosasaur", re.IGNORECASE)


def block_of(page_title: str) -> str | None:
    """Block of §4 a yearly page belongs to ("2026 in paleoichthyology" -> fossil_fishes)."""
    for page in WIKIPEDIA_PAGES:
        if page.title_template.replace("{year}", "").strip() in page_title:
            return page.block
    return None


@cache
def featured_fishes() -> frozenset[str]:
    path = project_root() / "dbt" / "seeds" / "featured_fishes.csv"
    if not path.exists():
        return frozenset()
    with path.open(encoding="utf-8", newline="") as f:
        return frozenset(r["genus"].strip() for r in csv.DictReader(f) if r["genus"].strip())


def section_group(block: str | None, section_path: list[str]) -> str:
    """Candidate group of a row from the headings it is under."""
    if block == "archosaurs":
        return _ARCHOSAUR_SECTIONS.get((section_path or [""])[0].lower(), "other")
    for heading in section_path:
        if heading.lower() in _SECTIONS:
            return _SECTIONS[heading.lower()]
    return "other"


def new_taxon_group(
    page_title: str, section_path: list[str], name: str | None, text: str
) -> str | None:
    """Group of a new taxon of a yearly page, or None when it is outside §4."""
    block = block_of(page_title)
    group = section_group(block, section_path)
    if block == "archosaurs":
        return group
    genus = (name or "").split(" ")[0]
    return _scoped(group, text, genus in featured_fishes())


def research_group(page_title: str, section_path: list[str], text: str) -> str | None:
    """Group of a study of a yearly page, or None when it is outside §4."""
    block = block_of(page_title)
    group = section_group(block, section_path)
    if block == "archosaurs":
        return group
    words = set(re.findall(r"[A-Z][a-z]+", text))
    return _scoped(group, text, bool(words & featured_fishes()))


def _scoped(group: str, text: str, featured: bool) -> str | None:
    if group in _ALWAYS:
        return group
    if group == "squamates" and _MOSASAUR.search(text):
        return "mosasaurs"
    if group == "bony_fishes" and featured:
        return "other_fishes"
    return None
