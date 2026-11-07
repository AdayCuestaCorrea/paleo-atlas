"""Paleontology news in the website (Phase 5): stories built from fct_news.

A story is the articles that tell the same thing (fct_news.story_key, judged by the
LLM); the one in the page's language is shown first and the others are listed as
"also in". Noise never reaches the website. Headlines and summaries are the outlets'
own, unmodified, always with the outlet's name and a link (their licences ask for it).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any

CATEGORIES = ("new_species", "research", "revision")


def _day(value: Any) -> dt.date | None:
    if value is None:
        return None
    return value.date() if isinstance(value, dt.datetime) else value


def stories(rows: list[dict[str, Any]], lang: str) -> list[dict[str, Any]]:
    """The stories, newest first: main article (page language first), the others, the
    date of the first article, the category and the taxon pages they name."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("category") in CATEGORIES:
            groups[r.get("story_key") or r["news_key"]].append(r)
    out = []
    for key, items in groups.items():
        items = sorted(items, key=lambda r: (r["lang"] != lang, -_ts(r)))
        main = items[0]
        taxa = list(dict.fromkeys(k for r in items for k in (r.get("taxon_keys") or [])))
        days = [d for d in (_day(r.get("published_at")) for r in items) if d]
        out.append({
            "key": key, "main": main, "others": items[1:],
            "date": min(days) if days else None, "category": main["category"],
            "taxa": taxa, "langs": sorted({r["lang"] for r in items}),
        })  # fmt: skip
    return sorted(out, key=lambda s: (s["date"] or dt.date.min, s["key"]), reverse=True)


def _ts(row: dict[str, Any]) -> float:
    value = row.get("published_at")
    return value.timestamp() if isinstance(value, dt.datetime) else 0.0


def by_taxon(all_stories: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in all_stories:
        for key in s["taxa"]:
            out[key].append(s)
    return out
