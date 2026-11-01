"""Checks on the built site, run in CI before publishing (ALCANCE.md §16).

* every internal link, image, stylesheet and script points to an existing file;
* every page has its counterpart in the other language (hreflang);
* every taxon image has a credit with its license;
* HTML tags are balanced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "source", "track", "wbr",
}  # fmt: skip


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.alternates: list[str] = []
        self.stack: list[str] = []
        self.unbalanced: list[str] = []
        self.hero_images = 0
        self.figcaption_text = ""
        self._in_figcaption = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        for name in ("href", "src"):
            if a.get(name):
                self.refs.append(a[name] or "")
        if tag == "link" and a.get("rel") == "alternate" and a.get("href"):
            self.alternates.append(a["href"] or "")
        if tag == "img" and "pic--hero" in (a.get("class") or ""):
            self.hero_images += 1
        if tag == "figcaption":
            self._in_figcaption = True
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "figcaption":
            self._in_figcaption = False
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.unbalanced.append(tag)

    def handle_data(self, data: str) -> None:
        if self._in_figcaption:
            self.figcaption_text += data


@dataclass
class CheckReport:
    pages: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems


def _target(ref: str, base: str, root: Path, page: Path) -> Path | None:
    """Local file a reference points to, or None for external links."""
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


def check_site(root: Path, base: str = "") -> CheckReport:
    report = CheckReport()
    base = base.rstrip("/")
    for page in sorted(root.rglob("*.html")):
        report.pages += 1
        rel = page.relative_to(root)
        parser = _PageParser()
        parser.feed(page.read_text(encoding="utf-8"))
        for ref in parser.refs:
            target = _target(ref, base, root, page)
            if target is not None and not target.exists():
                report.problems.append(f"{rel}: broken link {ref}")
        if rel.parts[0] in ("es", "en") and not parser.alternates:
            report.problems.append(f"{rel}: no hreflang alternate")
        if (
            parser.hero_images
            and "CC" not in parser.figcaption_text
            and (
                "domain" not in parser.figcaption_text.lower()
                and "dominio" not in parser.figcaption_text.lower()
            )
        ):
            report.problems.append(f"{rel}: image without a license in its credit")
        if parser.unbalanced or parser.stack:
            unclosed = ", ".join(parser.stack[-3:])
            report.problems.append(
                f"{rel}: unbalanced tags (stray {parser.unbalanced[:3]}, unclosed [{unclosed}])"
            )
    return report
