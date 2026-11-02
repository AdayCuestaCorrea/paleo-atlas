"""Deterministic checks for extracted facts and written sentences (ALCANCE.md §12.1, §16).

No model judges another model here: every rule is plain string logic, so a
failure can be explained and reproduced.

* **Fact check** — a fact's quote must appear verbatim in its source chunk, and
  every number in the fact must appear in that quote.
* **Citation** — every sentence cites at least one existing fact.
* **Faithfulness** — numbers in a sentence must come from the facts it cites;
  capitalized names must come from the taxon's facts.
* **Anti-copy** — no sentence shares a run of ``N_GRAM`` words with a source
  in the same language (the published prose must be new writing). Runs made
  mostly of names, numbers and function words ("from the Late Cretaceous Farak
  Formation of Niger") are facts, not prose: a run only counts as copied when
  it contains at least ``MIN_ORDINARY_WORDS`` ordinary words.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

N_GRAM = 8  # decision §16: no 8-word run copied from a source
MIN_ORDINARY_WORDS = 4
MIN_QUOTE_CHARS = 12
MAX_WORDS = 520
MIN_WORDS = 40

_QUOTES = str.maketrans(
    {
        "\u201c": '"',  # left double quote
        "\u201d": '"',  # right double quote
        "\u2018": "'",  # left single quote
        "\u2019": "'",  # right single quote
        "\u2013": "-",  # en dash
        "\u2014": "-",  # em dash
        "\u2212": "-",  # minus sign
    }
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*|\d+(?:[.,]\d+)*", re.UNICODE)
_CAPITALIZED = re.compile(r"\b[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,}(?:-[a-záéíóúñü]+)?\b")

# Capitalized words that are not claims (sentence openers, months, section words).
_NOT_NAMES = {
    "the",
    "this",
    "these",
    "its",
    "it",
    "in",
    "on",
    "at",
    "as",
    "a",
    "an",
    "and",
    "but",
    "with",
    "from",
    "during",
    "after",
    "before",
    "unlike",
    "like",
    "both",
    "some",
    "most",
    "however",
    "although",
    "while",
    "because",
    "their",
    "they",
    "researchers",
    "scientists",
    "paleontologists",
    "today",
    "until",
    "when",
    "where",
    "which",
    "who",
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "este",
    "esta",
    "estos",
    "estas",
    "su",
    "sus",
    "en",
    "con",
    "de",
    "del",
    "durante",
    "tras",
    "antes",
    "después",
    "aunque",
    "mientras",
    "como",
    "hoy",
    "según",
    "investigadores",
    "paleontólogos",
    "científicos",
}


_FUNCTION_WORDS = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "at",
    "to",
    "from",
    "by",
    "for",
    "with",
    "and",
    "or",
    "as",
    "is",
    "was",
    "were",
    "be",
    "been",
    "its",
    "it",
    "that",
    "this",
    "which",
    "into",
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "de",
    "del",
    "en",
    "por",
    "para",
    "con",
    "y",
    "o",
    "que",
    "se",
    "su",
    "sus",
    "es",
    "fue",
    "era",
    "al",
    "lo",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    return " ".join(text.lower().split())


def numbers(text: str) -> set[str]:
    """Numbers in a language-neutral form: "1,5" and "1.5" -> "1.5"; "1,000" -> "1000"."""
    # Spanish style groups thousands with a (narrow) space: "1 742,8" -> "1742,8".
    text = re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?:\D|$))", "", text)
    out = set()
    for token in _NUMBER.findall(text):
        token = re.sub(r"[.,](?=\d{3}(?:\D|$))", "", token)  # thousands separators
        out.add(token.replace(",", "."))
    return out


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(unicodedata.normalize("NFKC", text))]


def ngrams(tokens: list[str], n: int = N_GRAM) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


_EPITHET = re.compile(r"(?:is|us|i|ae|um|a|ensis|orum|arum|oides)$")


def _is_ordinary(token: str, previous: str | None) -> bool:
    """A lowercase word that is not a function word, a number or a species epithet
    (a Latin-looking word right after a capitalized genus: "Rebbachisaurus tamesnensis")."""
    if not token.islower() or token in _FUNCTION_WORDS or token[0].isdigit():
        return False
    return not (previous and previous[:1].isupper() and _EPITHET.search(token))


def copied_runs(text: str, source_grams: set[tuple[str, ...]]) -> list[str]:
    """Runs of ``N_GRAM`` words shared with a source that read as copied prose."""
    original = _WORD.findall(unicodedata.normalize("NFKC", text))
    lowered = [t.lower() for t in original]
    runs = []
    for i in range(len(lowered) - N_GRAM + 1):
        if tuple(lowered[i : i + N_GRAM]) in source_grams:
            window = original[i : i + N_GRAM]
            previous = [original[i - 1] if i else None, *window[:-1]]
            ordinary = sum(_is_ordinary(t, p) for t, p in zip(window, previous, strict=True))
            if ordinary >= MIN_ORDINARY_WORDS:
                runs.append(" ".join(window))
    return runs


def names(text: str) -> set[str]:
    """Capitalized words that look like names (first word of the text excluded)."""
    found = set()
    for match in _CAPITALIZED.finditer(text):
        if match.start() == 0:
            continue
        if match.group(0).lower() not in _NOT_NAMES:
            found.add(match.group(0))
    return found


# --------------------------------------------------------------------------- facts


def check_fact(statement: str, quote: str, chunk_text: str) -> str | None:
    """Why the fact is rejected, or None when it is supported by its chunk."""
    if len(quote.strip()) < MIN_QUOTE_CHARS:
        return "quote too short"
    if normalize(quote) not in normalize(chunk_text):
        return "quote not found verbatim in the source"
    missing = numbers(statement) - numbers(quote)
    if missing:
        return f"numbers not in the quote: {sorted(missing)}"
    if copied := copied_runs(statement, ngrams(words(chunk_text))):
        # Facts copied from the source would be copied again by the writer.
        return f"statement copies the source wording: {copied[0]!r}"
    return None


# --------------------------------------------------------------------------- sentences


@dataclass
class SentenceReport:
    index: int
    text: str
    problems: list[str] = field(default_factory=list)


@dataclass
class TextReport:
    sentences: list[SentenceReport]
    problems: list[str] = field(default_factory=list)  # text-level problems
    word_count: int = 0

    @property
    def passed(self) -> bool:
        return not self.problems and all(not s.problems for s in self.sentences)

    def summary(self) -> list[str]:
        out = list(self.problems)
        for s in self.sentences:
            out.extend(f"sentence {s.index + 1} ({s.text[:60]!r}): {p}" for p in s.problems)
        return out


def check_text(
    sentences: list[tuple[str, list[str]]],
    facts: dict[str, str],
    source_texts: Iterable[str],
    *,
    check_names: bool = True,
) -> TextReport:
    """Check sentences ``[(text, fact_ids)]`` against facts ``{fact_id: fact text}``.

    ``facts`` values should contain everything a sentence may rely on (the
    fact statement and, when public, its quote). ``source_texts`` are the
    chunks in the same language as the sentences (for the anti-copy rule).
    """
    source_grams: set[tuple[str, ...]] = set()
    for text in source_texts:
        source_grams |= ngrams(words(text))
    all_names = (
        set().union(*(names(f) | set(f.split()) for f in facts.values())) if facts else set()
    )

    reports = []
    for i, (text, fact_ids) in enumerate(sentences):
        report = SentenceReport(i, text)
        cited = [facts[f] for f in fact_ids if f in facts]
        if not fact_ids:
            report.problems.append("no citation")
        elif len(cited) != len(fact_ids):
            unknown = [f for f in fact_ids if f not in facts]
            report.problems.append(f"cites unknown facts {unknown}")
        cited_numbers = set().union(*(numbers(c) for c in cited)) if cited else set()
        if missing := numbers(text) - cited_numbers:
            report.problems.append(f"numbers not in the cited facts: {sorted(missing)}")
        if check_names and (unknown_names := {n for n in names(text) if n not in all_names}):
            report.problems.append(f"names not in the facts: {sorted(unknown_names)}")
        if copied := copied_runs(text, source_grams):
            report.problems.append(f"copies {N_GRAM}+ words from a source: {copied[0]!r}")
        reports.append(report)

    # The same fact as the only support of two sentences = the text repeats itself.
    sole: dict[str, int] = {}
    for report, (_, fact_ids) in zip(reports, sentences, strict=True):
        if len(fact_ids) == 1:
            if fact_ids[0] in sole:
                report.problems.append(
                    f"repeats the fact of sentence {sole[fact_ids[0]] + 1} ({fact_ids[0]})"
                )
            else:
                sole[fact_ids[0]] = report.index

    word_count = sum(len(words(t)) for t, _ in sentences)
    problems = []
    if word_count > MAX_WORDS:
        problems.append(f"too long: {word_count} words (max {MAX_WORDS})")
    if word_count < MIN_WORDS and len(facts) >= 6:
        problems.append(f"too short: {word_count} words for {len(facts)} facts")
    return TextReport(reports, problems, word_count)


# Clades above the family keep their Latin form in English but are written in
# Spanish ("Crocodylomorpha" -> "cocodrilomorfos"); genera and species never are.
_HIGHER_CLADE = re.compile(r"(?:morpha|poda|ia|formes|oidea|idae|inae|ae)$")


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )


def _spanish_clade_in(name: str, text: str) -> bool:
    """True when `text` writes the clade `name` in Spanish: same hispanized stem,
    any ending (Crocodylomorpha -> cocodrilomorfos, Neosauropoda -> neosaurópodos)."""
    from paleo.site.terms import hispanize

    if not _HIGHER_CLADE.search(name):
        return False
    stem = re.sub(r"[aeiou]+$", "", hispanize(name)).replace("crocodil", "cocodril")
    return len(stem) >= 6 and any(w.startswith(stem) for w in re.findall(r"\w+", _fold(text)))


def check_alignment(
    source: list[tuple[str, list[str]]],
    adapted: list[str],
    scientific_names: set[str],
) -> list[str]:
    """An adaptation must keep one sentence per source sentence, the same numbers
    and every scientific name used in the source sentence."""
    if len(source) != len(adapted):
        return [f"{len(adapted)} sentences for {len(source)} in the source text"]
    problems = []
    for i, ((src, _), dst) in enumerate(zip(source, adapted, strict=True)):
        if numbers(src) != numbers(dst):
            problems.append(
                f"sentence {i + 1}: numbers differ "
                f"({sorted(numbers(src))} vs {sorted(numbers(dst))})"
            )
        kept = {n for n in scientific_names if n in src}
        if lost := {n for n in kept if n not in dst and not _spanish_clade_in(n, dst)}:
            problems.append(f"sentence {i + 1}: scientific names lost {sorted(lost)}")
    return problems
