"""Checks on the built site, run in CI before publishing (ALCANCE.md §16).

* every internal link, image, stylesheet and script points to an existing file;
* every page declares its counterpart in the other language (hreflang link, which
  the broken-link check then follows);
* no taxon page is an orphan: some other page links to it;
* every image in a figure (main image and gallery) has a credit with its license;
* HTML tags are balanced;
* the search index lists every taxon page.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
}  # fmt: skip


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.anchors: list[str] = []  # <a href> links, not to the same page in the other language
        self.alternates: list[str] = []
        self.redirect = False  # <meta http-equiv="refresh">: a moved page
        self.stack: list[str] = []
        self.unbalanced: list[str] = []
        self.hero_images = 0
        self.figcaption_text = ""
        self._in_figcaption = False
        self.figures: list[tuple[bool, str]] = []  # (has an image, caption text)
        self._figure: list[Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        for name in ("href", "src"):
            if a.get(name):
                self.refs.append(a[name] or "")
        if tag == "a" and a.get("href") and not a.get("hreflang"):
            self.anchors.append(a["href"] or "")
        if tag == "link" and a.get("rel") == "alternate" and a.get("href"):
            self.alternates.append(a["href"] or "")
        if tag == "meta" and (a.get("http-equiv") or "").lower() == "refresh":
            self.redirect = True
        if tag == "img" and "pic--hero" in (a.get("class") or ""):
            self.hero_images += 1
        if tag == "figcaption":
            self._in_figcaption = True
        if tag == "figure":
            self._figure = [False, ""]
        if tag == "img" and a.get("src") and self._figure is not None:
            self._figure[0] = True
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "figcaption":
            self._in_figcaption = False
        if tag == "figure" and self._figure is not None:
            self.figures.append((self._figure[0], self._figure[1]))
            self._figure = None
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.unbalanced.append(tag)

    def handle_data(self, data: str) -> None:
        if self._in_figcaption:
            self.figcaption_text += data
            if self._figure is not None:
                self._figure[1] += data


@dataclass
class CheckReport:
    pages: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def _target(ref: str, base: str, root: Path, page: Path) -> Path | None:
    """Local file a reference points to, or None for external links. Absolute URLs
    of the site itself (canonical, hreflang) are checked as local files too."""
    from paleo.site.build import SITE_URL

    if ref.startswith(SITE_URL + "/"):
        return root / ref[len(SITE_URL) + 1 :].split("#")[0]
    parsed = urlparse(ref)
    if parsed.scheme or ref.startswith(("mailto:", "#", "//")):
        return None
    path = parsed.path
    if not path:
        return None
    if path.startswith("/"):
        if base and path.startswith(base + "/"):
            path = path[len(base) :]
        elif base:
            return root / "__outside_base__" / path.lstrip("/")
        return root / path.lstrip("/")
    return (page.parent / path).resolve()


def _licensed(caption: str) -> bool:
    lower = caption.lower()
    return "CC" in caption or "domain" in lower or "dominio" in lower


def check_site(root: Path, base: str = "") -> CheckReport:
    report = CheckReport()
    base = base.rstrip("/")
    linked: set[Path] = set()  # every local page some other page links to
    redirects: set[Path] = set()  # old URLs of moved pages (not taxon pages any more)
    for page in sorted(root.rglob("*.html")):
        report.pages += 1
        rel = page.relative_to(root)
        parser = _PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for ref in parser.refs:
            target = _target(ref, base, root, page)
            if target is not None and not target.exists():
                report.problems.append(f"{rel}: broken link {ref}")
        for ref in parser.anchors:
            target = _target(ref, base, root, page)
            if target is not None and target.resolve() != page.resolve():
                linked.add(target.resolve())
        if parser.redirect:
            redirects.add(page.resolve())
        if rel.parts[0] in ("es", "en") and not parser.alternates:
            report.problems.append(f"{rel}: no hreflang alternate")
        unlicensed = [
            caption for has_img, caption in parser.figures if has_img and not _licensed(caption)
        ]
        if unlicensed:
            report.problems.append(
                f"{rel}: {len(unlicensed)} image(s) without a license in the credit"
            )
        if parser.unbalanced or parser.stack:
            unclosed = ", ".join(parser.stack[-3:])
            report.problems.append(
                f"{rel}: unbalanced tags (stray {parser.unbalanced[:3]}, unclosed [{unclosed}])"
            )
    # No taxon page is an orphan: each one is reachable from an index, a list or
    # another page (the encyclopedia must be browsable, not only searchable).
    for folder in ("es/taxones", "en/taxa"):
        for page in sorted((root / folder).glob("*.html")):
            if page.name != "index.html" and page.resolve() not in linked | redirects:
                report.problems.append(f"{page.relative_to(root)}: no page links to it")
    if report.pages == 0:
        report.problems.append(f"{root}: no pages (was the site built?)")
    for index, folder in (("es/buscar.json", "es/taxones"), ("en/search.json", "en/taxa")):
        if (root / index).exists():
            entries = len(json.loads((root / index).read_text(encoding="utf-8"))["taxa"])
            pages = len([
                p for p in (root / folder).glob("*.html")
                if p.name != "index.html" and p.resolve() not in redirects
            ])  # fmt: skip
            if entries != pages:
                report.problems.append(f"{index}: {entries} taxa in the index, {pages} pages")
    return report
