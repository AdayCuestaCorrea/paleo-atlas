"""Pieces of the taxon page (ALCANCE.md §11.1) computed before rendering: responsive
images, the deep-time strip, the relatives on a time axis, the study history by
decade, which events are new and the language tag of each study.

Everything here is a pure function of the page's data, so the HTML can be drawn on
the server (it works without JavaScript) and tested.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any

from paleo.site.explore import PERIODS

SRCSET_WIDTHS = (960, 1280, 1920)  # standard Wikimedia thumbnail steps
NEW_DAYS = 90  # an event is "new" for three months after it was published
_THUMB = re.compile(r"^(https://[^/]+/wikipedia/commons/thumb/\w/\w\w/[^/]+)/\d+px-([^?]+)(\?.*)?$")


def srcset(url: str | None) -> str | None:
    """The same Commons picture at 960, 1280 and 1920 px for <img srcset>; None for
    anything that is not a Commons thumbnail (PhyloPic silhouettes, originals)."""
    match = _THUMB.match(url or "")
    if not match:
        return None
    base, name = match.group(1), match.group(2)
    return ", ".join(f"{base}/{w}px-{name} {w}w" for w in SRCSET_WIDTHS)


# ------------------------------------------------------------------- deep time

TIME_WIDTH = 1000.0  # SVG units of the strip
TIME_OLDEST = 487.0  # Ma, the start of the Ordovician (the oldest period in scope)


def time_axis(max_ma: float | None, min_ma: float | None, periods: list[str]) -> dict[str, Any]:
    """The strip of the periods on a true scale with the taxon's range marked.

    ``periods`` are the keys the taxon is listed under (explore.facets): those bands
    are drawn bright, the rest faded. ``mark`` is None when the ages are unknown."""

    def x(ma: float) -> float:
        return round((TIME_OLDEST - ma) / TIME_OLDEST * TIME_WIDTH, 1)

    bands = [
        {"key": key, "en": en, "es": es, "x": x(old), "width": round(x(young) - x(old), 1),
         "active": key in periods, "labelled": x(young) - x(old) > 60}
        for key, en, es, old, young in PERIODS
    ]  # fmt: skip
    mark = None
    if max_ma is not None:
        x0, x1 = x(max_ma), x(min_ma if min_ma is not None else max_ma)
        width = max(6.0, x1 - x0)  # a short range stays visible, centred on itself
        mark = {"x": round(x0 - (width - (x1 - x0)) / 2, 1), "width": round(width, 1)}
    ticks = [{"label": f"{v:g}", "x": x(v)} for v in (252, 66)]
    return {"bands": bands, "mark": mark, "ticks": ticks, "width": TIME_WIDTH}


# -------------------------------------------------------------------- relatives

_STEPS = (1, 2, 5, 10, 20, 25, 50, 100)


def kin_rows(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The relatives of a page on a time axis: one row per genus, closest first (the
    order of fct_taxon_neighborhood), its bar from the oldest to the youngest fossil
    known, as percentages of the axis, with the axis ticks and the period bands."""
    if not rows:
        return None
    dated = [r for r in rows if r.get("first_appearance_max_ma") is not None]
    out: dict[str, Any] = {
        "clade": rows[0].get("level_clade_name"), "total": rows[0].get("level_genera"),
        "rows": [], "ticks": [], "bands": [],
    }  # fmt: skip
    if dated:
        hi = max(r["first_appearance_max_ma"] for r in dated)
        lo = min(_young(r) for r in dated)
        pad = max(2.0, (hi - lo) * 0.06)
        hi, lo = hi + pad, max(0.0, lo - pad)
        span = hi - lo

        def pos(ma: float) -> float:
            return round((hi - ma) / span * 100, 2)

        step = next((s for s in _STEPS if span / s <= 6), 100)
        v = math.ceil(lo / step) * step
        while v <= hi:
            out["ticks"].append({"ma": v, "pos": pos(v)})
            v += step
        for key, en, es, old, young in PERIODS:
            left, right = max(0.0, pos(old)), min(100.0, pos(young))
            if right > 0 and left < 100 and right > left:
                out["bands"].append(
                    {"key": key, "en": en, "es": es, "left": left, "width": round(right - left, 2)}
                )
    for r in rows:
        row = {"key": r["member_key"], "name": r["member_name"], "self": bool(r.get("is_self")),
               "from": r.get("first_appearance_max_ma"), "to": None}  # fmt: skip
        if dated and r.get("first_appearance_max_ma") is not None:
            row["to"] = _young(r)
            left, right = pos(row["from"]), pos(row["to"])
            row.update(left=left, width=round(max(0.6, right - left), 2), label_right=left > 60,
                       right=round(100 - right, 2))  # fmt: skip
        out["rows"].append(row)
    return out


def _young(r: dict[str, Any]) -> float:
    young = r.get("last_appearance_min_ma")
    return r["first_appearance_max_ma"] if young is None else young


# ---------------------------------------------------------------- study history


def is_new(event: dict[str, Any], built_on: dt.date, days: int = NEW_DAYS) -> bool:
    """A tracked event published within ``days`` of the build (the history rebuilt
    backwards is never new)."""
    date = event.get("event_date")
    if not date or event.get("origin", "tracked") != "tracked":
        return False
    return 0 <= (built_on - date).days <= days


def history_by_decade(history: dict[str, Any], built_on: dt.date) -> list[dict[str, Any]]:
    """Events per decade for the bar chart: the history backwards by decade, then the
    events tracked since the project started under the build year."""
    bars = [
        {"label": f"{decade}s", "n": len(items), "now": False}
        for decade, items in history["decades"]
    ]
    bars.sort(key=lambda b: b["label"])
    if history["recent"]:
        bars.append({"label": str(built_on.year), "n": len(history["recent"]), "now": True})
    top = max((b["n"] for b in bars), default=1)
    for b in bars:
        b["height"] = max(6, round(b["n"] / top * 100))
    return bars


def study_lang_tag(event: dict[str, Any], lang: str) -> str | None:
    """What the reader should know about a study's language before opening it.

    "lang:xx" when Crossref gives a language other than the page's; on Spanish pages
    without that, "translated" when the title shown is our translation and "original"
    when it is shown as published (language unknown). None otherwise."""
    code = (event.get("language") or "").lower()
    if code:
        return None if code == lang else f"lang:{code}"
    if lang != "es" or not event.get("title"):
        return None
    return "translated" if event.get("title_es") else "original"


# ------------------------------------------------------------------------- map


def map_viewbox(points: list[dict[str, Any]]) -> str:
    """A 2:1 view box around the finds (with a margin), or the whole world."""
    if not points:
        return "-180 -90 360 180"
    xs = [p["lon"] for p in points]
    ys = [-p["lat"] for p in points]
    x0, x1, y0, y1 = min(xs) - 12, max(xs) + 12, min(ys) - 8, max(ys) + 8
    w, h = x1 - x0, y1 - y0
    if w / h > 2:
        h = w / 2
    else:
        w = h * 2
    if w >= 360:
        return "-180 -90 360 180"
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    x = max(-180.0, min(180.0 - w, cx - w / 2))
    y = max(-90.0, min(90.0 - h, cy - h / 2))
    return " ".join(f"{v:.1f}".rstrip("0").rstrip(".") for v in (x, y, w, h))
