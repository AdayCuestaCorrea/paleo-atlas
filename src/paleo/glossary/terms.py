"""The glossary's terms: technical words and phrases of the verified pages.

How many pages use each word or two-word phrase is counted in the verified texts of
both languages; an LLM picks the technical ones among the most frequent English
candidates and gives their Spanish equivalent, forms and category; then every term
is counted again with all its forms, and those in fewer than ``MIN_PAGES`` pages are
dropped. The result is the seed ``dbt/seeds/glossary_terms.csv``.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from itertools import pairwise
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from paleo.llm import LLM
from paleo.narrative.facts import prompt

MIN_PAGES = 3
CANDIDATES = 1_800
CHUNK = 200
FIRST_BATCH = 150
FIELDS = ["term_id", "term_en", "term_es", "forms_en", "forms_es", "category", "pages_en",
          "pages_es", "batch"]  # fmt: skip
WORD = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.U)
# Function words: a two-word phrase with one of them is never a term ("during the").
STOP = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "from", "by", "with", "for",
    "as", "into", "onto", "than", "that", "this", "these", "those", "which", "who", "whose",
    "its", "it", "his", "her", "their", "they", "was", "were", "is", "are", "be", "been",
    "being", "has", "had", "have", "also", "more", "most", "one", "two", "three", "some",
    "many", "other", "such", "both", "during", "after", "before", "while", "when", "where",
    "about", "between", "within", "like", "not", "only", "up", "but", "all", "any", "each",
    "very",
}  # fmt: skip


class Term(BaseModel):
    en: str
    es: str
    forms_en: list[str] = []
    forms_es: list[str] = []
    category: Literal["anatomy", "time", "classification", "animals", "rocks"]


class Terms(BaseModel):
    terms: list[Term]


class SpanishTerm(BaseModel):
    index: int
    term: str
    forms: list[str] = []


class SpanishTerms(BaseModel):
    terms: list[SpanishTerm]


LATIN = re.compile(r"(idae|inae|oidea|ia|ini|formes)$", re.I)  # Tyrannosauridae, Ornithischia
SPANISH_BATCH = 10
SENTENCES_PER_TERM = 3


def page_texts(texts_dir: Path) -> dict[str, list[str]]:
    """Language -> the plain text of every verified page."""
    out: dict[str, list[str]] = {"en": [], "es": []}
    for path in sorted(texts_dir.glob("*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        if page.get("status") != "verified" or page.get("lang") not in out:
            continue
        out[page["lang"]].append(" ".join(
            s["text"] for section in page["sections"] for s in section["sentences"]
        ))  # fmt: skip
    return out


def aligned_sentences(texts_dir: Path) -> list[tuple[str, str]]:
    """(English, Spanish) sentence pairs of the pages verified in both languages, paired
    by the facts they cite (a Spanish page may have lost a sentence in the rescue)."""
    out = []
    for path in sorted(texts_dir.glob("*.en.json")):
        twin = path.with_name(path.name.replace(".en.json", ".es.json"))
        if not twin.exists():
            continue
        en, es = (json.loads(p.read_text(encoding="utf-8")) for p in (path, twin))
        if en.get("status") != "verified" or es.get("status") != "verified":
            continue
        spanish = {
            (sec["section"], tuple(s["fact_ids"])): s["text"]
            for sec in es["sections"] for s in sec["sentences"]
        }  # fmt: skip
        for sec in en["sections"]:
            for s in sec["sentences"]:
                match = spanish.get((sec["section"], tuple(s["fact_ids"])))
                if match:
                    out.append((s["text"], match))
    return out


def page_frequencies(texts: Iterable[str], exclude: set[str]) -> Counter[str]:
    """In how many pages each lowercase word (4+ letters) and two-word phrase appears;
    words in ``exclude`` (scientific names) and phrases with them are left out."""
    counts: Counter[str] = Counter()
    for text in texts:
        words = [w.lower() for w in WORD.findall(text)]
        seen = {w for w in words if len(w) >= 4 and w not in exclude and w not in STOP}
        seen |= {f"{a} {b}" for a, b in pairwise(words)
                 if len(a) >= 3 and len(b) >= 3 and not {a, b} & (exclude | STOP)}  # fmt: skip
        counts.update(seen)
    return counts


def term_id(term: str) -> str:
    plain = unicodedata.normalize("NFKD", term).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def form_pattern(forms: Iterable[str]) -> re.Pattern[str]:
    """Whole-word, case-insensitive match of any of the forms (longest first)."""
    alternatives = "|".join(re.escape(f) for f in sorted(set(forms), key=len, reverse=True))
    return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", re.I | re.U)


def pages_with(texts: Iterable[str], forms: Iterable[str]) -> int:
    pattern = form_pattern(forms)
    return sum(1 for text in texts if pattern.search(text))


def pick_terms(llm: LLM, candidates: list[str]) -> list[Term]:
    """The technical terms among the candidates, in chunks (one call each)."""
    system, _ = prompt("glossary_terms")
    out: list[Term] = []
    for start in range(0, len(candidates), CHUNK):
        chunk = candidates[start : start + CHUNK]
        answer = llm.complete_json(system, "CANDIDATES:\n" + "\n".join(chunk), Terms,
                                   max_tokens=5_000)  # fmt: skip
        out += answer.terms
    return out


def _proper(term: str) -> str:
    return term[:1].upper() + term[1:]


def merge_terms(terms: list[Term]) -> list[Term]:
    """One term per Spanish equivalent (the LLM may give "theropod" and "theropod
    dinosaur", or "Late" and "Upper Cretaceous"): the first keeps the others as forms.
    Geological time units are proper names and keep a capital."""
    from paleo.site.terms import _STAGES, _UNITS  # the site's Spanish names of time units

    out: dict[str, Term] = {}
    for t in terms:
        if t.category == "time":
            en = _proper(t.en)
            es = _STAGES.get(en) or _UNITS.get(en) or _proper(t.es)
            forms_es = sorted({*t.forms_es, t.es} - {es}) if es != t.es else t.forms_es
            t = t.model_copy(update={"en": en, "es": es, "forms_es": forms_es})
        key = re.sub(r"^(periodo|período|piso|edad|época) ", "", t.es.lower())
        if key in out:
            first = out[key]
            first.forms_en = sorted({*first.forms_en, t.en, *t.forms_en} - {first.en})
            first.forms_es = sorted({*first.forms_es, t.es, *t.forms_es} - {first.es})
        else:
            out[key] = t
    return list(out.values())


def spanish_terms(llm: LLM, terms: list[Term], pairs: list[tuple[str, str]]) -> list[Term]:
    """The Spanish term and forms as our Spanish pages really write them, read from the
    sentences aligned with English ones that use the term. A form the model returns
    that is not in those Spanish sentences is ignored; a term with no aligned
    sentence keeps the LLM's first guess."""
    system, _ = prompt("glossary_spanish")
    out = list(terms)
    asks = []
    for n, t in enumerate(terms):
        pattern = form_pattern([t.en, *t.forms_en])
        found = [(en, es) for en, es in pairs if pattern.search(en)][:SENTENCES_PER_TERM]
        if found:
            asks.append((n, found))
    for start in range(0, len(asks), SPANISH_BATCH):
        batch = asks[start : start + SPANISH_BATCH]
        user = "\n\n".join(
            f"{i}. TERM: {terms[n].en}\n" + "\n".join(f"EN: {en}\nES: {es}" for en, es in found)
            for i, (n, found) in enumerate(batch, start=1)
        )
        answer = llm.complete_json(system, user, SpanishTerms, max_tokens=3_000)
        for item in answer.terms:
            if not 1 <= item.index <= len(batch):
                continue
            n, found = batch[item.index - 1]
            spanish = " ".join(es for _, es in found).lower()
            forms = [f for f in item.forms if f and f.lower() in spanish]
            if forms:
                out[n] = terms[n].model_copy(update={"es": item.term, "forms_es": forms})
    return out


def build_terms(
    llm: LLM, texts_dir: Path, scientific_names: set[str]
) -> list[dict[str, str | int]]:
    """Seed rows: the picked terms with all their forms counted in both languages,
    most used first; the first ``FIRST_BATCH`` are batch 1."""
    texts = page_texts(texts_dir)
    exclude = {n.lower() for n in scientific_names}
    freq = page_frequencies(texts["en"], exclude)
    candidates = [w for w, n in freq.most_common() if n >= MIN_PAGES][:CANDIDATES]
    rows: dict[str, dict[str, str | int]] = {}
    picked = [t for t in pick_terms(llm, candidates) if not LATIN.search(t.en)]
    picked = merge_terms(spanish_terms(llm, picked, aligned_sentences(texts_dir)))
    for t in picked:
        key = term_id(t.en)
        # only forms that really appear in that language's pages ("late Cretácico" is not
        # Spanish, "cranial" is not a Spanish form)
        forms_en = sorted({t.en} | {f for f in t.forms_en if f and pages_with(texts["en"], [f])})
        forms_es = sorted({t.es} | {f for f in t.forms_es if f and pages_with(texts["es"], [f])})
        pages_en, pages_es = pages_with(texts["en"], forms_en), pages_with(texts["es"], forms_es)
        if key in rows or pages_en + pages_es < MIN_PAGES:
            continue
        rows[key] = {
            "term_id": key, "term_en": t.en, "term_es": t.es,
            "forms_en": "|".join(f for f in forms_en if f != t.en),
            "forms_es": "|".join(f for f in forms_es if f != t.es),
            "category": t.category, "pages_en": pages_en, "pages_es": pages_es,
        }  # fmt: skip
    ordered = sorted(rows.values(), key=lambda r: (-(r["pages_en"] + r["pages_es"]), r["term_id"]))
    for n, row in enumerate(ordered):
        row["batch"] = 1 if n < FIRST_BATCH else 2
    return ordered


def write_seed(rows: list[dict[str, str | int]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
