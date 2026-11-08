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
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from paleo.glossary.terms import form_pattern
from paleo.ingest.glossary import index_store, lead_store
from paleo.llm import LLM, LLMOutputError
from paleo.narrative.checks import copied_runs, ngrams, numbers, spelled_numbers, words
from paleo.narrative.facts import prompt
from paleo.store import _atomic_write

log = logging.getLogger(__name__)

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
    known = numbers(source).union(*spelled_numbers(source))
    extra = numbers(definition) - known
    # Written in words: "fifty-eight million" may be "58 million" or "58,000,000", or a
    # rounded "58.3 million" (nobody spells out decimals).
    rounded = known | {str(f(float(n))) for n in known if "." in n for f in (int, round)}
    extra |= {max(forms, key=len) for forms in spelled_numbers(definition) if not forms & rounded}
    if extra:
        problems.append(f"numbers not in the source: {', '.join(sorted(extra))}")
    return problems


def _source(
    term: dict[str, Any], lang: str, cache_root: Path | None, raw_root: Path | None = None
) -> dict[str, Any] | None:
    """The lead a definition in ``lang`` is written from: same language, else English;
    only a lead the index accepts at that same revision (a source dropped later, or
    replaced by another article, is never used from the cache)."""
    index = index_store(raw_root).latest(term["term_id"])
    if index is None:
        return None
    for source_lang in (lang, "en"):
        entry = index["payload"].get(source_lang) or {}
        latest = lead_store(source_lang, cache_root).latest(term["term_id"])
        if entry.get("accepted") and latest and latest["payload"]["revid"] == entry["revid"]:
            return {"lang": source_lang, **latest["payload"]}
    return None


def _attempt(
    writer: LLM,
    judge: LLM,
    system: str,
    judge_system: str,
    lang: str,
    batch: list[tuple[dict[str, Any], dict[str, Any]]],
    feedback: dict[int, tuple[str, list[str], int]],
) -> dict[int, tuple[str, list[str], int]]:
    """Write and check a batch: index -> (definition, problems, attempt number). With
    ``feedback`` (index -> the previous try), the model sees what was wrong."""
    parts = []
    for i, (t, s) in enumerate(batch, start=1):
        part = (
            f"{i}. TERM: {t[f'term_{lang}']} · LANGUAGE: {lang}\nSOURCE: {s['lead'][:LEAD_CHARS]}"
        )
        if i in feedback:
            previous, problems, _ = feedback[i]
            part += (f"\nYOUR PREVIOUS TRY WAS REJECTED: {previous}\nPROBLEMS: "
                     f"{'; '.join(problems)}\nWrite it again in really different words, "
                     "without those problems.")  # fmt: skip
        parts.append(part)
    try:
        answer = writer.complete_json(system, "\n\n".join(parts), Definitions, max_tokens=2_500)
        written = {d.index: d.definition.strip() for d in answer.definitions}
    except LLMOutputError as exc:  # the batch stays unwritten ("not written")
        log.warning("glossary writer: %s", exc)
        written = {}
    to_judge = [(i, t, s, written[i]) for i, (t, s) in enumerate(batch, start=1)
                if written.get(i)]  # fmt: skip
    verdicts: dict[int, Verdict] = {}
    if to_judge:
        judge_user = "\n\n".join(
            f"{n}. TERM: {t[f'term_{lang}']}\nSOURCE: {s['lead'][:LEAD_CHARS]}\nDEFINITION: {d}"
            for n, (_, t, s, d) in enumerate(to_judge, start=1)
        )
        try:
            reply = judge.complete_json(judge_system, judge_user, Verdicts, max_tokens=900)
        except LLMOutputError as exc:  # the batch stays unjudged ("judge: no answer")
            log.warning("glossary judge: %s", exc)
        else:
            by_n = {v.index: v for v in reply.items}
            verdicts = {i: by_n[n] for n, (i, *_) in enumerate(to_judge, start=1) if n in by_n}
    out = {}
    for i, (term, source) in enumerate(batch, start=1):
        definition = written.get(i, "")
        if not definition:
            out[i] = ("", ["not written"], 2 if feedback else 1)
            continue
        problems = deterministic_problems(definition, source["lead"], term[f"all_{lang}"])
        verdict = verdicts.get(i)
        if verdict is None:
            problems.append("judge: no answer")
        elif not verdict.supported:
            problems.append(f"judge: {verdict.unsupported or 'not supported'}")
        out[i] = (definition, problems, 2 if feedback else 1)
    return out


def write_definitions(
    writer: LLM,
    judge: LLM,
    terms: list[dict[str, Any]],
    *,
    derived_root: Path,
    cache_root: Path | None = None,
    raw_root: Path | None = None,
    now: dt.datetime | None = None,
) -> WriteResult:
    system, version = prompt("glossary_define")
    judge_system, judge_version = prompt("glossary_judge")
    result = WriteResult(terms=len(terms))
    stamp = (now or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds")
    for lang in ("en", "es"):
        todo = []
        for term in terms:
            source = _source(term, lang, cache_root, raw_root)
            if source is None:
                result.no_source += lang == "en"
                continue
            path = definition_path(derived_root, term["term_id"], lang)
            if path.exists():
                old = json.loads(path.read_text(encoding="utf-8"))
                done = old["status"] == "verified" or old.get("attempts", 1) >= 2
                if (done and old["source"]["revid"] == source["revid"]
                        and old["prompt_version"] == version
                        and old["judge_version"] == judge_version):  # fmt: skip
                    result.up_to_date += 1
                    continue
            todo.append((term, source))
        for start in range(0, len(todo), BATCH):
            batch = todo[start : start + BATCH]
            outcome = _attempt(writer, judge, system, judge_system, lang, batch, {})
            # one more try for the rejected ones, told what was wrong (like the pages)
            again = {i: outcome[i] for i in outcome if outcome[i][1]}
            if again:
                retry = [batch[i - 1] for i in sorted(again)]
                feedback = {n: again[i] for n, i in enumerate(sorted(again), start=1)}
                second = _attempt(writer, judge, system, judge_system, lang, retry, feedback)
                for n, i in enumerate(sorted(again), start=1):
                    outcome[i] = (*second[n][:2], 2)
            for i, (term, source) in enumerate(batch, start=1):
                definition, problems, attempts = outcome[i]
                status = "verified" if not problems else "rejected"
                getattr(result, status)[lang] += 1
                path = definition_path(derived_root, term["term_id"], lang)
                path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write(path, json.dumps({
                    "term_id": term["term_id"], "lang": lang, "term": term[f"term_{lang}"],
                    "definition": definition, "status": status, "problems": problems,
                    "attempts": attempts,
                    "source": {k: source[k] for k in ("lang", "title", "revid")},
                    "generator": writer.label, "judge": judge.label,
                    "prompt_version": version, "judge_version": judge_version,
                    "generated_at": stamp,
                }, ensure_ascii=False, indent=1) + "\n")  # fmt: skip
    return result
