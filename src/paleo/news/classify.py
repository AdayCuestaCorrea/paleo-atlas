"""Category and scientific names of each news article, with an LLM (Groq in Actions).

The articles come from the raw store (``paleo ingest news``); the answers go to
``derived/news/labels.json``, one row per article with the hash of what the model saw
and the prompt version, so an article is only asked again if its headline or summary
changes or the prompt does. Articles are sent in batches to spend little quota.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from paleo.ingest import news as news_ingest
from paleo.llm import LLM
from paleo.narrative.facts import prompt
from paleo.store import _atomic_write

BATCH = 20
CATEGORIES = ("new_species", "new_fossil", "new_study", "revision", "noise")
Category = Literal["new_species", "new_fossil", "new_study", "revision", "noise"]


class ItemLabel(BaseModel):
    index: int
    category: Category
    taxa: list[str] = []


class BatchLabels(BaseModel):
    items: list[ItemLabel]


@dataclass
class ClassifyResult:
    total: int = 0
    up_to_date: int = 0
    classified: int = 0
    missing: int = 0  # items the model left out of its answer (asked again next run)


def labels_path(derived_root: Path) -> Path:
    return derived_root / "news" / "labels.json"


def stored_articles(raw_root: Path | None) -> dict[str, dict[str, Any]]:
    """Key -> latest payload of every stored article."""
    items = news_ingest.store(raw_root)
    out = {}
    for key in items.stored_keys():
        latest = items.latest(key)
        if latest:
            out[key] = latest["payload"]
    return out


def model_input(article: dict[str, Any]) -> str:
    """What the model sees of one article (and what its hash covers)."""
    text = article["title"]
    if article.get("summary"):
        text += " — " + article["summary"]
    return text


def input_hash(article: dict[str, Any]) -> str:
    return hashlib.sha1(model_input(article).encode()).hexdigest()[:12]


def load_labels(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["key"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


def save_labels(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps([rows[k] for k in sorted(rows)], ensure_ascii=False,
                                   indent=1) + "\n")  # fmt: skip


def classify_batch(
    llm: LLM, system: str, batch: list[tuple[str, dict[str, Any]]]
) -> dict[str, ItemLabel]:
    """Key -> the model's label, for the items it answered."""
    lines = [f"{i}. [{a['lang']}] {model_input(a)}" for i, (_, a) in enumerate(batch, start=1)]
    answer = llm.complete_json(system, "NEWS:\n" + "\n".join(lines), BatchLabels,
                               max_tokens=3_000)  # fmt: skip
    by_index = {item.index: item for item in answer.items}
    return {key: by_index[i] for i, (key, _) in enumerate(batch, start=1) if i in by_index}


def classify_news(
    llm: LLM,
    *,
    raw_root: Path | None,
    derived_root: Path,
    limit: int | None = None,
    keys: set[str] | None = None,
    now: dt.datetime | None = None,
) -> ClassifyResult:
    """Classify the articles that are new, changed or labelled with an older prompt
    (only ``keys``, if given: the evaluation runs on the labelled articles)."""
    system, version = prompt("classify_news")
    path = labels_path(derived_root)
    rows = load_labels(path)
    if not path.exists():
        save_labels(path, rows)  # dbt reads the file even when nothing is classified
    articles = stored_articles(raw_root)
    if keys is not None:
        articles = {k: a for k, a in articles.items() if k in keys}
    result = ClassifyResult(total=len(articles))
    pending = []
    for key, article in sorted(articles.items(), key=lambda kv: kv[1].get("published") or ""):
        row = rows.get(key)
        if row and row["input_hash"] == input_hash(article) and row["prompt_version"] == version:
            result.up_to_date += 1
        else:
            pending.append((key, article))
    pending = pending[-limit:] if limit else pending  # the newest first when limited
    stamp = (now or dt.datetime.now(dt.UTC)).isoformat(timespec="seconds")
    for start in range(0, len(pending), BATCH):
        batch = pending[start : start + BATCH]
        labels = classify_batch(llm, system, batch)
        result.missing += len(batch) - len(labels)
        for key, label in labels.items():
            rows[key] = {
                "key": key,
                "category": label.category,
                "taxa": sorted({t.strip() for t in label.taxa if t.strip()}),
                "input_hash": input_hash(articles[key]),
                "generator": llm.label,
                "prompt_version": version,
                "classified_at": stamp,
            }
            result.classified += 1
        save_labels(path, rows)  # keep progress if the quota runs out mid-way
    return result
