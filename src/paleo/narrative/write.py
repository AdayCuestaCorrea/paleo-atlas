"""Step 2 of a narrative page: write English prose from verified facts, then adapt
it to Spanish sentence by sentence, and check both (ALCANCE.md §12.1).

A text that fails its checks gets one retry with the list of problems; if it
fails again it is saved for review and the site keeps the fallback text.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, Field

from paleo.llm import LLM
from paleo.narrative.checks import (
    MAX_WORDS,
    TextReport,
    alignment_failures,
    check_alignment,
    check_text,
)
from paleo.narrative.facts import Category, prompt
from paleo.narrative.sources import Chunk
from paleo.store import _atomic_write

SECTION_ORDER = [
    "description",
    "curiosities",
    "discovery",
    "paleobiology",
    "classification",
    "time_and_habitat",
    "debate",
]


# Sub-topics of the paleobiology section: the site gives them headings when the
# section is long enough (ALCANCE.md §12.1).
PaleoTopic = Literal["diet", "growth", "locomotion_senses", "behavior", "health"]
PALEO_TOPICS = list(PaleoTopic.__args__)


class WrittenSentence(BaseModel):
    text: str
    fact_ids: list[str] = Field(description="ids of the facts this sentence relies on")
    topic: PaleoTopic | None = Field(
        default=None, description="only in the paleobiology section: its sub-topic"
    )


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


MAX_FACTS_FOR_WRITING = 36


# How many of the selected facts each section may take: the living animal
# (paleobiology, curiosities) gets more room than the history of research.
SECTION_QUOTA = {
    "description": 5,
    "curiosities": 8,
    "discovery": 3,
    "paleobiology": 12,
    "classification": 3,
    "time_and_habitat": 3,
    "debate": 3,
}


def _spread(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Facts taken in turns from each source chunk, so a section's quota covers the
    whole source (diet, senses, injuries…) and not only its first paragraph."""
    by_chunk: dict[str, list[dict[str, Any]]] = {}
    for f in facts:
        by_chunk.setdefault(f.get("chunk_id") or "", []).append(f)
    out: list[dict[str, Any]] = []
    while any(by_chunk.values()):
        for queue in by_chunk.values():
            if queue:
                out.append(queue.pop(0))
    return out


def select_facts(facts: list[dict[str, Any]], limit: int = MAX_FACTS_FOR_WRITING) -> list[dict]:
    """At most ``limit`` facts: each section up to its quota (spread over the source),
    then whatever is left in turns, so a long article yields a balanced page."""
    by_section: dict[str, list[dict[str, Any]]] = {name: [] for name in SECTION_ORDER}
    for fact in facts:
        by_section.setdefault(fact["category"], []).append(fact)
    queues = {name: _spread(items) for name, items in by_section.items()}
    chosen: list[dict[str, Any]] = []
    for name, queue in queues.items():
        take = min(SECTION_QUOTA.get(name, 3), len(queue), limit - len(chosen))
        chosen += queue[:take]
        del queue[:take]
    while len(chosen) < min(limit, len(facts)):  # unused quota goes round the sections
        for queue in queues.values():
            if queue and len(chosen) < limit:
                chosen.append(queue.pop(0))
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
    """~120 words for a sparse taxon, up to ~700 for a well documented one."""
    return max(120, min(700, 40 + 18 * fact_count))


_SPACES = str.maketrans({"\u00a0": " ", "\u202f": " ", "\u2009": " ", "\u2011": "-"})


def _tidy(text: str) -> str:
    """Plain spaces and hyphens (models like narrow no-break spaces)."""
    return " ".join(text.translate(_SPACES).split())


def _canonical_id(fact_id: str) -> str:
    """ "F0113" -> "F113": with more than 99 facts the model sometimes pads the id like
    the two-digit ones ("F013"). Ids are F + at least three digits."""
    m = re.fullmatch(r"F0*(\d+)", fact_id.strip())
    return f"F{int(m.group(1)):03d}" if m else fact_id


def _flatten(text: WrittenText) -> list[tuple[str, list[str], str]]:
    """(sentence, fact_ids, section) in the canonical section order."""
    order = {name: i for i, name in enumerate(SECTION_ORDER)}
    out = []
    for section in sorted(text.sections, key=lambda s: order.get(s.section, 99)):
        for s in section.sentences:
            # "paleobiology:diet": the sub-topic travels with the section (the Spanish
            # version inherits it from the English sentence); _save splits it.
            name = section.section
            if name == "paleobiology" and s.topic in PALEO_TOPICS:
                name = f"{name}:{s.topic}"
            out.append((_tidy(s.text), [_canonical_id(i) for i in s.fact_ids], name))
    return out


MAX_DROPPED_SENTENCES = 3


def _salvage(sentences: list, report: TextReport) -> list | None:
    """The sentences that passed, when only a few failed and the text as a whole has no
    problem (length…): a long page is not lost for one unsourced number. None when the
    failures are too many or text-level. What remains is checked again by the caller."""
    failed = {r.index for r in report.sentences if r.problems}
    if report.problems or not failed or len(failed) > MAX_DROPPED_SENTENCES:
        return None
    kept = [x for i, x in enumerate(sentences) if i not in failed]
    return kept if len(kept) >= 3 else None


def _salvage_es(
    en: list[tuple[str, list[str], str]],
    adapted: list[str],
    es: list[tuple[str, list[str], str]],
    report: TextReport,
    scientific_names: set[str],
) -> list | None:
    """As _salvage, for a Spanish adaptation: the sentences that failed their checks
    or the alignment with their English sentence (other numbers, a lost name) are
    left out, when they are a few. None if the sentence count differs."""
    misaligned = alignment_failures([(t, f) for t, f, _ in en], adapted, scientific_names)
    if misaligned is None or report.problems:
        return None
    failed = {r.index for r in report.sentences if r.problems} | misaligned
    if not failed or len(failed) > MAX_DROPPED_SENTENCES:
        return None
    kept = [x for i, x in enumerate(es) if i not in failed]
    return kept if len(kept) >= 3 else None


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
        lines += [
            "",
            "Cómo corregirlas: una frase por cada frase inglesa, con el mismo índice; los "
            "números iguales que en inglés (con coma decimal) y escritos con cifras; NO "
            "conviertas unidades (3.45 t es «3,45 t», nunca «3450 kg»; 8.8 m es «8,8 m»); los "
            "géneros y especies sin traducir (los clados por encima de la familia pueden ir en "
            "español); y si una frase copia ocho palabras seguidas de una fuente, reescríbela "
            "de verdad: cambia el orden de la frase, el verbo y la construcción, no solo una "
            "palabra suelta.",
        ]
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
        name, _, topic = section.partition(":")
        sentence = {"text": text, "fact_ids": fact_ids, **({"topic": topic} if topic else {})}
        sections.setdefault(name, []).append(sentence)
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
    if path.parent.name == "texts":  # a verified text retires the failed one it replaces
        (path.parent.parent / "texts_review" / path.name).unlink(missing_ok=True)


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
    if not en_report.passed and (kept := _salvage(en, en_report)) is not None:
        report = check_text([(t, f) for t, f, _ in kept], fact_texts, sources["en"])
        if report.passed:  # the failed sentences are left out, the rest is verified
            en, en_report = kept, report
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
    salvaged = False
    for _attempt in range(retries + 1):
        adapted = _adapt_es(llm, taxon, en, feedback)
        es, es_report, problems = check_es(adapted)
        if not problems:
            break
        feedback = problems
    if problems and (kept := _salvage_es(en, adapted, es, es_report, scientific_names)) is not None:
        report = check_text(
            [(t, f) for t, f, _ in kept], fact_texts, sources["es"], check_names=False
        )
        if report.passed:  # aligned, but a few Spanish sentences failed: leave them out
            es, es_report, problems = kept, report, []
            salvaged = True
    review = None
    if salvaged:
        review = "skipped"  # no sentence-by-sentence pass over a shortened text
    elif not problems:
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


def _stored_sentences(doc: dict[str, Any]) -> list[tuple[str, list[str], str]]:
    """(text, fact ids, section[:topic]) of a saved text, in order."""
    return [
        (
            s["text"],
            s["fact_ids"],
            section["section"] + (f":{s['topic']}" if s.get("topic") else ""),
        )
        for section in doc["sections"]
        for s in section["sentences"]
    ]


def resalvage_es(
    derived_root: Path,
    es_sources: Callable[[str], list[str]],
    scientific_names: set[str],
) -> dict[str, list[str]]:
    """Check again, with today's checks and rescue, the Spanish adaptations that failed
    (texts_review), without calling any model: those that pass now, or after leaving
    out a few failed sentences, are saved as verified. Only when their English text is
    verified and every file is of the same facts. ``es_sources`` gives the Spanish
    source texts of a genus (for the anti-copy check)."""
    out: dict[str, list[str]] = {"salvaged": [], "still_failed": [], "skipped": []}
    for path in sorted((derived_root / "texts_review").glob("*.es.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        key = doc["taxon_key"]
        en_path = derived_root / "texts" / f"{key}.en.json"
        facts_path = derived_root / "facts" / f"{key}.json"
        if not (en_path.exists() and facts_path.exists()):
            out["skipped"].append(key)
            continue
        en_doc = json.loads(en_path.read_text(encoding="utf-8"))
        facts_doc = json.loads(facts_path.read_text(encoding="utf-8"))
        current = facts_hash(facts_doc["facts"])
        if en_doc.get("status") != "verified" or not (
            en_doc.get("facts_hash") == doc.get("facts_hash") == current
        ):
            out["skipped"].append(key)
            continue
        en = _stored_sentences(en_doc)
        adapted = [t for t, _, _ in _stored_sentences(doc)]
        fact_texts = _fact_texts(select_facts(facts_doc["facts"]))
        sources = es_sources(doc["taxon"])
        es = [(text, f, s) for text, (_, f, s) in zip(adapted, en, strict=False)]
        report = check_text([(t, f) for t, f, _ in es], fact_texts, sources, check_names=False)
        kept: list | None = es
        if (
            check_alignment([(t, f) for t, f, _ in en], adapted, scientific_names)
            or not report.passed
        ):
            kept = _salvage_es(en, adapted, es, report, scientific_names)
            if kept is not None:
                report = check_text(
                    [(t, f) for t, f, _ in kept], fact_texts, sources, check_names=False
                )
                kept = kept if report.passed else None
        if kept is None:
            out["still_failed"].append(key)
            continue
        _save(
            derived_root / "texts" / f"{key}.es.json",
            taxon=doc["taxon"],
            key=key,
            lang="es",
            status="verified",
            llm=SimpleNamespace(label=doc["generator"]),  # the model that wrote it
            version=doc["prompt_version"],
            facts_hash=current,
            sentences=kept,
            report=report,
            problems=[],
            review="skipped",  # no grammar pass over a text that was not re-adapted
        )
        out["salvaged"].append(key)
    return out
