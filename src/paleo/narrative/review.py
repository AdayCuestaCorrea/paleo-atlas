"""A model as reviewer of the written pages (ALCANCE.md, Phase 7, step 5).

The rules of ``checks`` catch what has a pattern; a sentence that misreads its source
("reached maturity in a year" for a one-year-old juvenile) needs a reader. The local
model reads each English sentence with the quotes of the facts it cites, and its
Spanish version, and flags the clear errors. Its flags are only recorded
(``derived/review_flags/<taxon>.json``): no text changes until the measurement on
the 15 hand-reviewed pages (``eval/fichas``) says how far to trust them.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from paleo.narrative.facts import prompt
from paleo.store import _atomic_write

BATCH = 3  # sentences per call: with 8 the 9B model passed every sentence (measured 2026-11-23)


class SentenceReview(BaseModel):
    index: int
    en_ok: bool
    en_reason: str = ""
    es_ok: bool = True
    es_reason: str = ""


class PageReview(BaseModel):
    sentences: list[SentenceReview]


def flags_dir(derived_root: Path) -> Path:
    return derived_root / "review_flags"


def _sentences(doc: dict[str, Any]) -> list[tuple[str, list[str], str]]:
    from paleo.narrative.write import _stored_sentences

    return _stored_sentences(doc)


def page_pairs(derived_root: Path, key: str) -> list[dict[str, Any]] | None:
    """English sentences of a verified page, each with its cited facts and its Spanish
    sentence (None when it has none); None when the page has no verified English text."""
    from paleo.narrative.write import _match_kept

    en_path = derived_root / "texts" / f"{key}.en.json"
    if not en_path.exists():
        return None
    en_doc = json.loads(en_path.read_text(encoding="utf-8"))
    if en_doc.get("status") != "verified":
        return None
    en = _sentences(en_doc)
    es_by_index: dict[int, str] = {}
    es_path = derived_root / "texts" / f"{key}.es.json"
    if es_path.exists():
        es = _sentences(json.loads(es_path.read_text(encoding="utf-8")))
        if (index := _match_kept(en, es)) is not None:
            es_by_index = {i: es[j][0] for j, i in enumerate(index)}
    facts_path = derived_root / "facts" / f"{key}.json"
    facts = []
    if facts_path.exists():
        facts = json.loads(facts_path.read_text(encoding="utf-8"))["facts"]
    by_id = {f["fact_id"]: f for f in facts}
    return [
        {"en": text, "es": es_by_index.get(i), "facts": [by_id[x] for x in ids if x in by_id]}
        for i, (text, ids, _) in enumerate(en)
    ]


def _text_hash(pairs: list[dict[str, Any]]) -> str:
    joined = "\n".join(f"{p['en']}\t{p['es'] or ''}" for p in pairs)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def _user_message(taxon: str, batch: list[tuple[int, dict[str, Any]]]) -> str:
    lines = [f"Page: {taxon}", ""]
    for n, p in batch:
        lines.append(f"[{n}] EN: {p['en']}")
        for f in p["facts"]:
            lines.append(f"    {f['fact_id']}: {f.get('statement', '')}")
            lines.append(f'      quote: "{f.get("quote", "")}"')
        lines.append(f"    ES: {p['es'] or '(none)'}")
        lines.append("")
    return "\n".join(lines)


def review_page(llm: Any, taxon: str, pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flags of one page: [{index, lang, sentence, reason}], index from 0."""
    system, _ = prompt("review_text")
    flags: list[dict[str, Any]] = []
    numbered = list(enumerate(pairs, start=1))
    for start in range(0, len(numbered), BATCH):
        batch = numbered[start : start + BATCH]
        result = llm.complete_json(system, _user_message(taxon, batch), PageReview,
                                   max_tokens=1_500)  # fmt: skip
        wanted = {n for n, _ in batch}
        for r in result.sentences:
            if r.index not in wanted:
                continue
            p = pairs[r.index - 1]
            if not r.en_ok:
                flags.append({"index": r.index - 1, "lang": "en", "sentence": p["en"],
                              "reason": r.en_reason})  # fmt: skip
            if not r.es_ok and p["es"]:
                flags.append({"index": r.index - 1, "lang": "es", "sentence": p["es"],
                              "reason": r.es_reason})  # fmt: skip
    return flags


def is_reviewed(derived_root: Path, key: str, pairs: list[dict[str, Any]]) -> bool:
    path = flags_dir(derived_root) / f"{key}.json"
    if not path.exists():
        return False
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc.get("text_hash") == _text_hash(pairs) and (
        doc.get("prompt_version") == prompt("review_text")[1]
    )


def save_flags(derived_root: Path, key: str, taxon: str, llm: Any,
               pairs: list[dict[str, Any]], flags: list[dict[str, Any]]) -> None:  # fmt: skip
    record = {
        "taxon": taxon, "taxon_key": key, "generator": llm.label,
        "prompt_version": prompt("review_text")[1], "text_hash": _text_hash(pairs),
        "reviewed_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "sentences": len(pairs), "flags": flags,
    }  # fmt: skip
    path = flags_dir(derived_root) / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(record, ensure_ascii=False, indent=1) + "\n")


# --- measurement on the 15 hand-reviewed pages (step 5a) ----------------------------

# The bar agreed for running the reviewer over every page: it finds at least 40 % of
# the high and medium text problems still in the evaluated texts, and flags at most
# 10 % of the sentences that have no known problem (a lower bound of its precision:
# some of those may be real errors the hand review missed).
MIN_RECALL = 0.40
MAX_FALSE_FLAG_RATE = 0.10


def evaluate(llm: Any, derived_root: Path, eval_dir: Path) -> dict[str, Any]:
    rows = [r for r in csv.DictReader((eval_dir / "findings.csv").open(encoding="utf-8"))
            if r["element"] == "text"]  # fmt: skip
    pages = sorted({r["taxon_key"] for r in rows})
    expected: set[tuple[str, str, str]] = set()  # (key, lang, sentence), high or medium
    known: set[tuple[str, str, str]] = set()  # any severity
    for r in rows:
        for lang in ("en", "es"):
            for s in filter(None, r[f"{lang}_sentences"].split(" || ")):
                known.add((r["taxon_key"], lang, s))
                if r["severity"] in ("high", "medium"):
                    expected.add((r["taxon_key"], lang, s))
    present: set[tuple[str, str, str]] = set()
    flagged: set[tuple[str, str, str]] = set()
    clean_total = 0
    per_page = {}
    for key in pages:
        pairs = page_pairs(derived_root, key)
        if not pairs:
            continue
        taxon = json.loads((derived_root / "texts" / f"{key}.en.json").read_text("utf-8"))["taxon"]
        flags = review_page(llm, taxon, pairs)
        save_flags(derived_root, key, taxon, llm, pairs, flags)
        per_page[key] = len(flags)
        for p in pairs:
            for lang in ("en", "es"):
                s = p[lang]
                if not s:
                    continue
                if (key, lang, s) not in known:
                    clean_total += 1
                if (key, lang, s) in expected:
                    present.add((key, lang, s))
        flagged |= {(key, f["lang"], f["sentence"]) for f in flags}
    found = present & flagged
    false_flags = {f for f in flagged if f not in known}
    recall = len(found) / len(present) if present else 0.0
    false_rate = len(false_flags) / clean_total if clean_total else 0.0
    return {
        "model": llm.label, "prompt_version": prompt("review_text")[1],
        "expected": len(present), "found": len(found), "recall": round(recall, 3),
        "clean_sentences": clean_total, "false_flags": len(false_flags),
        "false_flag_rate": round(false_rate, 3), "flags_per_page": per_page,
        "found_list": sorted(" | ".join(x) for x in found),
        "passes": recall >= MIN_RECALL and false_rate <= MAX_FALSE_FLAG_RATE,
        "bar": {"min_recall": MIN_RECALL, "max_false_flag_rate": MAX_FALSE_FLAG_RATE},
        "measured_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }  # fmt: skip


# --- whole-page review (step 5, chosen in eval/fichas/reviewer_study.md) -------------

PAGE_MODEL = "gpt-oss:20b"  # reasoning "low": 14/42 found on the 15 pages, 19/23 flags real
Kind = Literal["contradiction", "repetition", "missing_context", "about_something_else"]


REWRITE_KINDS = ("contradiction", "missing_context")


class PageProblem(BaseModel):
    sentences: list[int]
    kind: Kind
    reason: str


class PageProblems(BaseModel):
    problems: list[PageProblem]


def pages_dir(derived_root: Path) -> Path:
    return derived_root / "review_pages"


def review_whole_page(llm: Any, taxon: str, pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Problems of one page read as a whole: [{sentences (from 0), kind, reason}]."""
    system, _ = prompt("review_page")
    user = f"Page: {taxon}\n\n" + "\n".join(f"[{i}] {p['en']}" for i, p in enumerate(pairs, 1))
    result = llm.complete_json(system, user, PageProblems, max_tokens=6_000)
    out = []
    for p in result.problems:
        idx = sorted({n - 1 for n in p.sentences if 1 <= n <= len(pairs)})
        if idx:
            out.append({"sentences": idx, "kind": p.kind, "reason": p.reason})
    return out


def page_record(derived_root: Path, key: str) -> dict[str, Any] | None:
    path = pages_dir(derived_root) / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_page_record(derived_root: Path, key: str, record: dict[str, Any]) -> None:
    path = pages_dir(derived_root) / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(record, ensure_ascii=False, indent=1) + "\n")


def is_page_reviewed(derived_root: Path, key: str, pairs: list[dict[str, Any]]) -> bool:
    doc = page_record(derived_root, key)
    return (
        bool(doc)
        and doc.get("text_hash") == _text_hash(pairs)
        and (doc.get("prompt_version") == prompt("review_page")[1])
    )


MAX_ROUNDS = 2  # a rewritten page is reviewed once more; its fixes are not reviewed again


def needs_review(derived_root: Path, key: str, pairs: list[dict[str, Any]]) -> bool:
    """A page is reviewed when it has no review of its current text and prompt, and once
    more after a rewrite replaced it (the rewrite may bring its own problems: on the 15
    pages the whole-page rewrites fixed 14 known problems and added 8)."""
    if not is_page_reviewed(derived_root, key, pairs):
        return True
    doc = page_record(derived_root, key) or {}
    return doc.get("rewrite") == "replaced" and doc.get("round", 1) < MAX_ROUNDS


def next_round(previous: dict[str, Any] | None) -> dict[str, Any]:
    """The round of a new review and the earlier reviews of the page, oldest first."""
    if not previous or previous.get("rewrite") != "replaced":
        return {"round": 1}
    earlier = previous.get("earlier", [])
    keep = ("reviewed_at", "problems", "repetitions_dropped", "rewrite", "rewrite_mode",
            "rewritten_at")  # fmt: skip
    earlier = [*earlier, {k: previous[k] for k in keep if k in previous}]
    return {"round": previous.get("round", 1) + 1, "earlier": earlier}


def drop_repetitions(derived_root: Path, key: str, problems: list[dict[str, Any]]) -> int:
    """Leave out the later sentences of each repeated claim, in English and in Spanish
    (no model). Within the page's limit of dropped sentences; returns how many."""
    from types import SimpleNamespace

    from paleo.narrative.write import (
        _match_kept,
        _max_dropped,
        _save,
        _stored_sentences,
        _word_count,
    )

    later = {i for p in problems if p["kind"] == "repetition" for i in p["sentences"][1:]}
    if not later:
        return 0
    texts = derived_root / "texts"
    en_doc = json.loads((texts / f"{key}.en.json").read_text(encoding="utf-8"))
    en = _stored_sentences(en_doc)
    if len(later) > _max_dropped(len(en)) or len(en) - len(later) < 3:
        return 0
    docs = [("en", en_doc, en, set(later))]
    es_path = texts / f"{key}.es.json"
    if es_path.exists():
        es_doc = json.loads(es_path.read_text(encoding="utf-8"))
        es = _stored_sentences(es_doc)
        index = _match_kept(en, es)
        if index is not None:
            docs.append(("es", es_doc, es, {j for j, i in enumerate(index) if i in later}))
    for lang, doc, sents, drop in docs:
        kept = [x for i, x in enumerate(sents) if i not in drop]
        _save(
            texts / f"{key}.{lang}.json", taxon=doc["taxon"], key=key, lang=lang,
            status="verified", llm=SimpleNamespace(label=doc["generator"]),
            version=doc["prompt_version"], facts_hash=doc["facts_hash"], sentences=kept,
            report=SimpleNamespace(word_count=_word_count(kept)),  # type: ignore[arg-type]
            problems=[], review=doc.get("review"),
        )  # fmt: skip
    return len(later)


def review_notes(pairs: list[dict[str, Any]], problems: list[dict[str, Any]]) -> list[str]:
    """The reviewer's problems as notes for the writer, quoting the sentences."""
    notes = []
    for p in problems:
        # repetitions are already left out without a model; "about something else" is
        # often useful context (a relative, the group's history): recorded, not rewritten
        if p["kind"] not in REWRITE_KINDS:
            continue
        quoted = " / ".join(f'"{pairs[i]["en"]}"' for i in p["sentences"])
        notes.append(f"- {p['kind'].replace('_', ' ')}: {quoted}: {p['reason']}")
    return notes


def rewrite_page(
    llm: Any,
    key: str,
    chunks: list[Any],
    notes: list[str],
    *,
    derived_root: Path,
    scientific_names: set[str],
    ages: dict[str, tuple[float, float]],
) -> str:
    """Write the page again with the reviewer's notes, in a scratch folder, through
    every check and the Phase 7 recheck. The published texts are replaced only when the
    new English and Spanish are verified (Spanish only if the page had it): a failed
    rewrite never makes a page worse. Returns "replaced" or why not."""
    import shutil
    import tempfile

    from paleo.narrative.write import recheck_quality, write_page

    texts = derived_root / "texts"
    had_es = (texts / f"{key}.es.json").exists()
    with tempfile.TemporaryDirectory(prefix="paleo-rewrite-") as tmp_name:
        tmp = Path(tmp_name)
        (tmp / "facts").mkdir()
        shutil.copy(derived_root / "facts" / f"{key}.json", tmp / "facts" / f"{key}.json")
        write_page(llm, tmp / "facts" / f"{key}.json", chunks, derived_root=tmp,
                   scientific_names=scientific_names, review_notes=notes)  # fmt: skip
        recheck_quality(tmp, ages)
        new = {lang: tmp / "texts" / f"{key}.{lang}.json" for lang in ("en", "es")}
        if not new["en"].exists():
            return "english failed"
        if had_es and not new["es"].exists():
            return "spanish failed"
        for path in new.values():
            if path.exists():
                shutil.copy(path, texts / path.name)
                (derived_root / "texts_review" / path.name).unlink(missing_ok=True)
    return "replaced"


class FixedSentence(BaseModel):
    index: int
    text: str
    fact_ids: list[str]


class FixedSentences(BaseModel):
    sentences: list[FixedSentence]


def flagged_now(record: dict[str, Any], total: int) -> list[dict[str, Any]]:
    """The record's contradictions and missing context, with their sentence numbers
    moved to today's text: the review numbered the page before its repeated sentences
    were left out (drop_repetitions leaves out all of them or none)."""
    later: set[int] = set()
    if record.get("repetitions_dropped"):
        later = {i for p in record["problems"] if p["kind"] == "repetition"
                 for i in p["sentences"][1:]}  # fmt: skip
    out = []
    for p in record["problems"]:
        if p["kind"] not in REWRITE_KINDS:
            continue
        idx = [i - sum(j < i for j in later) for i in p["sentences"] if i not in later]
        idx = [i for i in idx if 0 <= i < total]
        if idx:
            out.append({**p, "sentences": idx})
    return out


def _fix_message(
    taxon: str,
    en: list[tuple[str, list[str], str]],
    problems: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    feedback: list[str] | None,
) -> str:
    flagged = sorted({i for p in problems for i in p["sentences"]})
    lines = [f"ANIMAL: {taxon}", "", "PAGE:"]
    lines += [f"[{i}] {t}" for i, (t, _, _) in enumerate(en, 1)]
    lines += ["", "PROBLEMS FOUND BY THE REVIEWER:"]
    lines += [
        f"- {p['kind'].replace('_', ' ')} in sentences "
        f"{', '.join(str(i + 1) for i in p['sentences'])}: {p['reason']}"
        for p in problems
    ]
    lines += ["", "TO FIX: sentences " + ", ".join(str(i + 1) for i in flagged)]
    lines += ["", "VERIFIED FACTS:"]
    lines += [f"{f['fact_id']} [{f['category']}] {f['statement']}" for f in facts]
    if feedback:
        lines += ["", "Your previous answer failed these automatic checks. Fix every one:",
                  *feedback,
                  "A number must be written exactly as in a cited fact or dropped; a name must "
                  "appear in the facts; a copied run of words must be rephrased."]  # fmt: skip
    return "\n".join(lines)


def fix_sentences(
    llm: Any,
    key: str,
    chunks: list[Any],
    problems: list[dict[str, Any]],
    *,
    derived_root: Path,
    scientific_names: set[str],
    ages: dict[str, tuple[float, float]],
    retries: int = 2,
) -> str:
    """Write again only the sentences the reviewer flagged (``problems`` numbered on
    today's text, from flagged_now); the rest of the page, and the Spanish of the rest,
    stay as they are. The new sentences go through every check, their Spanish is
    adapted and aligned, and the page through the Phase 7 recheck, in a scratch folder:
    the published texts are replaced only when all of it passes. Returns "replaced" or
    why not. Asked for by the user on 2026-11-25, after the whole-page rewrites of
    nights 8-9 fixed 14 known problems on the 15 pages but added 8 and shortened some."""
    import shutil
    import tempfile
    from types import SimpleNamespace

    from paleo.narrative.checks import check_alignment, check_text
    from paleo.narrative.write import (
        _adapt_es,
        _canonical_id,
        _fact_texts,
        _match_kept,
        _max_dropped,
        _save,
        _stored_sentences,
        _tidy,
        _word_count,
        recheck_quality,
        select_facts,
    )

    texts = derived_root / "texts"
    en_doc = json.loads((texts / f"{key}.en.json").read_text(encoding="utf-8"))
    en = _stored_sentences(en_doc)
    flagged = {i for p in problems for i in p["sentences"] if 0 <= i < len(en)}
    if not flagged:
        return "nothing to fix"
    facts_doc = json.loads((derived_root / "facts" / f"{key}.json").read_text("utf-8"))
    facts = select_facts(facts_doc["facts"])
    fact_texts = _fact_texts(facts)
    sources = {lang: [c.text for c in chunks if c.lang == lang and c.public_quote]
               for lang in ("en", "es")}  # fmt: skip
    taxon = en_doc["taxon"]
    system, _ = prompt("fix_sentences")

    def check(rows: list, lang: str) -> Any:
        sents = [(t, f) for (t, f, _), _, _ in rows]
        return check_text(sents, fact_texts, sources[lang], check_names=lang == "en")

    def holds(rows: list) -> bool:
        return len(en) - len(rows) <= _max_dropped(len(en)) and len(rows) >= 3

    # rows: (sentence, index of the English sentence it replaces, is new)
    rows: list[tuple[tuple[str, list[str], str], int, bool]] = []
    feedback: list[str] | None = None
    for attempt in range(retries + 1):
        result = llm.complete_json(system, _fix_message(taxon, en, problems, facts, feedback),
                                   FixedSentences, max_tokens=2_000)  # fmt: skip
        changes = {s.index - 1: s for s in result.sentences if s.index - 1 in flagged}
        if not changes:
            feedback = ["you returned none of the sentences listed under TO FIX"]
            continue
        rows = []
        for i, sent in enumerate(en):
            text = _tidy(changes[i].text) if i in changes else sent[0]
            if text == sent[0]:  # not changed, or returned as it was: keeps its Spanish
                rows.append((sent, i, False))
            elif text:
                ids = [_canonical_id(x) for x in changes[i].fact_ids]
                rows.append(((text, ids, sent[2]), i, True))
        report = check(rows, "en")
        if report.passed and holds(rows):
            break
        failed = {r.index for r in report.sentences if r.problems}
        last = attempt == retries  # on the last try, leave out the new ones that fail
        if last and not report.problems and all(rows[k][2] for k in failed):
            kept = [r for k, r in enumerate(rows) if k not in failed]
            if holds(kept) and check(kept, "en").passed:
                rows = kept
                break
        feedback = report.summary() or ["too many sentences left out: fix them instead"]
        rows = []
    if not rows:
        return "english failed"
    if len(rows) == len(en) and not any(r[2] for r in rows):
        return "unchanged"  # every flagged sentence came back as it was
    new_en = [r[0] for r in rows]

    # Spanish: the unchanged sentences keep theirs; only the new ones are adapted.
    es_path = texts / f"{key}.es.json"
    es_doc = json.loads(es_path.read_text(encoding="utf-8")) if es_path.exists() else None
    new_es = None
    if es_doc:
        es = _stored_sentences(es_doc)
        index = _match_kept(en, es)
        if index is None:
            return "spanish failed"
        es_of = {index[j]: es[j] for j in range(len(es))}
        need = [k for k, r in enumerate(rows) if r[2]]
        es_feedback: list[str] | None = None
        for _attempt in range(retries + 1):
            adapted = _adapt_es(llm, taxon, [new_en[k] for k in need], es_feedback) if need else []
            es_problems = check_alignment([new_en[k][:2] for k in need], adapted, scientific_names)
            if not es_problems:
                by_row = dict(zip(need, adapted, strict=True))
                es_rows = []
                for k, (sent, src, _) in enumerate(rows):
                    if k in by_row:
                        es_rows.append(((by_row[k], sent[1], sent[2]), src, True))
                    elif src in es_of:  # a sentence the Spanish had left out stays out
                        es_rows.append((es_of[src], src, False))
                report = check(es_rows, "es")
                if report.passed:
                    new_es = [r[0] for r in es_rows]
                    break
                es_problems = report.summary()
            es_feedback = es_problems
        if new_es is None:
            return "spanish failed"

    with tempfile.TemporaryDirectory(prefix="paleo-fix-") as tmp_name:
        tmp = Path(tmp_name)
        (tmp / "facts").mkdir()
        shutil.copy(derived_root / "facts" / f"{key}.json", tmp / "facts" / f"{key}.json")
        for lang, doc, sents in (("en", en_doc, new_en), ("es", es_doc, new_es)):
            if doc is None or sents is None:
                continue
            _save(tmp / "texts" / f"{key}.{lang}.json", taxon=taxon, key=key, lang=lang,
                  status="verified", llm=SimpleNamespace(label=llm.label),
                  version=doc["prompt_version"], facts_hash=doc["facts_hash"],
                  sentences=sents,
                  report=SimpleNamespace(word_count=_word_count(sents)),  # type: ignore[arg-type]
                  problems=[], review=doc.get("review"))  # fmt: skip
        recheck_quality(tmp, ages)
        out = {lang: tmp / "texts" / f"{key}.{lang}.json" for lang in ("en", "es")}
        if not out["en"].exists():
            return "english failed"
        if es_doc and not out["es"].exists():
            return "spanish failed"
        for path in out.values():
            if path.exists():
                shutil.copy(path, texts / path.name)
                (derived_root / "texts_review" / path.name).unlink(missing_ok=True)
    return "replaced"
