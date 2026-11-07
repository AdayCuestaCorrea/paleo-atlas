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

from paleo.news.classify import labels_path, load_labels, model_input, stored_articles
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
# Chosen by paleo eval news on the labelled pairs (eval/reports/*-news.md); provisional
# until those labels exist.
METHOD, THRESHOLD = "tfidf", 0.35


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
    assigned = groups(keys, found)
    rows = [{"key": k, "group": g, "method": method, "threshold": threshold}
            for k, g in sorted(assigned.items())]  # fmt: skip
    path = clusters_path(derived_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(rows, indent=1) + "\n")
    sizes: dict[str, int] = {}
    for g in assigned.values():
        sizes[g] = sizes.get(g, 0) + 1
    return {"articles": len(keys), "links": len(found), "groups": len(sizes),
            "grouped": sum(n for n in sizes.values() if n > 1)}  # fmt: skip
