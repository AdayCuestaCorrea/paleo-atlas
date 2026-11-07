"""The glossary in the website (§12.2): terms marked in the prose of the taxon pages,
their definitions (with the glossary terms they use, marked too) and the glossary page.

Only published definitions are used (written from a cited Wikipedia revision and
passing every check). A term is marked the first time it appears on a page, as a link
to its entry in the glossary, so it works without JavaScript; glossary.js turns it into
a popover.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any
from urllib.parse import quote

CATEGORIES = ("anatomy", "time", "classification", "animals", "rocks")


def _pattern(forms: dict[str, str]) -> re.Pattern[str] | None:
    """One alternation of every form (longest first), whole words, any case. Forms are
    matched on escaped HTML text, so they are escaped too."""
    if not forms:
        return None
    alternatives = "|".join(
        re.escape(html.escape(f, quote=False)) for f in sorted(forms, key=len, reverse=True)
    )
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.I | re.U)


def sort_key(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode().lower()


class Glossary:
    """The published glossary in one language."""

    def __init__(self, rows: list[dict[str, Any]], lang: str, page_url: str) -> None:
        self.lang = lang
        self.page_url = page_url
        self.terms: dict[str, dict[str, Any]] = {}
        forms: dict[str, str] = {}
        for r in rows:
            definition = r.get(f"definition_{lang}")
            if not definition:
                continue
            self.terms[r["term_id"]] = r
            for form in [r[f"term_{lang}"], *(r.get(f"forms_{lang}") or [])]:
                if form:
                    forms.setdefault(form.lower(), r["term_id"])
        self._forms = forms
        self._pattern = _pattern(forms)

    def __bool__(self) -> bool:
        return bool(self.terms)

    def mark(self, escaped: str, used: set[str], skip: str | None = None) -> str:
        """Mark in already-escaped text the first appearance of each term not in
        ``used`` (which is updated), except ``skip`` (a definition never marks its own
        term)."""
        if self._pattern is None:
            return escaped

        def repl(m: re.Match[str]) -> str:
            key = self._forms.get(html.unescape(m.group(0)).lower())
            if key is None or key in used or key == skip:
                return m.group(0)
            used.add(key)
            return f'<a class="gl" href="{self.page_url}#{key}" data-gl="{key}">{m.group(0)}</a>'

        return self._pattern.sub(repl, escaped)

    def definition_html(self, term_id: str) -> str:
        """The definition, escaped, with the other glossary terms it uses marked."""
        used: set[str] = set()
        text = html.escape(self.terms[term_id][f"definition_{self.lang}"], quote=False)
        return self.mark(text, used, skip=term_id)

    def source(self, term_id: str) -> dict[str, str]:
        r = self.terms[term_id]
        if self.lang == "es" and r.get("source_title_es"):
            lang, title, revid = r.get("source_lang_es") or "es", r["source_title_es"], r[
                "source_revid_es"]  # fmt: skip
        else:
            lang, title, revid = "en", r["source_title_en"], r["source_revid_en"]
        url = f"https://{lang}.wikipedia.org/w/index.php?title={quote(title)}&oldid={revid}"
        return {"title": title, "url": url}

    def closure(self, ids: set[str]) -> list[str]:
        """The terms a page needs: those it marks and, recursively, those their
        definitions mark (a popover can open the definition of a term inside another)."""
        todo, seen = list(ids), set(ids)
        while todo:
            for key in re.findall(r'data-gl="([^"]+)"', self.definition_html(todo.pop())):
                if key not in seen:
                    seen.add(key)
                    todo.append(key)
        return sorted(seen)

    def page_data(self, ids: set[str]) -> dict[str, dict[str, str]]:
        """What the popovers of a page show, for the terms it marks."""
        return {
            key: {"term": self.terms[key][f"term_{self.lang}"],
                  "html": self.definition_html(key), **self.source(key)}
            for key in self.closure(ids)
        }  # fmt: skip

    def entries(self) -> list[dict[str, Any]]:
        """The glossary page: every published term, alphabetical, with its letter."""
        out = []
        for key, r in self.terms.items():
            term = r[f"term_{self.lang}"]
            other = r[f"term_{'en' if self.lang == 'es' else 'es'}"]
            out.append({
                "id": key, "term": term, "other": other, "category": r["category"],
                "pages": r.get(f"pages_{self.lang}") or 0, "html": self.definition_html(key),
                "letter": sort_key(term)[:1].upper(), **self.source(key),
                "search": " ".join([term, other, *(r.get(f"forms_{self.lang}") or [])]).lower(),
            })  # fmt: skip
        return sorted(out, key=lambda e: sort_key(e["term"]))
