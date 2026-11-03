"""Step 1 of a narrative page: extract checkable facts from the source chunks.

Every fact comes with a verbatim quote from its chunk; the quote is checked
deterministically (``checks.check_fact``) and unsupported facts are dropped and
counted. Quotes from copyrighted abstracts are kept only in the local cache.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from paleo.llm import LLM, LLMOutputError
from paleo.narrative.checks import check_fact, normalize
from paleo.narrative.sources import Chunk, taxon_key
from paleo.store import _atomic_write

Category = Literal[
    "description", "discovery", "paleobiology", "classification", "time_and_habitat", "debate"
]
BATCH_CHARS = 9_000  # chunks per call, kept well under Groq's 8K tokens/minute with the prompt


CATEGORIES = set(Category.__args__)


class ExtractedFact(BaseModel):
    chunk_id: str = Field(description="id of the chunk the fact comes from")
    statement: str = Field(description="one self-contained fact, in English")
    category: Category
    quote: str = Field(description="exact span copied from that chunk")

    @field_validator("category", mode="before")
    @classmethod
    def _known_category(cls, value: object) -> str:
        """A made-up category must not sink the whole answer: map it to description."""
        text = str(value).strip().lower().replace(" ", "_")
        return text if text in CATEGORIES else "description"


class Extraction(BaseModel):
    facts: list[ExtractedFact]


def prompt(name: str) -> tuple[str, str]:
    """(text, version) of a prompt file in ``narrative/prompts``."""
    text = resources.files("paleo.narrative.prompts").joinpath(f"{name}.md").read_text("utf-8")
    first = text.splitlines()[0]
    version = first.removeprefix("<!-- version:").removesuffix("-->").strip()
    return text.split("\n", 1)[1].strip(), version


@dataclass
class FactsResult:
    taxon: str
    accepted: int
    rejected: int
    path: Path


def _batches(chunks: list[Chunk]) -> list[list[Chunk]]:
    batches: list[list[Chunk]] = []
    size = 0
    for chunk in chunks:
        if batches and size + len(chunk.text) <= BATCH_CHARS:
            batches[-1].append(chunk)
            size += len(chunk.text)
        else:
            batches.append([chunk])
            size = len(chunk.text)
    return batches


def _user_message(taxon: str, batch: list[Chunk]) -> str:
    parts = [f"ANIMAL: {taxon}\n"]
    for chunk in batch:
        parts.append(f"=== CHUNK {chunk.chunk_id} — {chunk.title} ===\n{chunk.text}\n")
    return "\n".join(parts)


def sources_hash(chunks: list[Chunk]) -> str:
    """Hash of the public sources only. Abstracts live in a local cache that a fresh
    CI runner does not have, so they must not make a species look changed."""
    joined = "\n".join(f"{c.chunk_id}\n{c.text}" for c in chunks if c.public_quote)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def extract_facts(
    llm: LLM, taxon: str, chunks: list[Chunk], *, derived_root: Path, cache_root: Path
) -> FactsResult:
    system, version = prompt("extract_facts")
    by_id = {c.chunk_id: c for c in chunks}
    accepted: list[dict] = []
    rejected: list[dict] = []
    private_quotes: dict[str, str] = {}
    seen: set[str] = set()

    def answer(batch: list[Chunk]) -> list[tuple[ExtractedFact, list[Chunk]]]:
        """Facts of one batch; an answer cut short (too many facts for the token cap,
        even after the retry with more tokens) is asked again in two halves."""
        try:
            result = llm.complete_json(
                system, _user_message(taxon, batch), Extraction, max_tokens=3_000
            )
        except LLMOutputError:
            if len(batch) == 1:
                raise
            half = len(batch) // 2
            return answer(batch[:half]) + answer(batch[half:])
        return [(fact, batch) for fact in result.facts]

    for fact, batch in (pair for b in _batches(chunks) for pair in answer(b)):
        chunk = by_id.get(fact.chunk_id)
        reason = (
            "unknown chunk id"
            if chunk is None or chunk not in batch
            else check_fact(fact.statement, fact.quote, chunk.text)
        )
        key = normalize(fact.statement)
        if reason is None and key in seen:
            reason = "duplicate"
        if reason:
            rejected.append({**fact.model_dump(), "reason": reason})
            continue
        seen.add(key)
        fact_id = f"F{len(accepted) + 1:03d}"
        record = {
            "fact_id": fact_id,
            "statement": fact.statement,
            "category": fact.category,
            "chunk_id": fact.chunk_id,
            "lang": chunk.lang,
            "quote": fact.quote if chunk.public_quote else None,
            "quote_sha": hashlib.sha256(fact.quote.encode("utf-8")).hexdigest()[:16],
        }
        if not chunk.public_quote:
            private_quotes[fact_id] = fact.quote
        accepted.append(record)

    key = taxon_key(taxon)
    out = {
        "taxon": taxon,
        "taxon_key": key,
        "generator": llm.label,
        "prompt_version": version,
        "sources_hash": sources_hash(chunks),
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "citations": {c.chunk_id: c.citation() for c in chunks},
        "facts": accepted,
        "rejected": rejected,
    }
    path = derived_root / "facts" / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    if private_quotes:
        private = cache_root / "facts_private" / f"{key}.json"
        private.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(private, json.dumps(private_quotes, ensure_ascii=False, indent=1) + "\n")
    return FactsResult(taxon, len(accepted), len(rejected), path)
