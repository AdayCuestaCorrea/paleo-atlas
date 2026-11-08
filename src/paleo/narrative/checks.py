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
MAX_WORDS = 850
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
_HIGHER_CLADE = re.compile(r"(?:morpha|poda|ia|formes|oidea|idae|inae|ae|aves|ea)$")


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
    # The words are spelled the Spanish way too, so a half-Latin form still matches
    # ("Caenagnátidos" for Caenagnathidae, "coelurosáuridos" for Coelurosauria).
    words = [hispanize(w).replace("crocodil", "cocodril") for w in re.findall(r"\w+", _fold(text))]
    return len(stem) >= 6 and any(w.startswith(stem) for w in words)


def _has_name(name: str, text: str) -> bool:
    """The name as a whole word: "Manu" is not in "manual", nor "Troodon" in
    "Troodontidae"."""
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text) is not None


_ES_NUMBER_WORDS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
    "mil": 1000,
}  # fmt: skip
_EN_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}  # fmt: skip
_ES_EXTRA_WORDS = {
    "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
    "veintiocho": 28, "veintinueve": 29, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
}  # fmt: skip
_SPELLED_SMALL = {k: v for k, v in _ES_NUMBER_WORDS.items() if v < 100}
_SPELLED_SMALL |= _EN_NUMBER_WORDS | {k: v for k, v in _ES_EXTRA_WORDS.items() if v < 100}
_HUNDREDS = {"hundred": 100, "cien": 100, "ciento": 100} | {
    k: v for k, v in _ES_EXTRA_WORDS.items() if v >= 100
}
_SCALES = {"thousand": 1000, "mil": 1000, "million": 10**6, "millon": 10**6,
           "millones": 10**6, "billion": 10**9}  # fmt: skip


def spelled_numbers(text: str) -> list[set[str]]:
    """Numbers written in words, in English or Spanish ("fifty-eight million",
    "cincuenta y ocho millones"), each as the forms it may take in digits: the whole
    value and, before "million" or larger, the number in front of it ("58 million" ->
    58). Small numbers alone (one to twelve) are left out: they are ordinary words ("one
    of the", "dos grupos") more often than figures. "Mil millones" is a (short) billion."""
    tokens = re.findall(r"\w+", _fold(text).replace("-", " "))
    found: list[set[str]] = []
    i = 0
    while i < len(tokens):
        total = current = used = 0
        coefficient = None
        j = i
        while j < len(tokens):
            t = tokens[j]
            if t in _SPELLED_SMALL and (not used or current % 10 == 0):
                current += _SPELLED_SMALL[t]
            elif t == "hundred" and used:
                current *= 100
            elif t in _HUNDREDS and t != "hundred":
                current += _HUNDREDS[t]
            elif t in _SCALES and (used or t == "mil"):
                scale = _SCALES[t]
                if t == "mil" and tokens[j + 1 : j + 2] in (["millones"], ["millon"]):
                    scale, j = 10**9, j + 1
                if scale >= 10**6 and coefficient is None:
                    coefficient = total + (current or 1)
                total += (current or 1) * scale
                current = 0
            elif (
                t in ("and", "y")
                and used
                and tokens[j + 1 : j + 2]
                and tokens[j + 1] in _SPELLED_SMALL
            ):
                pass
            else:
                break
            used += 1
            j += 1
        if not used:
            i += 1
            continue
        value = total + current
        if total or value > 12:
            found.append({str(value)} | ({str(coefficient)} if coefficient else set()))
        i = j
    return found


_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def _roman(token: str) -> int | None:
    if not re.fullmatch(r"[IVXL]+", token):
        return None
    total = 0
    for a, b in zip(token, token[1:] + " ", strict=True):
        value = _ROMAN[a]
        total += -value if b != " " and _ROMAN[b] > value else value
    return total


def _said_otherwise(number: str, dst: str) -> bool:
    """A number of the English sentence that the Spanish one writes in its own way: a
    century in Roman numerals ("19th century" -> "siglo XIX") or in words ("dos")."""
    if not number.isdigit() or int(number) > 1000:
        return False
    n = int(number)
    if any(_roman(t) == n for t in re.findall(r"\b[IVXL]+\b", dst)):
        return True
    return any(_ES_NUMBER_WORDS.get(w) == n for w in re.findall(r"\w+", _fold(dst)))


def numbers_match(src: str, dst: str) -> bool:
    """The same numbers in a sentence and its adaptation, allowing the Spanish ways of
    writing some of them: centuries in Roman numerals, small numbers in words and short
    decades ("the 1990s" -> "los años 90"). A converted unit (3.45 t -> 3450 kg) or a
    different number still fails."""
    s, d = numbers(src), numbers(dst)
    missing, extra = s - d, d - s
    for n in sorted(missing):
        if re.fullmatch(r"1[5-9]\d0|20[0-2]0", n) and n[2:] in extra:  # "1990" -> "90"
            missing.discard(n)
            extra.discard(n[2:])
        elif _said_otherwise(n, dst):
            missing.discard(n)
    return not missing and not extra


def _align_one(src: str, dst: str, scientific_names: set[str]) -> list[str]:
    """What an adapted sentence lost from its source sentence (empty if nothing)."""
    problems = []
    if not numbers_match(src, dst):
        problems.append(f"numbers differ ({sorted(numbers(src))} vs {sorted(numbers(dst))})")
    # "5,650 kg" in English is five thousand; in Spanish it reads as 5.65.
    grouped = {m for m in re.findall(r"\b\d{1,3}(?:,\d{3})+(?!\d)", src)}
    if comma := sorted(m for m in grouped if m in dst):
        problems.append(
            f"thousands written with a comma {comma} read as decimals "
            "in Spanish: write them without it (5650) or with a space (12 300)"
        )
    kept = {n for n in scientific_names if _has_name(n, src)}
    if lost := {n for n in kept if not _has_name(n, dst) and not _spanish_clade_in(n, dst)}:
        problems.append(f"scientific names lost {sorted(lost)}")
    return problems


def check_alignment(
    source: list[tuple[str, list[str]]],
    adapted: list[str],
    scientific_names: set[str],
) -> list[str]:
    """An adaptation must keep one sentence per source sentence, the same numbers
    and every scientific name used in the source sentence."""
    if len(source) != len(adapted):
        return [f"{len(adapted)} sentences for {len(source)} in the source text"]
    return [
        f"sentence {i + 1}: {p}"
        for i, ((src, _), dst) in enumerate(zip(source, adapted, strict=True))
        for p in _align_one(src, dst, scientific_names)
    ]


def alignment_failures(
    source: list[tuple[str, list[str]]],
    adapted: list[str],
    scientific_names: set[str],
) -> set[int] | None:
    """Indices (from 0) of the adapted sentences that fail the alignment; None when
    the number of sentences differs (then the whole text fails)."""
    if len(source) != len(adapted):
        return None
    return {
        i
        for i, ((src, _), dst) in enumerate(zip(source, adapted, strict=True))
        if _align_one(src, dst, scientific_names)
    }
