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
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from paleo.config import enabled_pages, get_paths, project_root
from paleo.ingest.pbdb import scope_clades
from paleo.names import GENUS_LIKE
from paleo.site import compare, explore, news, status, taxon_page, terms
from paleo.site.data import SiteData, history, load, numbered_text
from paleo.site.fallback import basic_sources, fallback_text
from paleo.site.glossary import Glossary
from paleo.site.indices import build_indices, unit_key, unit_name
from paleo.site.search import build_index, card_meta

LANGS = ("es", "en")
HOME_CARDS = 12  # cards the home page draws before the explorer's JS takes over
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
        "status": "es/estado.html",
        "glossary": "es/glosario.html",
        "news": "es/noticias.html",
        "compare": "es/comparador.html",
        "compare_index": "es/comparar.json",
        "search_index": "es/buscar.json",
        "explore_index": "es/explorar.json",
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
        "status": "en/status.html",
        "glossary": "en/glossary.html",
        "news": "en/news.html",
        "compare": "en/size.html",
        "compare_index": "en/compare.json",
        "search_index": "en/search.json",
        "explore_index": "en/explore.json",
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
    "curiosities",
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


def fmt_count(n: int, lang: str) -> str:
    """A whole number as each language writes it: 4890 and 10 252 (RAE: no separator
    with four digits, a narrow space from five), 4,890 and 10,252 in English."""
    if lang == "en":
        return f"{n:,}"
    return f"{n:,}".replace(",", "\u202f") if n >= 10000 else str(n)


def fmt_date(value: dt.date | None, lang: str, precision: str = "day") -> str:
    """Format a date with the precision we actually know ("2026", "feb 2026")."""
    if value is None:
        return ""
    month = MONTHS[lang][value.month - 1]
    if precision == "year":
        return str(value.year)
    if precision == "month":
        return f"{month} {value.year}"
    if precision == "short":  # day and month, for lists of this year's news
        return f"{value.day} {month}"
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
        # Taxon page pieces (taxon_page.py), computed on the server so pages work
        # without JavaScript.
        for fn in (
            taxon_page.srcset,
            taxon_page.time_axis,
            taxon_page.kin_rows,
            taxon_page.map_viewbox,
            taxon_page.study_lang_tag,
            explore.facets,
        ):
            self.env.globals[fn.__name__] = fn
        self.env.globals["history_by_decade"] = lambda h: taxon_page.history_by_decade(
            h, data.built_on
        )
        self.env.tests["is_new"] = lambda e: taxon_page.is_new(e, data.built_on)
        self.env.globals["terms"] = terms
        self.env.globals["size_range"] = lambda s, lang: compare.fmt_range(
            s["min_m"], s["max_m"], s["qualifier"], lang
        )
        self.env.globals["size_phrase"] = lambda s, lang: compare.phrase(
            s["min_m"], s["max_m"], lang
        )
        self.env.globals["fmt_len"] = compare.fmt_len
        self.env.globals["compare_hash"] = compare.HASH
        self.env.globals["thumb"] = explore.thumb
        self.env.globals["SECTION_ORDER"] = SECTION_ORDER
        # Atlas taxa by name (and genus-only pages by genus) for links in the prose.
        # A species folded into its genus page links there.
        self.atlas_names = {r["subject_name"]: r["to_key"] for r in data.redirects} | {
            t["taxon_name"]: t["taxon_key"] for t in data.taxa
        }
        self.atlas_genera = {name.split(" ")[0] for name in self.atlas_names}
        self._names = re.compile(r"\b[A-Z][a-z]+(?: [a-z]+)?")
        clades = scope_clades(enabled_only=False)
        groups = list(dict.fromkeys(c.taxon_group for c in clades))
        self.groups = groups
        # Groups under their block (§4), in the order of the scope seed.
        self.blocks: dict[str, list[str]] = {}
        for c in clades:
            if c.taxon_group not in self.blocks.setdefault(c.block, []):
                self.blocks[c.block].append(c.taxon_group)
        self.indices = build_indices(data.taxa, groups)
        self.env.globals["indices"] = self.indices
        self.env.globals["unit_name"] = unit_name
        self.env.globals["unit_key"] = unit_key
        # Glossary per language (§12.2) and, while a page renders, what its prose marked
        # and linked: the glossary terms and the taxon pages its popovers need.
        self.glossaries = {lang: Glossary(data.glossary, lang, self.url(lang, "glossary"))
                           for lang in ("es", "en")}  # fmt: skip
        self.taxa_by_key = {t["taxon_key"]: t for t in data.taxa}
        self.env.globals["taxa_by_key"] = self.taxa_by_key
        self._marked: dict[str, set[str]] | None = None

    # ----------------------------------------------------------------- prose

    def prose(self, text: str, lang: str, own_name: str | None, links: bool = True) -> Markup:
        """Escape a sentence, italicize scientific names and link them: to their page
        in the atlas, or to Wikipedia in the page's language (only italics when
        ``links`` is false, e.g. inside a link)."""
        escaped = html.escape(text)

        def link(name: str) -> str:
            key = self.atlas_names.get(name)
            if name == own_name or not links:
                return f"<em>{name}</em>"
            if key:
                if self._marked is not None:
                    self._marked["taxa"].add(key)
                href = self.url(lang, "taxon", key)
                title = html.escape(self.t(lang, "link_taxon", taxon=name), quote=True)
                return f'<a class="taxon-link" href="{href}" title="{title}"><em>{name}</em></a>'
            title = html.escape(self.t(lang, "link_wikipedia", taxon=name), quote=True)
            return (
                f'<a class="ext" href="{wikipedia_search(name, lang)}" rel="noopener" '
                f'title="{title}"><em>{name}</em></a>'
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
        if links and self._marked is not None and self.glossaries[lang]:
            # glossary terms in the plain text only (never inside a name's link or <em>)
            out = [self.glossaries[lang].mark(seg, self._marked["glossary"]) if i % 2 == 0
                   and "*" not in seg else seg for i, seg in enumerate(out)]  # fmt: skip
        return Markup(re.sub(r"\*([^*]+)\*", r"<em>\1</em>", "".join(out)))

    # ------------------------------------------------------------------ urls

    def path(self, lang: str, kind: str, key: str | None = None) -> str:
        return PATHS[lang][kind].format(key=key)

    def url(self, lang: str, kind: str, key: str | None = None) -> str:
        return f"{self.base}/{self.path(lang, kind, key)}"

    def t(self, lang: str, name: str, **kwargs: Any) -> str:
        return self.i18n[lang][name].format(**kwargs)

    # -------------------------------------------------------------- explorer

    @cached_property
    def explore_entries(self) -> list[dict[str, Any]]:
        data = self.data
        curiosities = {
            k for (k, lang) in data.texts
            if lang == "es" and any(
                s["section"] == "curiosities" and s["sentences"]
                for s in data.texts[(k, lang)]["sections"]
            )
        }  # fmt: skip
        return explore.explore_entries(
            data.taxa, groups=self.groups, curiosities=curiosities,
            ranks=explore.new_order(data.taxa, data.all_events()),
        )  # fmt: skip

    def home_context(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        data = self.data
        entries = self.explore_entries
        new = sorted((e for e in entries if e["flags"] & explore.NEW), key=lambda e: e["rank"])
        counts = explore.initial_counts(entries)
        # Every country on the map, biggest first so the small ones are drawn on top.
        totals = Counter(c for e in entries for c in e["countries"] if c in data.country_centroids)
        countries = sorted(totals, key=lambda c: (-totals[c], c))
        return {
            "slides": explore.pick_curiosities(data.taxa, data.texts, data.built_on),
            "events": events[:6],
            "blocks": self.blocks,
            "group_pictures": explore.group_pictures(data.taxa, data.texts),
            "periods": explore.PERIODS,
            "counts": counts,
            "first_new": [e["taxon"] for e in new[:HOME_CARDS]],
            "new_total": len(new),
            "pages_total": len(entries),
            "map_countries": [(c, *data.country_centroids[c]) for c in countries],
            # A detailed map (1:50m) for the zoomed in home map, loaded on the first zoom.
            "map_detail": "world-50m.svg" if (self.static_dir / "world-50m.svg").exists() else None,
            "period_symbols": explore.PERIOD_SYMBOLS,
        }

    # ----------------------------------------------------------- data status

    def status_context(self) -> dict[str, Any]:
        """Everything the data status page shows (status.py)."""
        from paleo.report import dbt_issues

        data = self.data
        view = status.runs_view(data.runs)
        runs = status.finished(data.runs)
        # The dbt results of this very build when present (CI runs dbt just before the
        # site); otherwise those logged by the last finished run.
        dbt = dbt_issues(project_root() / "dbt" / "target" / "run_results.json")
        if dbt is None and runs:
            dbt = runs[-1].get("dbt")
        tests = (dbt or {}).get("tests") or {"data": (dbt or {}).get("counts", {}), "unit": {}}
        sources = status.freshness(data.freshness, data.built_on)
        texts = status.texts_by_day(data.texts)
        new = [t for t in data.taxa if t["page_type"] == "new"]
        images = Counter(
            f"{t.get('image_source') or 'none'}/{t.get('image_level') or 'none'}" for t in data.taxa
        )
        events = Counter(e["event_type"] for evs in data.events.values() for e in evs)
        return {
            "last_run": runs[-1] if runs else None,
            "ok": status.overall(runs[-1] if runs else None, tests, sources),
            "view": view,
            "bars": status.bar_chart(view) if view else None,
            "calendar": status.calendar(data.runs, data.built_on),
            "delay": status.schedule_delay(data.runs),
            "texts": status.line_chart(texts) if texts else None,
            "texts_total": texts[-1] if texts else {"en": 0, "es": 0},
            "tests": tests,
            "issues": [i for i in (dbt or {}).get("issues", []) if i["status"] == "warn"],
            "errors": [i for i in (dbt or {}).get("issues", []) if i["status"] != "warn"],
            "sources": sources,
            "pbdb_new": (sum(1 for t in new if t.get("pbdb_has_taxon")), len(new)),
            "images": images.most_common(),
            "image_total": sum(images.values()),
            "events_by_type": events.most_common(),
            "studies": (data.stats or {}).get("studies", 0)
            + (data.stats or {}).get("unchecked_studies", 0),
            "event_total": sum(events.values()),
            "taxa_total": len(data.taxa),
        }

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
        home = self.home_context(events)
        status_ctx = self.status_context()
        for lang in LANGS:
            # News stories (Phase 5): the page language's article first in each story.
            stories = news.stories(data.news, lang)
            media_of = news.by_taxon(stories)
            media_weeks: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for st in stories:
                if st["date"]:
                    media_weeks[iso_week(st["date"])].append(st)
            common = {"latest_week": week_keys[0] if week_keys else None}
            out.append(Page(lang, "home", None, "index.html.j2",
                            {**common, **home, "media": stories[:6]}))  # fmt: skip
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
                          "media": media_of.get(key, [])[:3],
                          "size": self.drawable_size(key),
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
                    Page(
                        lang,
                        "recap",
                        key,
                        "recap.html.j2",
                        {"week": key, "events": weeks[key], "media": media_weeks.get(key, [])},
                    )
                )
            out.append(Page(lang, "status", None, "status.html.j2", status_ctx))
            out.append(Page(lang, "news", None, "news.html.j2", {
                "stories": stories, "news_categories": Counter(st["category"] for st in stories),
            }))  # fmt: skip
            entries = self.glossaries[lang].entries()
            out.append(Page(lang, "glossary", None, "glossary.html.j2", {
                "entries": entries,
                "letters": list(dict.fromkeys(e["letter"] for e in entries)),
                "categories": Counter(e["category"] for e in entries),
            }))  # fmt: skip
            for kind in ("sources", "assess", "about"):
                extra = {"gbif": data.gbif} if kind == "sources" else {}
                out.append(Page(lang, kind, None, f"{kind}.{lang}.html.j2", extra))
            out.append(Page(lang, "search", None, "search.html.j2", {}))
            out.append(Page(lang, "compare", None, "compare.html.j2", {
                "compare_count": sum(1 for s in data.sizes.values() if s.get("in_comparator")),
            }))  # fmt: skip
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

    @cached_property
    def silhouettes(self) -> set[str]:
        """Uuids of the silhouettes the site serves (clean copies, paleo sizes
        silhouettes): PhyloPic's host sends no CORS headers, so masks need our own."""
        folder = get_paths().data / "derived" / "silhouettes"
        return {p.stem for p in folder.glob("*.svg")} if folder.exists() else set()

    def drawable_size(self, key: str) -> dict[str, Any] | None:
        """The taxon's size for the card, if the comparator can draw it."""
        size = self.data.sizes.get(key)
        if size and size.get("in_comparator") and size.get("silhouette_uuid") in self.silhouettes:
            sil = compare.sil_url(f"{self.base}/static", size["silhouette_uuid"])
            return {**size, "sil_url": sil}
        return None

    def render(self, page: Page) -> str:
        """The page's HTML. On taxon pages the prose marks glossary terms and links
        taxa; the popovers' data (definitions, previews) goes at the end of the page."""
        self._marked = {"glossary": set(), "taxa": set()} if page.kind == "taxon" else None
        try:
            out = self._render(page)
            marked = self._marked
        finally:
            self._marked = None
        if marked and (marked["glossary"] or marked["taxa"]):
            out = out.replace("</body>", self.popover_data(page.lang, marked) + "</body>", 1)
        return out

    def popover_data(self, lang: str, marked: dict[str, set[str]]) -> str:
        """JSON for glossary.js: definitions of the marked terms (and of the terms they
        use) and a preview of every linked taxon page."""
        previews = {}
        for key in sorted(marked["taxa"]):
            t = self.taxa_by_key.get(key)
            if t is None:
                continue
            previews[key] = {
                "name": t["taxon_name"], "meta": card_meta(t, lang),
                "img": explore.thumb(t.get("image_url")),  # card width: Commons serves fixed ones
                "silhouette": t.get("image_source") == "phylopic",
            }  # fmt: skip
        data = {
            "glossary": self.glossaries[lang].page_data(marked["glossary"]),
            "previews": previews,
            "labels": {k: self.i18n[lang][k] for k in (
                "gl_source", "gl_see", "gl_also")},
        }  # fmt: skip
        payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        return (f'<script type="application/json" id="page-data">{payload}</script>\n'
                f'<script src="{self.base}/static/glossary.js" defer></script>\n')  # fmt: skip

    def _render(self, page: Page) -> str:
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
            count=lambda n: fmt_count(n, lang),
            card_meta=lambda taxon: card_meta(taxon, lang),
            built_on=self.data.built_on,
            last_checked=self.data.last_checked,
            stats=self.data.stats,
            page_kind=page.kind,
            prose=lambda text, links=True: self.prose(
                text, lang, (page.context.get("taxon") or {}).get("taxon_name"), links
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
        # Moved pages: a small redirect at the old URL (not in the sitemap or search).
        redirect = self.env.get_template("redirect.html.j2")
        for r in self.data.redirects:
            for lang in LANGS:
                other = "en" if lang == "es" else "es"
                target = tmp / self.path(lang, "taxon", r["from_key"])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    redirect.render(
                        lang=lang, T=self.i18n[lang], name=r["subject_name"],
                        to=self.url(lang, "taxon", r["to_key"]),
                        canonical=f"{SITE_URL}/{self.path(lang, 'taxon', r['to_key'])}",
                        alternate=self.url(other, "taxon", r["from_key"]), other=other,
                    ),
                    encoding="utf-8",
                )  # fmt: skip
        for lang in LANGS:
            index = build_index(
                self.data.taxa, lang, lambda key, lang=lang: self.url(lang, "taxon", key)
            )
            (tmp / self.path(lang, "search_index")).write_text(
                json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
            explorer = explore.build_explore(
                self.explore_entries, lang, lambda key, lang=lang: self.url(lang, "taxon", key),
                groups=self.groups, centroids=self.data.country_centroids,
            )  # fmt: skip
            (tmp / self.path(lang, "explore_index")).write_text(
                json.dumps(explorer, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
            index = compare.build_compare(
                self.data.sizes, self.data.refs,
                {t["taxon_key"]: t["taxon_name"] for t in self.data.taxa}, lang,
                lambda key, lang=lang: self.url(lang, "taxon", key),
                f"{self.base}/static", self.i18n[lang], self.silhouettes,
            )  # fmt: skip
            (tmp / self.path(lang, "compare_index")).write_text(
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
        sil_out = tmp / "static" / "sil"
        sil_out.mkdir(exist_ok=True)
        used = {s["silhouette_uuid"] for s in self.data.sizes.values()} | {
            r["phylopic_uuid"] for r in self.data.refs if r.get("phylopic_uuid")
        }
        for uuid in sorted(used & self.silhouettes):
            shutil.copy2(get_paths().data / "derived" / "silhouettes" / f"{uuid}.svg", sil_out)
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
