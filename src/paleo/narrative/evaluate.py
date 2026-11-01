"""Evaluate one LLM configuration against the gold set (decision A18).

For each gold taxon the full pipeline (facts -> EN -> ES) runs with the given
model, into a separate folder so production output is never touched. Metrics:

* **checks** — whether the EN and ES texts pass the deterministic checks;
* **fact recall** — share of gold facts matched by an extracted fact;
* **text recall** — share of gold facts that end up said in the EN text;
* cost — calls, tokens and seconds.

"Matched" means cosine similarity of sentence embeddings (local Ollama model)
above a threshold, so a paraphrase counts and wording does not matter.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from paleo.llm import LLM, QuotaExhausted
from paleo.narrative import gold
from paleo.narrative.facts import extract_facts
from paleo.narrative.sources import Chunk
from paleo.narrative.write import write_page

EMBED_MODEL = "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
MATCH_THRESHOLD = (
    0.75  # cosine similarity; calibrated by hand on the Spinosaurus pair (ALCANCE §12)
)


class Embedder:
    """Sentence embeddings from a local Ollama model, cached in memory."""

    def __init__(self, model: str = EMBED_MODEL, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.url = f"{base_url}/api/embed"
        self._cache: dict[str, list[float]] = {}

    def __call__(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            body = httpx.post(self.url, json={"model": self.model, "input": missing}, timeout=300)
            body.raise_for_status()
            for text, vector in zip(missing, body.json()["embeddings"], strict=True):
                self._cache[text] = vector
        return [self._cache[t] for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def recall(
    reference: list[str],
    candidates: list[str],
    embed: Callable[[list[str]], list[list[float]]],
    threshold: float = MATCH_THRESHOLD,
) -> tuple[float, list[float]]:
    """Share of ``reference`` texts with a candidate above ``threshold``, and
    the best similarity of each reference text."""
    if not reference:
        return 1.0, []
    if not candidates:
        return 0.0, [0.0] * len(reference)
    ref_vectors = embed(reference)
    cand_vectors = embed(candidates)
    best = [max(cosine(r, c) for c in cand_vectors) for r in ref_vectors]
    return sum(b >= threshold for b in best) / len(reference), best


@dataclass
class TaxonResult:
    taxon: str
    status: str = "done"  # done | pending_quota | error
    facts_accepted: int = 0
    facts_rejected: int = 0
    reject_reasons: dict[str, int] = field(default_factory=dict)
    en: str | None = None  # verified | failed
    es: str | None = None
    en_words: int | None = None
    es_words: int | None = None
    problems: list[str] = field(default_factory=list)
    fact_recall: float | None = None
    text_recall: float | None = None
    error: str | None = None


def _reason_kind(reason: str) -> str:
    return reason.split(":")[0]


def evaluate_taxon(
    llm: LLM,
    doc: dict[str, Any],
    chunks: list[Chunk],
    *,
    run_dir: Path,
    cache_root: Path,
    scientific_names: set[str],
    embed: Callable[[list[str]], list[list[float]]],
) -> TaxonResult:
    result = TaxonResult(doc["taxon"])
    derived = run_dir / "derived"
    try:
        facts = extract_facts(
            llm, doc["taxon"], chunks, derived_root=derived, cache_root=cache_root
        )
        written = write_page(
            llm, facts.path, chunks, derived_root=derived, scientific_names=scientific_names
        )
    except QuotaExhausted as exc:
        result.status, result.error = "pending_quota", str(exc)
        return result
    except Exception as exc:  # one bad taxon must not stop the evaluation
        result.status, result.error = "error", f"{type(exc).__name__}: {exc}"[:300]
        return result

    facts_doc = json.loads(facts.path.read_text(encoding="utf-8"))
    result.facts_accepted = facts.accepted
    result.facts_rejected = facts.rejected
    result.reject_reasons = dict(Counter(_reason_kind(r["reason"]) for r in facts_doc["rejected"]))
    result.en, result.es = written.status.get("en"), written.status.get("es")
    result.en_words, result.es_words = written.words.get("en"), written.words.get("es")
    result.problems = [f"[{lang}] {p}" for lang, ps in written.problems.items() for p in ps]

    gold_statements = [f["statement"] for f in doc["facts"]]
    result.fact_recall, _ = recall(
        gold_statements, [f["statement"] for f in facts_doc["facts"]], embed
    )
    folder = "texts" if written.status.get("en") == "verified" else "texts_review"
    en_path = derived / folder / f"{doc['taxon_key']}.en.json"
    if en_path.exists():
        en = json.loads(en_path.read_text(encoding="utf-8"))
        sentences = [s["text"] for sec in en["sections"] for s in sec["sentences"]]
        result.text_recall, _ = recall(gold_statements, sentences, embed)
    return result


def summarize(results: list[TaxonResult], llm: LLM) -> dict[str, Any]:
    done = [r for r in results if r.status == "done"]

    def mean(values: list[float | None]) -> float | None:
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    return {
        "generator": llm.label,
        "evaluated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "taxa": len(results),
        "done": len(done),
        "pending_quota": sum(r.status == "pending_quota" for r in results),
        "errors": sum(r.status == "error" for r in results),
        "en_verified": sum(r.en == "verified" for r in done),
        "es_verified": sum(r.es == "verified" for r in done),
        "fact_recall": mean([r.fact_recall for r in done]),
        "text_recall": mean([r.text_recall for r in done]),
        "facts_accepted": sum(r.facts_accepted for r in done),
        "facts_rejected": sum(r.facts_rejected for r in done),
        "mean_en_words": mean([r.en_words for r in done]),
        "calls": llm.stats.calls,
        "cached_calls": llm.stats.cached,
        "prompt_tokens": llm.stats.prompt_tokens,
        "completion_tokens": llm.stats.completion_tokens,
        "seconds": round(llm.stats.seconds, 1),
        "match_threshold": MATCH_THRESHOLD,
        "results": [asdict(r) for r in results],
    }


def write_report(summary: dict[str, Any], reports_dir: Path, label: str) -> Path:
    """Markdown + JSON report in ``eval/reports``."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{dt.date.today().isoformat()}-{label}"
    (reports_dir / f"{stem}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    s = summary
    lines = [
        f"# Evaluation — {s['generator']}",
        "",
        f"{s['evaluated_at']} · gold set of {s['taxa']} taxa · "
        f"match threshold {s['match_threshold']}",
        "",
        "Recall metrics compare meanings with sentence embeddings; by hand calibration they",
        "can be off by one or two facts per taxon, so use them to compare configurations.",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Taxa evaluated / pending quota / errors | "
        f"{s['done']} / {s['pending_quota']} / {s['errors']} |",
        f"| EN pages verified | {s['en_verified']} / {s['done']} |",
        f"| ES pages verified | {s['es_verified']} / {s['done']} |",
        f"| Fact recall (gold facts found by extraction) | {s['fact_recall']} |",
        f"| Text recall (gold facts said in the EN text) | {s['text_recall']} |",
        f"| Facts accepted / rejected | {s['facts_accepted']} / {s['facts_rejected']} |",
        f"| Mean EN words | {s['mean_en_words']} |",
        f"| Model calls (cached) | {s['calls']} ({s['cached_calls']}) |",
        f"| Tokens (prompt + completion) | {s['prompt_tokens']} + {s['completion_tokens']} |",
        f"| Model time (s) | {s['seconds']} |",
        "",
        "| Taxon | Status | Facts ok/rej | EN | ES | EN words | Fact recall | Text recall |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in s["results"]:
        lines.append(
            f"| {r['taxon']} | {r['status']} | {r['facts_accepted']}/{r['facts_rejected']} | "
            f"{r['en'] or '—'} | {r['es'] or '—'} | {r['en_words'] or '—'} | "
            f"{r['fact_recall'] if r['fact_recall'] is not None else '—'} | "
            f"{r['text_recall'] if r['text_recall'] is not None else '—'} |"
        )
    problems = [(r["taxon"], p) for r in s["results"] for p in r["problems"][:3]]
    if problems:
        lines += ["", "## Failed checks (first 3 per taxon)", ""]
        lines += [f"- *{t}*: {p}" for t, p in problems]
    path = reports_dir / f"{stem}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_gold(project_root: Path) -> list[dict[str, Any]]:
    return [gold.load(p) for p in sorted((project_root / gold.GOLD_DIR).glob("*.json"))]
