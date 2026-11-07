"""Spanish versions of the study titles shown in each taxon's history.

Titles come from the Crossref metadata already stored in the raw store. Each
translation is checked deterministically (same numbers, scientific names kept)
and saved to ``derived/study_titles/es.json``; the site shows it next to the
original title, marked as a translation of an article in English.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paleo.ingest import crossref
from paleo.llm import LLM
from paleo.narrative.facts import prompt
from paleo.narrative.sources import study_title
from paleo.narrative.write import AdaptedText, _tidy
from paleo.store import _atomic_write

BATCH = 20
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class TitlesResult:
    total: int = 0
    up_to_date: int = 0
    translated: int = 0
    rejected: int = 0


def titles_path(derived_root: Path) -> Path:
    return derived_root / "study_titles" / "es.json"


def stored_titles(raw_root: Path | None) -> tuple[dict[str, str], set[str]]:
    """(DOI -> plain title of every work Crossref knows that is not in Spanish, DOIs of
    the works Crossref says are in Spanish): those never need a translation."""
    works = crossref.store(raw_root)
    out, spanish = {}, set()
    for doi in works.stored_keys():
        latest = works.latest(doi)
        if latest and latest["payload"].get("found"):
            work = latest["payload"]["work"]
            if str(work.get("language") or "").lower() == "es":
                spanish.add(doi)
                continue
            title = study_title(work)
            if title:
                out[doi] = title
    return out, spanish


def check_title(source: str, translated: str, scientific_names: set[str]) -> list[str]:
    """Problems with a translation; empty if it can be published."""
    problems = []
    if not translated:
        return ["empty translation"]

    def numbers(text: str) -> list[str]:
        return sorted(n.replace(",", ".") for n in _NUMBER.findall(text))

    if numbers(source) != numbers(translated):
        problems.append("numbers changed")
    for word in re.findall(r"[A-Z][a-z]+", source):
        if word in scientific_names and word not in translated:
            problems.append(f"name lost: {word}")
    if not 0.5 <= len(translated) / len(source) <= 2:
        problems.append("length out of range")
    return problems


def _load(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["doi"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


def _save(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [rows[doi] for doi in sorted(rows)]
    _atomic_write(path, json.dumps(ordered, ensure_ascii=False, indent=1) + "\n")


def translate_titles(
    llm: LLM,
    *,
    raw_root: Path | None,
    derived_root: Path,
    scientific_names: set[str],
    limit: int | None = None,
) -> TitlesResult:
    """Translate titles that are new, changed or written with an older prompt."""
    system, version = prompt("translate_titles")
    path = titles_path(derived_root)
    rows = _load(path)
    if not path.exists():
        _save(path, rows)  # dbt reads the file even when nothing gets translated
    titles, spanish = stored_titles(raw_root)
    for doi in spanish & rows.keys():  # translated before the language was read
        del rows[doi]
    result = TitlesResult(total=len(titles))
    pending = []
    for doi, title in sorted(titles.items()):
        row = rows.get(doi)
        if row and row["title"] == title and row["prompt_version"] == version:
            result.up_to_date += 1
        else:
            pending.append((doi, title))
    pending = pending[:limit] if limit else pending
    for start in range(0, len(pending), BATCH):
        batch = pending[start : start + BATCH]
        user = "TÍTULOS:\n" + "\n".join(f"{i}. {t}" for i, (_, t) in enumerate(batch, start=1))
        answer = llm.complete_json(system, user, AdaptedText, max_tokens=4_000)
        by_index = {s.index: _tidy(s.text) for s in answer.sentences}
        for i, (doi, title) in enumerate(batch, start=1):
            translated = by_index.get(i, "")
            if check_title(title, translated, scientific_names):
                result.rejected += 1
                continue
            rows[doi] = {
                "doi": doi,
                "title": title,
                "title_es": translated,
                "generator": llm.label,
                "prompt_version": version,
                "translated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            }
            result.translated += 1
        _save(path, rows)  # keep progress if the quota runs out mid-way
    return result
