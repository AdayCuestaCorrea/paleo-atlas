"""Step 2 of a narrative page: write English prose from verified facts, then adapt
it to Spanish sentence by sentence, and check both (ALCANCE.md §12.1).

A text that fails its checks gets one retry with the list of problems; if it
fails again it is saved for review and the site keeps the fallback text.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from paleo.llm import LLM
from paleo.narrative.checks import MAX_WORDS, TextReport, check_alignment, check_text
from paleo.narrative.facts import Category, prompt
from paleo.narrative.sources import Chunk
from paleo.store import _atomic_write

SECTION_ORDER = [
    "description",
    "discovery",
    "paleobiology",
    "classification",
    "time_and_habitat",
    "debate",
]


class WrittenSentence(BaseModel):
    text: str
    fact_ids: list[str] = Field(description="ids of the facts this sentence relies on")


class WrittenSection(BaseModel):
    section: Category
    sentences: list[WrittenSentence]


class WrittenText(BaseModel):
    sections: list[WrittenSection]


class AdaptedSentence(BaseModel):
    index: int = Field(description="index of the English sentence, starting at 1")
    text: str = Field(description="the Spanish version of that sentence")


class AdaptedText(BaseModel):
    sentences: list[AdaptedSentence]


@dataclass
class WriteResult:
    taxon_key: str
    status: dict[str, str] = field(default_factory=dict)  # lang -> verified | failed
    problems: dict[str, list[str]] = field(default_factory=dict)
    words: dict[str, int] = field(default_factory=dict)
    review: str | None = None  # Spanish grammar pass: accepted | rejected | unchanged


MAX_FACTS_FOR_WRITING = 24


def select_facts(facts: list[dict[str, Any]], limit: int = MAX_FACTS_FOR_WRITING) -> list[dict]:
    """At most ``limit`` facts, taken round-robin across sections in source order,
    so a long article yields a balanced page instead of an overlong one."""
    by_section: dict[str, list[dict[str, Any]]] = {name: [] for name in SECTION_ORDER}
    for fact in facts:
        by_section.setdefault(fact["category"], []).append(fact)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < min(limit, len(facts)):
        for name in by_section:
            if by_section[name] and len(chosen) < limit:
                chosen.append(by_section[name].pop(0))
    order = {f["fact_id"]: i for i, f in enumerate(facts)}
    return sorted(chosen, key=lambda f: order[f["fact_id"]])


def facts_hash(facts: list[dict[str, Any]]) -> str:
    """Hash of the facts a page is written from (the selected ones)."""
    selected = select_facts(facts)
    return hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()[:16]


def prompt_versions() -> dict[str, str]:
    """Version a text of each language is written with; a change rewrites it."""
    en = prompt("write_en")[1]
    return {"en": en, "es": f"{prompt('adapt_es')[1]}+{prompt('review_es')[1]}"}


def is_up_to_date(facts_path: Path, derived_root: Path) -> bool:
    """True when both texts (or a failed English one kept for review) were written
    from exactly these facts and prompts, so writing again would only spend quota."""
    doc = json.loads(facts_path.read_text(encoding="utf-8"))
    current = facts_hash(doc["facts"])
    versions = prompt_versions()
    key = doc["taxon_key"]

    def same(folder: str, lang: str) -> bool:
        path = derived_root / folder / f"{key}.{lang}.json"
        if not path.exists():
            return False
        stored = json.loads(path.read_text(encoding="utf-8"))
        return stored["facts_hash"] == current and stored["prompt_version"] == versions[lang]

    if same("texts_review", "en"):
        return True  # English failed with these facts: retry only with --force
    return same("texts", "en") and (same("texts", "es") or same("texts_review", "es"))


def target_words(fact_count: int) -> int:
    """~120 words for a sparse taxon, up to ~450 for a well documented one."""
    return max(120, min(450, 40 + 10 * fact_count))


_SPACES = str.maketrans({"\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u2011": "-"})


def _tidy(text: str) -> str:
    """Plain spaces and hyphens (models like narrow no-break spaces)."""
    return " ".join(text.translate(_SPACES).split())


def _flatten(text: WrittenText) -> list[tuple[str, list[str], str]]:
    """(sentence, fact_ids, section) in the canonical section order."""
    order = {name: i for i, name in enumerate(SECTION_ORDER)}
    out = []
    for section in sorted(text.sections, key=lambda s: order.get(s.section, 99)):
        out.extend((_tidy(s.text), s.fact_ids, section.section) for s in section.sentences)
    return out


def _fact_texts(facts: list[dict[str, Any]]) -> dict[str, str]:
    """What a sentence may rely on: the statement and, when public, the quote."""
    return {f["fact_id"]: f"{f['statement']} {f.get('quote') or ''}".strip() for f in facts}


def _write_en(
    llm: LLM, taxon: str, facts: list[dict[str, Any]], feedback: list[str] | None
) -> WrittenText:
    system, _ = prompt("write_en")
    target = target_words(len(facts))
    system = system.replace("{target_words}", str(target))
    system = system.replace("{max_words}", str(min(MAX_WORDS, int(target * 1.25))))
    lines = [f"ANIMAL: {taxon}", "", "VERIFIED FACTS:"]
    lines += [f"{f['fact_id']} [{f['category']}] {f['statement']}" for f in facts]
    if feedback:
        lines += [
            "",
            "Your previous answer failed these automatic checks. Fix every one:",
            *feedback,
            "",
            "How to fix them: a number must be written exactly as in a cited fact (copy it, do "
            "not round it) or the sentence must drop it; a name must appear in the facts; a "
            "copied run of words must be rephrased in your own words; a too-long text must "
            "leave out less important facts.",
        ]
    return llm.complete_json(system, "\n".join(lines), WrittenText, max_tokens=3_000)


def _adapt_es(
    llm: LLM, taxon: str, sentences: list[tuple[str, list[str], str]], feedback: list[str] | None
) -> list[str]:
    system, _ = prompt("adapt_es")
    lines = [f"ANIMAL: {taxon}", "", "ENGLISH SENTENCES:"]
    lines += [f"{i}. {text}" for i, (text, _, _) in enumerate(sentences, start=1)]
    if feedback:
        lines += ["", "Tu respuesta anterior no pasó estas comprobaciones. Corrígelas todas:"]
        lines += feedback
    result = llm.complete_json(system, "\n".join(lines), AdaptedText, max_tokens=3_000)
    by_index = {s.index: _tidy(s.text) for s in result.sentences}
    return [by_index.get(i, "") for i in range(1, len(sentences) + 1)] if by_index else []


def _review_es(
    llm: LLM, taxon: str, en: list[tuple[str, list[str], str]], es: list[str]
) -> list[str]:
    """Grammar pass over a Spanish text that already passed its checks."""
    system, _ = prompt("review_es")
    lines = [f"ANIMAL: {taxon}", "", "FRASES:"]
    for i, ((english, _, _), spanish) in enumerate(zip(en, es, strict=True), start=1):
        lines += [f"{i}. {spanish}", f"   (inglés: {english})"]
    result = llm.complete_json(system, "\n".join(lines), AdaptedText, max_tokens=3_000)
    by_index = {s.index: _tidy(s.text) for s in result.sentences}
    return [by_index.get(i, "") for i in range(1, len(es) + 1)]


def _save(
    path: Path,
    *,
    taxon: str,
    key: str,
    lang: str,
    status: str,
    llm: LLM,
    version: str,
    facts_hash: str,
    sentences: list[tuple[str, list[str], str]],
    report: TextReport | None,
    problems: list[str],
    review: str | None = None,
) -> None:
    sections: dict[str, list[dict[str, Any]]] = {}
    for text, fact_ids, section in sentences:
        sections.setdefault(section, []).append({"text": text, "fact_ids": fact_ids})
    record = {
        "taxon": taxon,
        "taxon_key": key,
        "lang": lang,
        "status": status,
        "generator": llm.label,
        "prompt_version": version,
        "facts_hash": facts_hash,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "word_count": report.word_count if report else None,
        "problems": problems,
        **({"review": review} if review else {}),
        "sections": [{"section": s, "sentences": v} for s, v in sections.items()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(record, ensure_ascii=False, indent=1) + "\n")


def write_page(
    llm: LLM,
    facts_path: Path,
    chunks: list[Chunk],
    *,
    derived_root: Path,
    scientific_names: set[str],
    retries: int = 2,
) -> WriteResult:
    facts_doc = json.loads(facts_path.read_text(encoding="utf-8"))
    taxon, key = facts_doc["taxon"], facts_doc["taxon_key"]
    facts = select_facts(facts_doc["facts"])
    current_hash = facts_hash(facts_doc["facts"])
    fact_texts = _fact_texts(facts)
    sources = {
        lang: [c.text for c in chunks if c.lang == lang and c.public_quote] for lang in ("en", "es")
    }
    result = WriteResult(key)
    versions = prompt_versions()
    en_version, es_version = versions["en"], versions["es"]

    # English from the facts.
    feedback: list[str] | None = None
    for _attempt in range(retries + 1):
        en = _flatten(_write_en(llm, taxon, facts, feedback))
        en_report = check_text([(t, f) for t, f, _ in en], fact_texts, sources["en"])
        if en_report.passed:
            break
        feedback = en_report.summary()
    en_status = "verified" if en_report.passed else "failed"
    folder = "texts" if en_report.passed else "texts_review"
    _save(
        derived_root / folder / f"{key}.en.json",
        taxon=taxon,
        key=key,
        lang="en",
        status=en_status,
        llm=llm,
        version=en_version,
        facts_hash=current_hash,
        sentences=en,
        report=en_report,
        problems=en_report.summary(),
    )
    result.status["en"] = en_status
    result.problems["en"] = en_report.summary()
    result.words["en"] = en_report.word_count
    if not en_report.passed:
        return result  # no Spanish adaptation of an unverified text

    # Spanish adapted from the verified English, sentence by sentence.
    def check_es(adapted: list[str]) -> tuple[list, TextReport, list[str]]:
        problems = check_alignment([(t, f) for t, f, _ in en], adapted, scientific_names)
        es = [(text, f, s) for text, (_, f, s) in zip(adapted, en, strict=False)]
        report = check_text(
            [(t, f) for t, f, _ in es], fact_texts, sources["es"], check_names=False
        )
        return es, report, problems + report.summary()

    feedback = None
    for _attempt in range(retries + 1):
        adapted = _adapt_es(llm, taxon, en, feedback)
        es, es_report, problems = check_es(adapted)
        if not problems:
            break
        feedback = problems
    review = None
    if not problems:
        # Grammar pass; kept only if the corrected text still passes every check.
        reviewed = _review_es(llm, taxon, en, adapted)
        if reviewed == adapted:
            review = "unchanged"
        else:
            r_es, r_report, r_problems = check_es(reviewed)
            review = "rejected" if r_problems else "accepted"
            if not r_problems:
                es, es_report = r_es, r_report
    es_status = "verified" if not problems else "failed"
    _save(
        derived_root / ("texts" if not problems else "texts_review") / f"{key}.es.json",
        taxon=taxon,
        key=key,
        lang="es",
        status=es_status,
        llm=llm,
        version=es_version,
        facts_hash=current_hash,
        sentences=es,
        report=es_report,
        problems=problems,
        review=review,
    )
    result.status["es"] = es_status
    result.review = review
    result.problems["es"] = problems
    result.words["es"] = es_report.word_count
    return result
