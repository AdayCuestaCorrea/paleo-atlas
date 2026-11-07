"""One-sentence definitions of the glossary terms, written from their source and
checked like the narrative pages (§12.2, Phase 5).

Each definition is written from the lead of the term's Wikipedia article in the same
language (the English lead when there is no Spanish one) and published only if it
passes every check:

* copy: no run of 8 words shared with the source (the narrative pages' rule);
* length: 10 to 35 words;
* circularity: it does not use the term or its forms;
* numbers: every number is in the source;
* judge: a second model, of another family, says everything it states is in the
  source.

Results go to ``derived/glossary/<term_id>.<lang>.json``, failed ones included (with
their problems, never published). A definition is written again only when its source
revision or a prompt changes.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from paleo.glossary.terms import form_pattern
from paleo.ingest.glossary import lead_store
from paleo.llm import LLM
from paleo.narrative.checks import copied_runs, ngrams, numbers, words
from paleo.narrative.facts import prompt
from paleo.store import _atomic_write

BATCH = 10
LEAD_CHARS = 1_500  # the first paragraphs say what a term is; enough context, little quota
MIN_WORDS, MAX_WORDS = 10, 35


class Definition(BaseModel):
    index: int
    definition: str


class Definitions(BaseModel):
    definitions: list[Definition]


class Verdict(BaseModel):
    index: int
    supported: bool
    unsupported: str = ""


class Verdicts(BaseModel):
    items: list[Verdict]


@dataclass
class WriteResult:
    terms: int = 0
    up_to_date: int = 0
    verified: dict[str, int] = field(default_factory=lambda: {"en": 0, "es": 0})
    rejected: dict[str, int] = field(default_factory=lambda: {"en": 0, "es": 0})
    no_source: int = 0


def definition_path(derived_root: Path, term_id: str, lang: str) -> Path:
    return derived_root / "glossary" / f"{term_id}.{lang}.json"


def deterministic_problems(definition: str, source: str, forms: list[str]) -> list[str]:
    """What the checks without a model find wrong (empty: it may be published)."""
    problems = []
    n = len(words(definition))
    if not MIN_WORDS <= n <= MAX_WORDS:
        problems.append(f"length: {n} words")
    for run in copied_runs(definition, ngrams(words(source))):
        problems.append(f"copied: {run}")
    if form_pattern(forms).search(definition):
        problems.append("circular: uses the term")
    extra = numbers(definition) - numbers(source)
    if extra:
        problems.append(f"numbers not in the source: {', '.join(sorted(extra))}")
    return problems


def _source(term: dict[str, Any], lang: str, cache_root: Path | None) -> dict[str, Any] | None:
    """The lead a definition in ``lang`` is written from: same language, else English."""
    for source_lang in (lang, "en"):
        latest = lead_store(source_lang, cache_root).latest(term["term_id"])
        if latest:
            return {"lang": source_lang, **latest["payload"]}
    return None


def write_definitions(
    writer: LLM,
    judge: LLM,
    terms: list[dict[str, Any]],
    *,
    derived_root: Path,
    cache_root: Path | None = None,
    now: dt.datetime | None = None,
) -> WriteResult:
    system, version = prompt("glossary_define")
    judge_system, judge_version = prompt("glossary_judge")
    result = WriteResult(terms=len(terms))
    stamp = (now or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds")
    for lang in ("en", "es"):
        todo = []
        for term in terms:
            source = _source(term, lang, cache_root)
            if source is None:
                result.no_source += lang == "en"
                continue
            path = definition_path(derived_root, term["term_id"], lang)
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                if (old["source"]["revid"] == source["revid"] and old["prompt_version"] == version
                        and old["judge_version"] == judge_version):  # fmt: skip
                    result.up_to_date += 1
                    continue
            todo.append((term, source))
        for start in range(0, len(todo), BATCH):
            batch = todo[start : start + BATCH]
            user = "\n\n".join(
                f"{i}. TERM: {t[f'term_{lang}']} · LANGUAGE: {lang}\n"
                f"SOURCE: {s['lead'][:LEAD_CHARS]}"
                for i, (t, s) in enumerate(batch, start=1)
            )
            written = {d.index: d.definition.strip()
                       for d in writer.complete_json(system, user, Definitions,
                                                     max_tokens=2_500).definitions}  # fmt: skip
            to_judge = [(i, t, s, written[i]) for i, (t, s) in enumerate(batch, start=1)
                        if written.get(i)]  # fmt: skip
            verdicts: dict[int, Verdict] = {}
            if to_judge:
                judge_user = "\n\n".join(
                    f"{n}. TERM: {t[f'term_{lang}']}\nSOURCE: {s['lead'][:LEAD_CHARS]}\n"
                    f"DEFINITION: {d}"
                    for n, (_, t, s, d) in enumerate(to_judge, start=1)
                )
                answer = judge.complete_json(judge_system, judge_user, Verdicts, max_tokens=2_000)
                by_n = {v.index: v for v in answer.items}
                verdicts = {i: by_n[n] for n, (i, *_) in enumerate(to_judge, start=1) if n in by_n}
            for i, (term, source) in enumerate(batch, start=1):
                definition = written.get(i, "")
                problems = deterministic_problems(definition, source["lead"],
                                                  term[f"all_{lang}"]) if definition else [
                    "not written"]  # fmt: skip
                verdict = verdicts.get(i)
                if definition and verdict is None:
                    problems.append("judge: no answer")
                elif verdict is not None and not verdict.supported:
                    problems.append(f"judge: {verdict.unsupported or 'not supported'}")
                status = "verified" if not problems else "rejected"
                getattr(result, status)[lang] += 1
                path = definition_path(derived_root, term["term_id"], lang)
                path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(path, json.dumps({
                    "term_id": term["term_id"], "lang": lang, "term": term[f"term_{lang}"],
                    "definition": definition, "status": status, "problems": problems,
                    "source": {k: source[k] for k in ("lang", "title", "revid")},
                    "generator": writer.label, "judge": judge.label,
                    "prompt_version": version, "judge_version": judge_version,
                    "generated_at": stamp,
                }, ensure_ascii=False, indent=1) + "\n")  # fmt: skip
    return result
