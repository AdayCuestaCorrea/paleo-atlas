"""Group the articles that tell the same story, across outlets and languages.

Two articles are linked when they were published within ``WINDOW_DAYS`` of each other
and their similarity reaches the threshold; groups are the connected components of
those links (transitive closure, union-find). The similarity method is pluggable so
the methods can be measured against the pairs labelled by hand (paleo eval news);
the daily run uses the one chosen there, among those that run on a CPU in Actions.
Only articles the LLM did not call noise are grouped.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel

from paleo.llm import LLM
from paleo.narrative.facts import prompt
from paleo.news.classify import (
    input_hash,
    labels_path,
    load_labels,
    model_input,
    stored_articles,
)
from paleo.store import _atomic_write

WINDOW_DAYS = 5

Similarity = Callable[[Sequence[str]], np.ndarray]  # texts -> square similarity matrix


def tfidf_similarity(texts: Sequence[str]) -> np.ndarray:
    """Cosine similarity of TF-IDF vectors of character 3-5-grams (word-bounded): no
    model, robust to inflections, weak across languages."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectors = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
                              lowercase=True).fit_transform(texts)  # fmt: skip
    return cosine_similarity(vectors)


def embedding_similarity(texts: Sequence[str]) -> np.ndarray:
    """Cosine similarity of multilingual sentence embeddings (Qwen3-Embedding 0.6B on
    the local Ollama, the model of the narrative evaluation): only for evaluation,
    since Actions has no Ollama."""
    from paleo.narrative.evaluate import Embedder

    vectors = np.asarray(Embedder()(list(texts)), dtype=float)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors @ vectors.T


METHODS: dict[str, Similarity] = {"tfidf": tfidf_similarity, "embeddings": embedding_similarity}
# TF-IDF fails across languages (F1 0.31 on the 47 labelled pairs, 2026-11-07: five of
# the six same-story pairs are English-Spanish); the daily run asks the LLM instead.
METHOD, THRESHOLD = "tfidf", 0.35
PAIR_BATCH = 15
SUMMARY_CHARS = 300


class PairAnswer(BaseModel):
    index: int
    same: bool


class PairAnswers(BaseModel):
    pairs: list[PairAnswer]


def _short(article: dict[str, Any]) -> str:
    text = f"[{article['lang']}] {article['title']}"
    if article.get("summary"):
        text += " — " + article["summary"][:SUMMARY_CHARS]
    return text


def pairs_path(derived_root: Path) -> Path:
    return derived_root / "news" / "pairs.json"


def judge_pairs(
    llm: LLM,
    articles: dict[str, dict[str, Any]],
    pairs: Sequence[tuple[str, str]],
    path: Path,
) -> dict[tuple[str, str], bool]:
    """Ask the LLM whether each pair tells the same story. Answers are kept in ``path``
    with the hashes of both inputs and the prompt version, so a pair is asked once."""
    system, version = prompt("same_story")
    rows = {}
    if path.exists():
        rows = {(r["key_a"], r["key_b"]): r for r in json.loads(path.read_text("utf-8"))}

    def current(a: str, b: str) -> bool:
        row = rows.get((a, b))
        return bool(row and row["prompt_version"] == version
                    and row["hash_a"] == input_hash(articles[a])
                    and row["hash_b"] == input_hash(articles[b]))  # fmt: skip

    pending = [(a, b) for a, b in pairs if not current(a, b)]
    for start in range(0, len(pending), PAIR_BATCH):
        batch = pending[start : start + PAIR_BATCH]
        user = "PAIRS:\n" + "\n".join(
            f"{i}. A: {_short(articles[a])}\n   B: {_short(articles[b])}"
            for i, (a, b) in enumerate(batch, start=1)
        )
        answer = llm.complete_json(system, user, PairAnswers, max_tokens=2_000)
        by_index = {p.index: p.same for p in answer.pairs}
        for i, (a, b) in enumerate(batch, start=1):
            if i in by_index:
                rows[(a, b)] = {"key_a": a, "key_b": b, "same": by_index[i],
                                "hash_a": input_hash(articles[a]),
                                "hash_b": input_hash(articles[b]),
                                "generator": llm.label, "prompt_version": version}  # fmt: skip
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, json.dumps([rows[k] for k in sorted(rows)], indent=1) + "\n")
    return {(a, b): rows[(a, b)]["same"] for a, b in pairs if (a, b) in rows}


def candidate_pairs(
    keys: Sequence[str], articles: dict[str, dict[str, Any]], window_days: int = WINDOW_DAYS
) -> list[tuple[str, str]]:
    """Every pair of articles published within the window (keys sorted)."""
    ordered = sorted(keys)
    out = []
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            ta, tb = published(articles[a]), published(articles[b])
            if ta and tb and abs((ta - tb).total_seconds()) <= window_days * 86_400:
                out.append((a, b))
    return out


def group_news_llm(llm: LLM, *, raw_root: Path | None, derived_root: Path) -> dict[str, int]:
    """Group the articles that are not noise by asking the LLM about each candidate
    pair (only pairs not asked before), and save key -> group to derived/news."""
    articles = stored_articles(raw_root)
    labels = load_labels(labels_path(derived_root))
    keys = sorted(k for k in articles if labels.get(k, {}).get("category") not in (None, "noise"))
    candidates = candidate_pairs(keys, articles)
    answers = judge_pairs(llm, articles, candidates, pairs_path(derived_root))
    same = [(a, b, 1.0) for (a, b), yes in answers.items() if yes]
    return _save_groups(keys, same, derived_root, method=llm.label, threshold=None,
                        candidates=len(candidates))  # fmt: skip


def published(article: dict[str, Any]) -> dt.datetime | None:
    value = article.get("published")
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def links(
    keys: Sequence[str],
    articles: dict[str, dict[str, Any]],
    similarity: np.ndarray,
    threshold: float,
    window_days: int = WINDOW_DAYS,
) -> list[tuple[str, str, float]]:
    """Pairs (a, b, similarity) within the window that reach the threshold."""
    out = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = published(articles[keys[i]]), published(articles[keys[j]])
            if a is None or b is None or abs((a - b).total_seconds()) > window_days * 86_400:
                continue
            if similarity[i, j] >= threshold:
                out.append((keys[i], keys[j], float(similarity[i, j])))
    return out


def groups(keys: Sequence[str], pairs: Sequence[tuple[str, str, float]]) -> dict[str, str]:
    """Key -> group id (the group's smallest key), by union-find over the pairs."""
    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for a, b, _ in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return {k: find(k) for k in keys}


def clusters_path(derived_root: Path) -> Path:
    return derived_root / "news" / "groups.json"


def group_news(
    *,
    raw_root: Path | None,
    derived_root: Path,
    similarity: Similarity,
    threshold: float,
    method: str,
) -> dict[str, int]:
    """Group the articles that are not noise and save key -> group to derived/news."""
    articles = stored_articles(raw_root)
    labels = load_labels(labels_path(derived_root))
    keys = sorted(k for k in articles if labels.get(k, {}).get("category") not in (None, "noise"))
    texts = [model_input(articles[k]) for k in keys]
    matrix = similarity(texts) if keys else np.zeros((0, 0))
    found = links(keys, articles, matrix, threshold)
    return _save_groups(keys, found, derived_root, method=method, threshold=threshold,
                        candidates=None)  # fmt: skip


def _save_groups(
    keys: Sequence[str],
    found: Sequence[tuple[str, str, float]],
    derived_root: Path,
    *,
    method: str,
    threshold: float | None,
    candidates: int | None,
) -> dict[str, int]:
    assigned = groups(keys, found)
    rows = [{"key": k, "group": g, "method": method, "threshold": threshold}
            for k, g in sorted(assigned.items())]  # fmt: skip
    path = clusters_path(derived_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(rows, indent=1) + "\n")
    sizes: dict[str, int] = {}
    for g in assigned.values():
        sizes[g] = sizes.get(g, 0) + 1
    return {"articles": len(keys), "candidates": candidates, "links": len(found),
            "groups": len(sizes), "grouped": sum(n for n in sizes.values() if n > 1)}  # fmt: skip
