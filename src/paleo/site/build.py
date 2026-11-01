"""Render the static site (ES + EN) from the warehouse.

Output goes to a temporary folder that replaces ``site/_build`` only when the
whole site rendered, so a failed build never leaves a half-written site.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shutil
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from paleo.config import project_root
from paleo.site import terms
from paleo.site.data import SiteData, load, numbered_text
from paleo.site.fallback import fallback_text

LANGS = ("es", "en")
I18N_DIR = Path(__file__).parent / "i18n"
SITE_URL = os.environ.get("PALEO_SITE_URL", "https://adaycuestacorrea.github.io/paleo-atlas")

PATHS = {
    "es": {
        "home": "es/index.html",
        "taxa": "es/taxones/index.html",
        "taxon": "es/taxones/{key}.html",
        "recaps": "es/resumen/index.html",
        "recap": "es/resumen/{key}.html",
        "sources": "es/fuentes.html",
        "assess": "es/como-evaluamos.html",
        "about": "es/acerca.html",
    },
    "en": {
        "home": "en/index.html",
        "taxa": "en/taxa/index.html",
        "taxon": "en/taxa/{key}.html",
        "recaps": "en/recap/index.html",
        "recap": "en/recap/{key}.html",
        "sources": "en/sources.html",
        "assess": "en/how-we-assess.html",
        "about": "en/about.html",
    },
}
MONTHS = {
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
SECTION_ORDER = [
    "description",
    "discovery",
    "paleobiology",
    "classification",
    "time_and_habitat",
    "debate",
]


def load_i18n() -> dict[str, dict[str, str]]:
    return {lang: tomllib.loads((I18N_DIR / f"{lang}.toml").read_text("utf-8")) for lang in LANGS}


def md_inline(text: str) -> Markup:
    """Escape, then turn *italics* (models use them for scientific names) into <em>."""
    escaped = html.escape(text)
    return Markup(re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped))


def fmt_date(value: dt.date | None, lang: str, precision: str = "day") -> str:
    """Format a date with the precision we actually know ("2026", "feb 2026")."""
    if value is None:
        return ""
    month = MONTHS[lang][value.month - 1]
    if precision == "year":
        return str(value.year)
    if precision == "month":
        return f"{month} {value.year}"
    return f"{value.day} {month} {value.year}"


def iso_week(value: dt.date) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def week_label(key: str, lang: str) -> str:
    year, week = key.split("-W")
    monday = dt.date.fromisocalendar(int(year), int(week), 1)
    sunday = monday + dt.timedelta(days=6)
    span = f"{fmt_date(monday, lang)} \u2013 {fmt_date(sunday, lang)}"
    prefix = "Semana" if lang == "es" else "Week"
    return f"{prefix} {int(week)} · {span}"


@dataclass
class Page:
    lang: str
    kind: str
    key: str | None
    template: str
    context: dict[str, Any]


class SiteBuilder:
    def __init__(self, data: SiteData, base: str = "") -> None:
        self.data = data
        self.base = base.rstrip("/")
        self.i18n = load_i18n()
        root = project_root() / "site"
        self.static_dir = root / "static"
        self.env = Environment(
            loader=FileSystemLoader(root / "templates"),
            autoescape=select_autoescape(["html", "j2", "xml"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["md"] = md_inline
        self.env.globals["terms"] = terms
        self.env.globals["SECTION_ORDER"] = SECTION_ORDER

    # ------------------------------------------------------------------ urls

    def path(self, lang: str, kind: str, key: str | None = None) -> str:
        return PATHS[lang][kind].format(key=key)

    def url(self, lang: str, kind: str, key: str | None = None) -> str:
        return f"{self.base}/{self.path(lang, kind, key)}"

    def t(self, lang: str, name: str, **kwargs: Any) -> str:
        return self.i18n[lang][name].format(**kwargs)

    # ----------------------------------------------------------------- pages

    def pages(self) -> list[Page]:
        data = self.data
        events = data.all_events()
        weeks: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            weeks[iso_week(event["event_date"])].append(event)
        week_keys = sorted(weeks, reverse=True)
        new = [t for t in data.taxa if t["page_type"] == "new"]
        known = [t for t in data.taxa if t["page_type"] == "known"]
        new.sort(key=lambda t: (t.get("naming_year") or 0, t["taxon_name"]), reverse=False)
        out: list[Page] = []
        for lang in LANGS:
            common = {"latest_week": week_keys[0] if week_keys else None}
            out.append(
                Page(lang, "home", None, "index.html.j2",
                     {**common, "events": events[:12], "new": new, "known": known[:24],
                      "known_total": len(known)})
            )  # fmt: skip
            out.append(Page(lang, "taxa", None, "taxa.html.j2", {"new": new, "known": known}))
            for taxon in data.taxa:
                key = taxon["taxon_key"]
                out.append(
                    Page(lang, "taxon", key, "taxon.html.j2",
                         {"taxon": taxon, "events": data.events.get(key, []),
                          "text": numbered_text(data, key, lang),
                          "fallback": fallback_text(taxon, lang)})
                )  # fmt: skip
            out.append(
                Page(lang, "recaps", None, "recaps.html.j2",
                     {"weeks": [(k, len(weeks[k])) for k in week_keys]})
            )  # fmt: skip
            for key in week_keys:
                out.append(
                    Page(lang, "recap", key, "recap.html.j2", {"week": key, "events": weeks[key]})
                )
            for kind in ("sources", "assess", "about"):
                out.append(Page(lang, kind, None, f"{kind}.{lang}.html.j2", {}))
        return out

    def render(self, page: Page) -> str:
        lang, other = page.lang, "en" if page.lang == "es" else "es"
        template = self.env.get_template(page.template)
        return template.render(
            lang=lang,
            other=other,
            T=self.i18n[lang],
            t=lambda name, **kw: self.t(lang, name, **kw),
            url=lambda kind, key=None, lang=lang: self.url(lang, kind, key),
            alternate=self.url(other, page.kind, page.key),
            self_url=self.url(lang, page.kind, page.key),
            canonical=f"{SITE_URL}/{self.path(lang, page.kind, page.key)}",
            base=self.base,
            fmt_date=lambda d, precision="day": fmt_date(d, lang, precision),
            week_label=lambda k: week_label(k, lang),
            built_on=self.data.built_on,
            page_kind=page.kind,
            **page.context,
        )

    def build(self, out_dir: Path) -> dict[str, Any]:
        tmp = out_dir.with_name(out_dir.name + ".tmp")
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        pages = self.pages()
        urls = []
        for page in pages:
            target = tmp / self.path(page.lang, page.kind, page.key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.render(page), encoding="utf-8")
            urls.append(f"{SITE_URL}/{self.path(page.lang, page.kind, page.key)}")
        root_ctx = {"base": self.base, "T": self.i18n}
        (tmp / "index.html").write_text(
            self.env.get_template("root.html.j2").render(**root_ctx), encoding="utf-8"
        )
        (tmp / "404.html").write_text(
            self.env.get_template("404.html.j2").render(**root_ctx), encoding="utf-8"
        )
        (tmp / "sitemap.xml").write_text(
            self.env.get_template("sitemap.xml.j2").render(urls=[f"{SITE_URL}/", *urls]),
            encoding="utf-8",
        )
        shutil.copytree(self.static_dir, tmp / "static")
        (tmp / ".nojekyll").write_text("", encoding="utf-8")  # serve files as they are
        if out_dir.exists():
            shutil.rmtree(out_dir)
        tmp.rename(out_dir)
        return {
            "pages": len(pages) + 2,
            "taxa": len(self.data.taxa),
            "verified_texts": len(self.data.texts),
            "untranslated_terms": sorted(terms.UNTRANSLATED),
        }


def build_site(warehouse: Path, out_dir: Path, base: str = "") -> dict[str, Any]:
    report = SiteBuilder(load(warehouse), base=base).build(out_dir)
    report["built_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    return report


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
