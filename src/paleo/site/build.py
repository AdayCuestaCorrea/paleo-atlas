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
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from paleo.config import enabled_pages, project_root
from paleo.ingest.pbdb import scope_clades
from paleo.names import GENUS_LIKE
from paleo.site import terms, tree
from paleo.site.data import SiteData, history, load, numbered_text
from paleo.site.fallback import basic_sources, fallback_text
from paleo.site.indices import build_indices, unit_key, unit_name
from paleo.site.search import build_index

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
        "search": "es/buscar.html",
        "search_index": "es/buscar.json",
        "encyclopedia": "es/enciclopedia/index.html",
        "group_index": "es/enciclopedia/grupo/{key}.html",
        "period_index": "es/enciclopedia/epoca/{key}.html",
        "country_index": "es/enciclopedia/pais/{key}.html",
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
        "search": "en/search.html",
        "search_index": "en/search.json",
        "encyclopedia": "en/encyclopedia/index.html",
        "group_index": "en/encyclopedia/group/{key}.html",
        "period_index": "en/encyclopedia/period/{key}.html",
        "country_index": "en/encyclopedia/country/{key}.html",
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


def claim(template: str, name: str | None, other: str | None = None) -> Markup:
    """A history claim ("{name}, synonym of {other}") with both names in italics."""

    def em(value: str | None) -> str:
        return f"<em>{escape(value or '')}</em>"

    text = str(escape(template))  # a plain str: Markup.replace would escape the <em>
    return Markup(text.replace("{name}", em(name)).replace("{other}", em(other)))


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


_GENUS = GENUS_LIKE
_EPITHET = re.compile(r"[a-z]{4,}(?:us|um|is|ae|ii|ensis|icus|ianus)")
_NOT_EPITHETS = {"thus", "plus", "status", "bonus", "genus", "corpus", "campus", "virus",
                 "analysis", "basis", "axis", "this", "naris"}  # fmt: skip


def wikipedia_search(name: str, lang: str) -> str:
    """Goes straight to the article when it exists, to the search results otherwise."""
    return f"https://{lang}.wikipedia.org/wiki/Special:Search?search={quote(name)}&go=Go"


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
        self.env.globals["claim"] = claim
        self.env.globals["tree_svg"] = tree.svg
        self.env.globals["tree_periods"] = tree.tree_periods
        self.env.globals["terms"] = terms
        self.env.globals["SECTION_ORDER"] = SECTION_ORDER
        # Atlas taxa by name (and genus-only pages by genus) for links in the prose.
        self.atlas_names = {t["taxon_name"]: t["taxon_key"] for t in data.taxa}
        self.atlas_genera = {name.split(" ")[0] for name in self.atlas_names}
        self._names = re.compile(r"\b[A-Z][a-z]+(?: [a-z]+)?")
        groups = list(dict.fromkeys(c.taxon_group for c in scope_clades(enabled_only=False)))
        self.indices = build_indices(data.taxa, groups)
        self.env.globals["indices"] = self.indices
        self.env.globals["unit_name"] = unit_name
        self.env.globals["unit_key"] = unit_key

    # ----------------------------------------------------------------- prose

    def prose(self, text: str, lang: str, own_name: str | None) -> Markup:
        """Escape a sentence, italicize scientific names and link them: to their page
        in the atlas, or to Wikipedia in the page's language."""
        escaped = html.escape(text)

        def link(name: str) -> str:
            key = self.atlas_names.get(name)
            if name == own_name:
                return f"<em>{name}</em>"
            if key:
                href = self.url(lang, "taxon", key)
                return f'<a class="taxon-link" href="{href}"><em>{name}</em></a>'
            return (
                f'<a class="ext" href="{wikipedia_search(name, lang)}" rel="noopener">'
                f"<em>{name}</em></a>"
            )

        out, pos = [], 0
        for match in self._names.finditer(escaped):
            name = match.group(0)
            genus, _, epithet = name.partition(" ")
            if (
                epithet
                and name not in self.atlas_names
                and (
                    not _EPITHET.fullmatch(epithet)
                    or epithet in _NOT_EPITHETS
                    or epithet.endswith("ous")
                )
            ):
                name = genus  # "Spinosaurus was": only the genus is a name
            if genus not in self.atlas_genera and not _GENUS.fullmatch(genus):
                continue
            start = match.start()
            out += [escaped[pos:start], link(name)]
            pos = start + len(name)
        out.append(escaped[pos:])
        return Markup(re.sub(r"\*([^*]+)\*", r"<em>\1</em>", "".join(out)))

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
        # Taxa with studies this year: known pages and the encyclopedia genera that a
        # study is about (a genus page replaces the known page of that genus).
        known = [
            t for t in data.taxa if t["page_type"] != "new" and data.events.get(t["taxon_key"])
        ]
        # Each taxon cites the yearly page of its own block (§4).
        year_pages = {pg.block: pg.title(data.built_on.year) for pg in enabled_pages()}
        default_page = enabled_pages()[0].title(data.built_on.year)
        idx = self.indices
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
                          "history": history(data.events.get(key, [])),
                          "kin": data.kinship(taxon),
                          "silhouettes": data.silhouettes,
                          "gallery": data.images.get(key, []),
                          "text": numbered_text(data, key, lang),
                          "fallback": fallback_text(taxon, lang),
                          "basic_sources": basic_sources(
                              taxon, data.events.get(key, []),
                              year_pages.get(taxon.get("taxonomic_block"), default_page),
                              lang)})
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
                extra = {"gbif": data.gbif} if kind == "sources" else {}
                out.append(Page(lang, kind, None, f"{kind}.{lang}.html.j2", extra))
            out.append(Page(lang, "search", None, "search.html.j2", {}))
            out.append(Page(lang, "encyclopedia", None, "encyclopedia.html.j2", {}))
            for key, families in idx.groups.items():
                out.append(Page(lang, "group_index", key, "index_list.html.j2",
                                {"index_kind": "group", "index_key": key,
                                 "sections": list(families.items())}))  # fmt: skip
            for key, sections in idx.periods.items():
                out.append(Page(lang, "period_index", key, "index_list.html.j2",
                                {"index_kind": "period", "index_key": key,
                                 "sections": sections}))  # fmt: skip
            for key, genera in idx.countries.items():
                out.append(Page(lang, "country_index", key, "index_list.html.j2",
                                {"index_kind": "country", "index_key": key,
                                 "sections": [("", genera)]}))  # fmt: skip
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
            alternate_absolute=f"{SITE_URL}/{self.path(other, page.kind, page.key)}",
            base=self.base,
            fmt_date=lambda d, precision="day": fmt_date(d, lang, precision),
            num=lambda v: (
                (f"{v:g}".replace(".", ",") if lang == "es" else f"{v:g}") if v is not None else ""
            ),
            week_label=lambda k: week_label(k, lang),
            built_on=self.data.built_on,
            last_checked=self.data.last_checked,
            stats=self.data.stats,
            page_kind=page.kind,
            prose=lambda text: self.prose(
                text, lang, (page.context.get("taxon") or {}).get("taxon_name")
            ),
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
        for lang in LANGS:
            index = build_index(
                self.data.taxa, lang, lambda key, lang=lang: self.url(lang, "taxon", key)
            )
            (tmp / self.path(lang, "search_index")).write_text(
                json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
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
