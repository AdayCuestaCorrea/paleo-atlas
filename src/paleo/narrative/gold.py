"""Reference ("gold") pages used to evaluate the narrative pipeline (decision A18).

Gold pages live in ``eval/gold/<taxon_key>.json`` and follow the pipeline's own
format: facts with a verbatim quote from a public chunk, and EN/ES texts whose
sentences cite those facts. They must pass exactly the same deterministic checks
as generated pages, so the reference never relies on anything the sources do
not say.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paleo.narrative.checks import check_alignment, check_fact, check_text
from paleo.narrative.sources import Chunk

GOLD_DIR = Path("eval") / "gold"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sentences(doc: dict[str, Any], lang: str) -> list[tuple[str, list[str]]]:
    return [
        (s["text"], s["fact_ids"]) for section in doc["texts"][lang] for s in section["sentences"]
    ]


def validate(doc: dict[str, Any], chunks: list[Chunk], scientific_names: set[str]) -> list[str]:
    """Problems of a gold page (empty list = valid)."""
    problems: list[str] = []
    by_id = {c.chunk_id: c for c in chunks}
    for fact in doc["facts"]:
        chunk = by_id.get(fact["chunk_id"])
        if chunk is None:
            problems.append(f"{fact['fact_id']}: unknown chunk {fact['chunk_id']}")
            continue
        if not chunk.public_quote:
            problems.append(f"{fact['fact_id']}: gold facts must use public chunks only")
        if reason := check_fact(fact["statement"], fact["quote"], chunk.text, chunk.title):
            problems.append(f"{fact['fact_id']}: {reason}")
    fact_texts = {f["fact_id"]: f"{f['statement']} {f['quote']}" for f in doc["facts"]}
    sources = {
        lang: [c.text for c in chunks if c.lang == lang and c.public_quote] for lang in ("en", "es")
    }
    en = sentences(doc, "en")
    report = check_text(en, fact_texts, sources["en"])
    problems += [f"en: {p}" for p in report.summary()]
    es = sentences(doc, "es")
    problems += [f"es: {p}" for p in check_alignment(en, [t for t, _ in es], scientific_names)]
    if [f for _, f in es] != [f for _, f in en]:
        problems.append("es: fact_ids must match the English sentences one to one")
    es_report = check_text(es, fact_texts, sources["es"], check_names=False)
    problems += [f"es: {p}" for p in es_report.summary()]
    return problems
