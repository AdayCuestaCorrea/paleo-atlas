"""The data status page (ALCANCE.md §11): pipeline runs, data quality, coverage and
source freshness, computed from the warehouse before rendering (the page works
without JavaScript; the charts are SVG drawn here).

Runs come from the run log (stg_pipeline__runs); only finished runs are shown, since
the site is built before the current run is finished.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

SCHEDULE = dt.time(6, 23)  # cron of the daily run (pipeline.yml)

# Step groups of a run, by step name (pipeline.yml), in the order they run.
STEP_GROUPS = [
    ("prep", re.compile(r"Set up|checkout|setup-uv|Install|Check out|Anything new", re.I)),
    ("ingest", re.compile(r"Ingest", re.I)),
    ("groq", re.compile(r"Groq", re.I)),
    ("dbt", re.compile(r"dbt", re.I)),
    ("site", re.compile(r"website", re.I)),
]
DIFF_KEYS = ["taxa_new", "texts_en", "texts_es", "events", "studies", "gallery_images"]


def _json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _ts(value: Any) -> dt.datetime | None:
    if value is None or isinstance(value, dt.datetime):
        return value.astimezone(dt.UTC) if value else None
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(dt.UTC)


def finished(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Finished runs, oldest first, with their JSON columns decoded."""
    out = []
    for r in runs:
        if r.get("status") == "running" or not r.get("finished_at"):
            continue
        run = dict(r)
        for k in ("steps", "summary", "dbt", "sources_changed", "changes_since_previous",
                  "wikipedia_new_revisions"):  # fmt: skip
            run[k] = _json(run.get(k))
        run["started_at"], run["finished_at"] = _ts(r["started_at"]), _ts(r["finished_at"])
        out.append(run)
    return sorted(out, key=lambda r: r["started_at"])


def step_group(name: str) -> str | None:
    """The first group whose pattern matches a step name (a step counts only once)."""
    return next((key for key, pattern in STEP_GROUPS if pattern.search(name)), None)


def runs_view(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The finished runs, newest first: wall-clock time, seconds per step group and the
    part the log does not break down, the day's source changes (shown once, on the
    day's latest run: the log counts them per day), the totals' changes and dbt."""
    out, seen_days = [], set()
    for r in reversed(finished(runs)):
        steps = r.get("steps") or []
        group_of = {id(s): step_group(s["name"]) for s in steps}
        groups = []
        for key, _ in STEP_GROUPS:
            mine = [s for s in steps if group_of[id(s)] == key]
            seconds = sum(s["seconds"] for s in mine)
            if seconds:
                groups.append({"key": key, "seconds": seconds,
                               "partial": any(s.get("partial") for s in mine)})  # fmt: skip
        wall = int((r["finished_at"] - r["started_at"]).total_seconds())
        known = sum(g["seconds"] for g in groups)
        total = max(wall, known)
        day = r["started_at"].date()
        first_of_day = day not in seen_days
        seen_days.add(day)
        changes = r.get("changes_since_previous") or {}
        dbt = r.get("dbt") or {}
        counts = dbt.get("counts") or {}
        out.append({
            "started_at": r["started_at"], "trigger": r["trigger"], "status": r["status"],
            "changed": bool(r.get("changed")), "seconds": total, "groups": groups,
            "unsplit": total - known if steps else total,
            "sources": (r.get("sources_changed") or {}) if first_of_day else {},
            "wikipedia": len(r.get("wikipedia_new_revisions") or []) if first_of_day else 0,
            "diffs": [(k, changes[k]) for k in DIFF_KEYS if changes.get(k)],
            "warnings": counts.get("warn", 0),
            "errors": sum(counts.get(k, 0) for k in ("error", "fail", "runtime error")),
        })  # fmt: skip
    return out


def calendar(runs: list[dict[str, Any]], today: dt.date, days: int = 30) -> list[dict[str, Any]]:
    """One square per day, oldest first: no run, a run that found changes, runs that
    found nothing new, or a failed run."""
    by_day: dict[dt.date, list[dict[str, Any]]] = {}
    for r in finished(runs):
        by_day.setdefault(r["started_at"].date(), []).append(r)
    out = []
    for i in range(days - 1, -1, -1):
        day = today - dt.timedelta(days=i)
        rs = by_day.get(day, [])
        state = (
            "none" if not rs
            else "failed" if any(r["status"] != "ok" for r in rs)
            else "changed" if any(r.get("changed") for r in rs)
            else "unchanged"
        )  # fmt: skip
        out.append({"day": day, "state": state, "runs": len(rs)})
    return out


def schedule_delay(runs: list[dict[str, Any]]) -> tuple[int, int] | None:
    """Fewest and most minutes the scheduled runs started after their 06:23 UTC cron."""
    delays = []
    for r in finished(runs):
        if r["trigger"] != "schedule":
            continue
        due = dt.datetime.combine(r["started_at"].date(), SCHEDULE, tzinfo=dt.UTC)
        delays.append(int((r["started_at"] - due).total_seconds() // 60))
    return (min(delays), max(delays)) if delays else None


def texts_by_day(texts: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    """Verified narrative pages, cumulative per day and language, every day of the range
    (a day without new pages keeps the total)."""
    per: dict[dt.date, dict[str, int]] = {}
    for (_, lang), t in texts.items():
        when = t.get("generated_at")
        if not when:
            continue
        day = (
            when.date() if isinstance(when, dt.datetime) else dt.date.fromisoformat(str(when)[:10])
        )
        per.setdefault(day, {"en": 0, "es": 0})[lang] = per.get(day, {}).get(lang, 0) + 1
    if not per:
        return []
    out, total = [], {"en": 0, "es": 0}
    day, last = min(per), max(per)
    while day <= last:
        for lang in total:
            total[lang] += per.get(day, {}).get(lang, 0)
        out.append({"day": day, **total})
        day += dt.timedelta(days=1)
    return out


def freshness(rows: list[dict[str, Any]], today: dt.date) -> list[dict[str, Any]]:
    """Each source with the days since its last check and whether that is within its
    rhythm (a source never checked is late)."""
    out = []
    for r in rows:
        checked = r.get("last_checked")
        age = (today - checked).days if checked else None
        out.append({**r, "age": age, "fresh": age is not None and age <= r["every_days"]})
    return out


def overall(run: dict[str, Any] | None, tests: dict[str, Any] | None, sources: list[dict]) -> bool:
    """All in order: the last finished run was fine, no data test failed and no source
    is late."""
    errors = sum(
        v for kind in (tests or {}).values() for k, v in kind.items() if k in ("error", "fail")
    )
    return bool(run and run["status"] == "ok" and not errors and all(s["fresh"] for s in sources))


# --------------------------------------------------------------------- SVG charts

W = 340  # width of every chart, in SVG units (about its size on screen, so text stays legible)


def bar_chart(view: list[dict[str, Any]], height: int = 190, last: int = 10) -> dict[str, Any]:
    """Stacked bars of the latest runs, oldest on the left: one segment per step group
    and a grey one for the time the log does not break down."""
    runs = list(reversed(view[:last]))
    left, right, top, bottom = 34, 4, 10, 30
    top_value = max([r["seconds"] for r in runs] + [1])
    step = (W - left - right) / max(1, len(runs))

    def h(v: float) -> float:
        return round((height - top - bottom) * v / top_value, 1)

    bars = []
    for i, r in enumerate(runs):
        x, w = round(left + i * step + step * 0.18, 1), round(step * 0.64, 1)
        base, segments = height - bottom, []
        parts = [(g["key"], g["seconds"]) for g in r["groups"]]
        if r["unsplit"] > 2:
            parts.append(("unsplit", r["unsplit"]))
        for key, seconds in parts:
            base -= h(seconds)
            segments.append({"key": key, "y": round(base, 1), "h": h(seconds), "seconds": seconds})
        bars.append({"x": x, "w": w, "cx": round(x + w / 2, 1), "segments": segments, "run": r})
    grid = [{"y": round(height - bottom - h(top_value * f), 1), "label": round(top_value * f)}
            for f in (0, 0.5, 1)]  # fmt: skip
    return {"width": W, "height": height, "bars": bars, "grid": grid, "axis_y": height - 16}


def line_chart(points: list[dict[str, Any]], keys=("en", "es"), height: int = 170) -> dict:
    """Lines of the cumulative verified pages, with end labels that never overlap."""
    left, right, top, bottom = 34, 52, 12, 26
    top_value = max([p[k] for p in points for k in keys] + [1])

    def x(i: int) -> float:
        return round(
            left + (i / (len(points) - 1) if len(points) > 1 else 0) * (W - left - right), 1
        )

    def y(v: float) -> float:
        return round(height - bottom - v / top_value * (height - top - bottom), 1)

    lines, placed = [], []
    for key in keys:
        coords = [(x(i), y(p[key])) for i, p in enumerate(points)]
        label_y = coords[-1][1] + 4 if coords else 0
        for other in placed:  # keep end labels 14 units apart
            if abs(other - label_y) < 14:
                label_y = other + (14 if label_y >= other else -14)
        placed.append(label_y)
        lines.append({"key": key, "path": "".join(f"{'L' if i else 'M'}{cx},{cy}"
                                                  for i, (cx, cy) in enumerate(coords)),
                      "dots": coords, "value": points[-1][key] if points else 0,
                      "label_x": round(W - right + 6, 1),
                      "label_y": round(label_y, 1)})  # fmt: skip
    grid = [{"y": y(top_value * f), "label": round(top_value * f)} for f in (0, 0.5, 1)]
    days = [{"x": x(i), "day": p["day"]} for i, p in enumerate(points)]
    # thin the day labels so they never crowd (at most ~6)
    every = -(-len(days) // 6)
    return {"width": W, "height": height, "lines": lines, "grid": grid,
            "days": [d for i, d in enumerate(days) if i % every == 0 or i == len(days) - 1],
            "axis_y": height - 8}  # fmt: skip
