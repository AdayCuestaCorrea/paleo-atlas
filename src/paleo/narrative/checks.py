"""Deterministic checks for extracted facts and written sentences (ALCANCE.md §12.1, §16).

No model judges another model here: every rule is plain string logic, so a
failure can be explained and reproduced.

* **Fact check** — a fact's quote must appear verbatim in its source chunk, every
  number in the fact must appear in that quote, and every abbreviated species
  ("A. volgensis") must be named so in the quote or its chunk.
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

# "A. volgensis"; not "D.C. since" (an acronym) nor "Ji Q. and" (a person's initial).
_SPECIES_ABBR = re.compile(r"(?<![^\W\d_.])([A-Z])\. ([a-z]{3,})\b")


def _one_letter_apart(a: str, b: str) -> bool:
    """A letter added, dropped or two letters swapped ("gracillis", "dentisuclatus"):
    a typo of the source the model fixed, not another species."""
    if min(len(a), len(b)) < 6 or a == b:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diff) != 2 or diff[1] != diff[0] + 1:
            return False
        i, j = diff
        return a[i] == b[j] and a[j] == b[i]
    if abs(len(a) - len(b)) != 1:
        return False
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1 :] == short for i in range(len(long_)))


def _named_epithets(initial: str, text: str, *, strict: bool) -> list[str]:
    """Epithets the text names for that initial. Strict: only after the abbreviation
    ("A. volgensis", '"A." volgensis', "S, kryschtofovici"). Otherwise also after any
    word with that initial ("Asiatosuchus volgensis") or a catalog key ("species:")."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    if strict:
        pattern = rf"(?<![^\W\d_])\"?{initial}\"?[.,]\"?\s{{0,2}}\"?([a-z]{{3,}})"
    else:  # lookahead: "Dryptosaurus\nspecies: aquilunguis" overlaps
        pattern = rf"(?=(?:\b{initial}[^\W\d_]*|species:)[\s.,'\"*]{{1,4}}([a-z]{{3,}}))"
    return re.findall(pattern, text)


def _same_epithet(found: str, epithet: str) -> bool:
    # a typo of the source the model fixed ("gracillis"), or the wikitext glued the
    # next word: "A. siemensiiDames" ([a-z] stops there), "M. glycyswith" (a prefix)
    return (
        found == epithet
        or _one_letter_apart(found, epithet)
        or (len(epithet) >= 5 and found.startswith(epithet))
    )


def species_not_in_source(statement: str, quote: str, context: str = "") -> list[str]:
    """Abbreviated species of the statement ("A. volynensis") that the source does
    not name: their epithet must appear after a word with the same initial
    ("A. volgensis", "Asiatosuchus volgensis", '"A." volgensis', "S, kryschtofovici")
    or in a catalog line ("species: jonesi"), spelled the same or one letter apart.

    A quote that only says "this species" may be completed from the ``context`` (the
    chunk and its heading), unless the statement swaps the species of the quote for
    another one ("A. palustris was described…" under a heading about another species
    becomes "A. iberoarmoricanus was described…"). Catches a
    species name changed or made up by the model, which the number check cannot see."""
    missing = []
    for match in _SPECIES_ABBR.finditer(statement):
        initial, epithet = match.groups()
        if epithet in _FUNCTION_WORDS or re.search(r"\b[A-Z]\. ?$", statement[: match.start()]):
            continue  # "Ji Q. and", "Washington D. C. since"
        if any(_same_epithet(n, epithet) for n in _named_epithets(initial, quote, strict=False)):
            continue  # "P. trossingensis" for "Plateosaurus trossingensis"
        in_quote = _named_epithets(initial, quote, strict=True)
        in_statement = _named_epithets(initial, statement, strict=False)  # "Pteranodon sternbergi"
        if in_quote and not any(_same_epithet(q, e) for q in in_quote for e in in_statement):
            missing.append(f"{initial}. {epithet}")  # swapped for the quote's species
            continue
        in_context = _named_epithets(initial, context, strict=False)
        if not any(_same_epithet(n, epithet) for n in in_context):
            missing.append(f"{initial}. {epithet}")
    return missing


def check_fact(statement: str, quote: str, chunk_text: str, heading: str = "") -> str | None:
    """Why the fact is rejected, or None when it is supported by its chunk.

    ``heading`` is the chunk's title ("Lepidotes (L. gigas)"): a species section
    names its species there and then says "this species"."""
    if len(quote.strip()) < MIN_QUOTE_CHARS:
        return "quote too short"
    if normalize(quote) not in normalize(chunk_text):
        return "quote not found verbatim in the source"
    missing = numbers(statement) - numbers(quote)
    if missing:
        return f"numbers not in the quote: {sorted(missing)}"
    if unnamed := species_not_in_source(statement, quote, f"{heading}\n{chunk_text}"):
        return f"species not named so in the source: {unnamed}"
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


# ICS stages, the ones that end in -ian in English. A Spanish sentence must not name
# a stage that its English sentence does not ("Santonian" -> "Cenomaniense").
_STAGES = [
    "Meghalayan",
    "Northgrippian",
    "Greenlandian",
    "Tarantian",
    "Chibanian",
    "Calabrian",
    "Gelasian",
    "Piacenzian",
    "Zanclean",
    "Messinian",
    "Tortonian",
    "Serravallian",
    "Langhian",
    "Burdigalian",
    "Aquitanian",
    "Chattian",
    "Rupelian",
    "Priabonian",
    "Bartonian",
    "Lutetian",
    "Ypresian",
    "Thanetian",
    "Selandian",
    "Danian",
    "Maastrichtian",
    "Campanian",
    "Santonian",
    "Coniacian",
    "Turonian",
    "Cenomanian",
    "Albian",
    "Aptian",
    "Barremian",
    "Hauterivian",
    "Valanginian",
    "Berriasian",
    "Tithonian",
    "Kimmeridgian",
    "Oxfordian",
    "Callovian",
    "Bathonian",
    "Bajocian",
    "Aalenian",
    "Toarcian",
    "Pliensbachian",
    "Sinemurian",
    "Hettangian",
    "Rhaetian",
    "Norian",
    "Carnian",
    "Ladinian",
    "Anisian",
    "Olenekian",
    "Induan",
    "Changhsingian",
    "Wuchiapingian",
    "Capitanian",
    "Wordian",
    "Roadian",
    "Kungurian",
    "Artinskian",
    "Sakmarian",
    "Asselian",
    "Gzhelian",
    "Kasimovian",
    "Moscovian",
    "Bashkirian",
    "Serpukhovian",
    "Tournaisian",
    "Famennian",
    "Frasnian",
    "Givetian",
    "Eifelian",
    "Emsian",
    "Pragian",
    "Lochkovian",
    "Ludfordian",
    "Gorstian",
    "Homerian",
    "Sheinwoodian",
    "Telychian",
    "Aeronian",
    "Rhuddanian",
    "Hirnantian",
    "Katian",
    "Sandbian",
    "Darriwilian",
    "Dapingian",
    "Floian",
    "Tremadocian",
]
# Spanish spellings that do not start like the English name ("rético", "bayociense").
_STAGE_ALIASES = {"Rhaetian": ("ret",), "Ypresian": ("ipres",), "Lutetian": ("lutec",),
                  "Bajocian": ("bayoc",), "Piacenzian": ("plasenc",)}  # fmt: skip


def _stage_form(word: str) -> str:
    """A spelling-tolerant form: no accents, no h, no double letters."""
    return re.sub(r"(.)\1", r"\1", _fold(word).replace("h", ""))


_STAGE_STEMS = {
    stage: (re.sub(r"(?:ian|ean|an)$", "", _stage_form(stage)), *_STAGE_ALIASES.get(stage, ()))
    for stage in _STAGES
}
_ES_STAGE_ENDING = re.compile(r"(?:u?iense|ense|ico|ica|iano|iana)s?")
_ES_STAGE_WORDS = {"danes": "Danian", "danesa": "Danian"}  # "el Danés" (Danian)


def stages_en(text: str) -> set[str]:
    return {w for w in re.findall(r"\b[A-Z][a-z]+(?:ian|ean|an)\b", text) if w in _STAGE_STEMS}


def stages_es(text: str, keep: str = "") -> set[str]:
    """Stages named in a Spanish text: stem of the English name + a Spanish ending
    ("Maastrichtiense", "titónico", "Danés"), so "norteamericana" is not Norian. Words
    also in ``keep`` (the English sentence) are names, not stages ("A. tortonica")."""
    found = set()
    kept = set(re.findall(r"[^\W\d_]+", keep))
    for word in re.findall(r"[^\W\d_]+", text):
        if word in kept:
            continue
        form = _stage_form(word)
        found |= {
            stage
            for stage, stems in _STAGE_STEMS.items()
            for stem in stems
            if form.startswith(stem) and _ES_STAGE_ENDING.fullmatch(form[len(stem) :])
        }
        if form in _ES_STAGE_WORDS:
            found.add(_ES_STAGE_WORDS[form])
    return found


_PERIODS = {"Cambrian": "cambrico", "Ordovician": "ordovicico", "Silurian": "silurico",
            "Devonian": "devonico", "Carboniferous": "carbonifero", "Permian": "permico",
            "Triassic": "triasico", "Jurassic": "jurasico", "Cretaceous": "cretacico",
            "Paleocene": "paleoceno", "Eocene": "eoceno", "Oligocene": "oligoceno",
            "Miocene": "mioceno", "Pliocene": "plioceno", "Pleistocene": "pleistoceno"}  # fmt: skip
_EN_PART = {"early": "E", "lower": "E", "middle": "M", "late": "L", "upper": "L"}
_ES_PART = {"inferior": "E", "temprano": "E", "medio": "M", "superior": "L", "tardio": "L"}
_ES_PART_BEFORE = {"principios": "E", "inicios": "E", "comienzos": "E", "mediados": "M",
                   "finales": "L", "final": "L"}  # fmt: skip


# The North American subperiods of the Carboniferous, as its parts in Spanish.
_SUBPERIODS = {"Mississippian": ("carbonifero", "E"), "Pennsylvanian": ("carbonifero", "L")}


_TERTIARY = {"paleoceno", "eoceno", "oligoceno", "mioceno", "plioceno"}
_WIDER = {
    r"\bPaleogene\b": {"paleoceno", "eoceno", "oligoceno"},
    r"\bNeogene\b": {"mioceno", "plioceno"},
    r"\bTertiary\b": _TERTIARY,
    r"\bEo-Oligocene\b": {"eoceno", "oligoceno"},
}


def _paleo(text: str) -> str:
    return re.sub(r"\bPalaeo", "Paleo", text)  # British spelling: "Palaeocene"


def periods_en(text: str) -> set[str]:
    """Periods and epochs an English sentence names (as in _PERIODS' values)."""
    text = _paleo(text)
    found = {v for k, v in _PERIODS.items() if re.search(rf"\b{k}\b", text)}
    found |= {p for k, (p, _) in _SUBPERIODS.items() if re.search(rf"\b{k}\b", text)}
    for name, epochs in _WIDER.items():  # the K-Pg boundary is the start of the Paleocene
        if re.search(name, text):
            found |= epochs
    return found


def periods_es(text: str) -> set[str]:
    folded = _fold(text)
    return {v for v in _PERIODS.values() if re.search(rf"\b{v}\b", folded)}


def epochs_en(text: str) -> set[tuple[str, str]]:
    """(period, E/M/L) of "Late Cretaceous", "Lower Jurassic", "Pennsylvanian"…"""
    text = _paleo(text)
    names = "|".join(_PERIODS)
    part = r"(?:Early|Lower|Middle|Late|Upper)"
    found = {v for k, v in _SUBPERIODS.items() if re.search(rf"\b{k}\b", text)}
    # Ranges too: "Middle to Late Eocene", "Early or Middle Miocene", "Early-Middle".
    for m in re.finditer(rf"\b({part}(?:\s*(?:to|or|and|-|\u2013)\s*{part})?) ({names})\b", text):
        for q in re.findall(part, m[1]):
            found.add((_PERIODS[m[2]], _EN_PART[q.lower()]))
    return found


def epochs_es(text: str) -> set[tuple[str, str]]:
    """(period, E/M/L) of "Cretácico Superior", "Jurásico tardío", "finales del Triásico"."""
    folded = _fold(text)
    names = "|".join(_PERIODS.values())
    after = re.findall(rf"\b({names})\s+({'|'.join(_ES_PART)})\b", folded)
    before = re.findall(rf"\b({'|'.join(_ES_PART_BEFORE)})\s+del\s+({names})\b", folded)
    return {(p, _ES_PART[q]) for p, q in after} | {(p, _ES_PART_BEFORE[q]) for q, p in before}


# Common names of clades: an adaptation must keep the one of its English sentence and
# not swap it for another ("sauropodomorph" -> "saurópodo").
_CLADE_WORDS = {
    r"\bsauropodomorphs?\b": r"sauropodomorf",
    r"\bsauropods?\b": r"sauropod(?!omorf)",
    r"\btheropods?\b": r"teropod",
    r"\bornithopods?\b": r"ornitopod",
    r"\bplesiosaurs?\b": r"plesiosaur",
    r"\bpliosaurs?\b": r"pliosaur",
    r"\bichthyosaurs?\b": r"ictiosaur",
    r"\bmosasaurs?\b": r"mosasaur",
    r"\bpterosaurs?\b": r"pterosaur",
    r"\bornithischians?\b": r"ornitisqui",
    r"\bsaurischians?\b": r"saurisqui",
    # "hadrosaur" in English is a hadrosaurid; a hadrosaurine is a subfamily
    r"\bhadrosaurs?\b": r"hadrosaur(?!in)",
    r"\bhadrosaurines?\b": r"hadrosaurin",
    r"\bceratopsians?\b": r"ceratops",
    r"\bceratosaurs?\b": r"ceratosaur",
    # an ankylosaur (Ankylosauria) is not an ankylosaurid (one family of it)
    r"\bankylosaurs?\b": r"anquilosaurio",
    r"\bankylosaurids?\b": r"anquilosaurid",
    r"\bstegosaurs?\b": r"estegosaur",
    r"\bcrocodylomorphs?\b": r"cocodrilomorf",
    r"\bcrocodyliforms?\b": r"crocodiliform|cocodriliform",
    r"\barchosaurs?\b": r"arcosaur",
    r"\btyrannosauroids?\b": r"tiranosauroide",
    r"\btyrannosaurids?\b": r"tiranosaurid",
    r"\bdiplodocines?\b": r"diplodocin",
    r"\bdiplodocids?\b": r"diplodocid",
    r"\babelisauroids?\b|\bAbelisauroidea\b": r"abelisauroide",
    r"\babelisaurids?\b|\bAbelisauridae\b": r"abelisaurid",
}


def clade_swaps(src: str, dst: str) -> list[str]:
    """English clade words whose Spanish form is missing while the Spanish sentence
    names another clade of the list that the English one does not."""
    folded = _fold(dst)
    in_src = {en: es for en, es in _CLADE_WORDS.items() if re.search(en, src, re.I)}
    if not in_src:
        return []
    others = [es for en, es in _CLADE_WORDS.items() if en not in in_src and re.search(es, folded)]
    missing = [en for en, es in in_src.items() if not re.search(es, folded)]
    if not (missing and others):
        return []
    return [re.search(en, src, re.I).group(0) for en in missing]  # type: ignore[union-attr]


# Words of the English sentence whose Spanish form must stay (on folded text): animals
# and plants that get swapped for another ("magpie" -> "gorrión", "horsetails" ->
# "helechos"), opposite meanings ("flightless" -> "voladores", "browse" -> "pastar")
# and places ("Missouri" -> "Misisipi"). Found reviewing 15 pages (Phase 7).
_KEEP_WORDS = {
    r"\bmagpies?\b": r"urraca",
    r"\bsparrows?\b": r"gorrion",
    r"\balligators?\b": r"aligator|caiman",
    r"\bcrocodiles?\b": r"cocodrilo",
    r"\bthresher sharks?\b": r"tiburon(?:es)? zorro",
    r"\bhorsetails?\b": r"colas? de caballo|equiset",
    r"\bferns?\b": r"helech",
    r"\bsails?\b": r"\bvelas?\b",
    r"\bhumps?\b": r"joroba",
    r"\bhorns?\b": r"cuerno|cornamenta",
    r"\bantlers?\b": r"\bastas?\b|cornamenta",
    r"\bbrows(?:e|es|ed|er|ers|ing)\b": r"ramone",
    r"\bgraz(?:e|es|ed|er|ers|ing)\b": r"\bpast(?:a|an|ar|aba|aban|o|os|oreo)\b|pastador",
    r"\bflightless\b": r"no volador|incapa\w* de volar|sin capacidad de vuelo|no pod\w* volar",
    r"\bgizzards?\b": r"molleja",
    r"\bamateur\b": r"aficionad",
    r"\bbattering ram\b": r"ariete",
    r"\bMissouri\b": r"misuri|missouri",
    r"\bMississippi\b": r"misisipi|mississippi",
    r"\bMorocco\b": r"marruecos",
    r"\bEgypt\b": r"egipto",
    r"\bGermany\b": r"alemania",
    r"\bEngland\b": r"inglaterra",
    r"\bBrazil\b": r"brasil",
    r"\bSpain\b": r"espana",
    r"\bBelgium\b": r"belgica",
    r"\bJapan\b": r"japon",
    r"\bRussia\b": r"rusia",
    r"\bAntarctica\b": r"antartida",
    r"\bSouth Dakota\b": r"dakota del sur|south dakota",
    r"\bNorth Dakota\b": r"dakota del norte|north dakota",
    r"\bNew Mexico\b": r"nuevo mexico|new mexico",
}
_KEEP_CASE = re.compile(r"^\\b[A-Z]")  # places are matched case-sensitively


def words_lost(src: str, dst: str) -> list[str]:
    """English words of _KEEP_WORDS whose Spanish form is missing. Common words are
    matched in lower case (or capitalised at the start): "North Horn Formation" is a
    name, not a horn."""
    folded = _fold(dst)
    start = src[:1].lower() + src[1:]
    lost = []
    for en, es in _KEEP_WORDS.items():
        text = src if _KEEP_CASE.match(en) else start
        if (m := re.search(en, text)) and not re.search(es, folded):
            lost.append(m.group(0))
    return lost


# A Spanish clade word one rank off, put right when its English sentence names the
# narrower clade (and not the one the Spanish used): same gender and number, so the
# rest of the sentence agrees. "crocodyliform" -> "cocodrilomorfo" -> "crocodiliforme".
_CLADE_FIXES = [
    (r"\bcrocodyliforms?\b", r"\bcrocodylomorphs?\b",
     r"\b([Cc])ocodrilomorfo(s?)\b", r"\1rocodiliforme\2"),
    (r"\btyrannosauroids?\b", r"\btyrannosaurids?\b",
     r"\b([Tt])iranos[aá]urido(s?)\b", r"\1iranosauroideo\2"),
    (r"\bankylosaurs?\b", r"\bankylosaurids?\b",
     r"\b([Aa])nquilos[aá]urido(s?)\b", r"\1nquilosaurio\2"),
    (r"\bceratosaurs?\b", r"\bceratopsids?\b|\bceratopsians?\b",
     r"\b([Cc])erat[oó]psido(s?)\b", r"\1eratosaurio\2"),
    (r"\bhadrosaurines?\b", r"\bhadrosaurids?\b|\bhadrosaurs?\b",
     r"\b([Hh])adros[aá]urido(s?)\b", r"\1adrosaurino\2"),
    (r"\babelisauroids?\b", r"\babelisaurids?\b",
     r"\b([Aa])belis[aá]urido(s?)\b", r"\1belisauroideo\2"),
    (r"\bdiplodocines?\b", r"\bdiplodocids?\b",
     r"\b([Dd])iplod[oó]cido(s?)\b", r"\1iplodocino\2"),
]  # fmt: skip


def fix_clade_rank(src: str, dst: str) -> str:
    """The Spanish sentence with its clade word put at the English sentence's rank."""
    for narrow, other, wrong, right in _CLADE_FIXES:
        if re.search(narrow, src, re.I) and not re.search(other, src, re.I):
            dst = re.sub(wrong, right, dst)
    return dst


# English words that never belong in a Spanish sentence ("noting que los fragmentos").
_EN_ONLY = {"noting", "the", "and", "with", "which", "from", "that", "were", "was", "been",
            "their", "however", "although", "being", "whose", "while", "suggesting"}  # fmt: skip
_QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”|\*[^*]*\*|_[^_]*_")


def english_left(dst: str, src: str = "") -> list[str]:
    """English words left untranslated in a Spanish sentence (quoted titles, italic
    names and words of the English sentence's own proper names aside)."""
    plain = _QUOTED.sub(" ", dst)
    tokens = re.findall(r"[^\W\d_]+", plain)
    src_tokens = " ".join(re.findall(r"[^\W\d_]+", src)).lower()
    left = set()
    for i, w in enumerate(tokens):
        if w.lower() not in _EN_ONLY:
            continue
        # inside an English name or title copied as is ("Garden of the Gods", "The
        # Science of Nature"): the word and a neighbour appear together in the source
        pairs = [tokens[j : j + 2] for j in (i - 1, i) if j >= 0 and j + 1 < len(tokens)]
        if not any(f" {' '.join(p).lower()} " in f" {src_tokens} " for p in pairs):
            left.add(w)
    return sorted(left)


def _epoch_bounds() -> dict[tuple[str, str], tuple[float, float]]:
    """(folded Spanish period, E/M/L) -> (oldest, youngest) Ma, from the ICS table."""
    from paleo.site.terms import TIME_UNITS

    out = {}
    for old, young, en, _ in TIME_UNITS:
        part, _, period = en.partition(" ")
        if period in _PERIODS and part in ("Early", "Middle", "Late"):
            out[(_PERIODS[period], _EN_PART[part.lower()])] = (old, young)
    return out


def _stage_bounds(stage: str) -> tuple[float, float] | None:
    from paleo.ranges import STAGES

    return next(((o, y) for o, y, n in STAGES if n == stage), None)


def _period_of(stage: str) -> str | None:
    """Folded Spanish name of the period a stage belongs to."""
    from paleo.site.terms import TIME_UNITS

    if not (b := _stage_bounds(stage)):
        return None
    for old, young, en, _ in TIME_UNITS:
        if en in _PERIODS and old >= b[0] - 1e-6 and young <= b[1] + 1e-6:
            return _PERIODS[en]
    return None


_CONTRAST = re.compile(
    r"\b(?:while|whereas|originally|thought|suggest\w*|argue\w*|disagree\w*|others?|before"
    r"|after|than|but|instead|rather|re-?dated|mientras|originalmente|se pensaba|sugier\w*"
    r"|antes|despu[eé]s|que el|pero|otros|otras|discrep\w*)\b",
    re.IGNORECASE,
)


def stage_epoch_conflicts(
    stages: set[str], epochs: set[tuple[str, str]], text: str = ""
) -> list[str]:
    """Stages named next to an epoch of their own period that does not contain them:
    "the Cenomanian stage of the Early Cretaceous" (the Cenomanian is Late). Not in a
    sentence that contrasts views or times ("originally thought Late Cretaceous, re-dated
    to the Albian"), where both may be right."""
    if text and _CONTRAST.search(text):
        return []
    bounds = _epoch_bounds()
    out, fits = [], False
    for stage in sorted(stages):
        sb, period = _stage_bounds(stage), _period_of(stage)
        named = [bounds[e] for e in epochs if e[0] == period and e in bounds]
        if not (sb and named):
            continue
        if any(sb[0] > y and sb[1] < o for o, y in named):
            fits = True
        else:
            out.append(stage)
    # "Middle Devonian... from the Givetian to the Frasnian": one stage fits, the
    # sentence is about a range; only a sentence where none fits is wrong.
    return [] if fits else out


def _align_one(src: str, dst: str, scientific_names: set[str]) -> list[str]:
    """What an adapted sentence lost from its source sentence (empty if nothing)."""
    problems = []
    if extra := sorted(stages_es(dst, keep=src) - stages_en(src)):
        problems.append(
            f"stages not in the English sentence {extra} (English: {sorted(stages_en(src))})"
        )
    en_epochs = epochs_en(src)
    if wrong := sorted(
        e for e in epochs_es(dst) - en_epochs if any(p == e[0] for p, _ in en_epochs)
    ):
        problems.append(f"other part of the period {wrong} (English: {sorted(en_epochs)})")
    # a sentence about the Palaeocene adapted as "Eoceno Superior" (found 2026-11-25)
    if (en_periods := periods_en(src)) and (other := sorted(periods_es(dst) - en_periods)):
        problems.append(
            f"period not in the English sentence {other} (English: {sorted(en_periods)})"
        )
    if swapped := clade_swaps(src, dst):
        problems.append(f"clade swapped for another {swapped}")
    if lost := words_lost(src, dst):
        problems.append(f"words not kept {lost}")
    if left := english_left(dst, src):
        problems.append(f"English words left untranslated {left}")
    if wrong := stage_epoch_conflicts(stages_es(dst, keep=src), epochs_es(dst), dst):
        problems.append(f"stage in another part of its period {wrong}")
    # a qualifier the English sentence does not use ("el grupo parafilético")
    folded = _fold(dst)
    qualifiers = {"parafil": "paraphyl", "monofil": "monophyl", "polifil": "polyphyl"}
    if extra := [es for es, en in qualifiers.items() if es in folded and en not in src.lower()]:
        problems.append(f"qualifier not in the English sentence {extra}")
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


# --- The page's own taxon against its age (Phase 7) ---------------------------------

_MA = re.compile(
    r"(\d+(?:\.\d+)?)(?:\s*(?:to|and|or|-|\u2013)\s*(\d+(?:\.\d+)?))?\s*"
    r"(?:million years ago|million years before present|Ma\b|mya\b)",
    re.IGNORECASE,
)
_ABOUT_IT = re.compile(
    r"\b(?:it|its|the genus|the species|fossils?|remains|specimens?|holotype)\b", re.I
)
_WHEN = re.compile(r"\b(?:lived|living|existed|dat(?:e|es|ed|ing)|age|ages|known from"
                   r"|time range|fossil record|stage|stages|epoch|period)\b", re.I)  # fmt: skip


def age_conflicts(text: str, taxon: str, max_ma: float, min_ma: float) -> list[str]:
    """What an English sentence about the taxon's own time says that its age (the
    Wikipedia taxobox) rules out: ages in Ma beyond it, or only stages outside it.
    *Iguanodon* (126-122 Ma) "lived from the Kimmeridgian to the Maastrichtian, 154.8 to
    66 million years ago" (PBDB's range); *Carnotaurus* (69-66) "69 to 64 million years
    ago" (its formation's). Only sentences about the taxon itself are judged."""
    genus = taxon.split()[0]
    if not (_WHEN.search(text) and (genus in text or _ABOUT_IT.search(text))):
        return []
    # Estimates differ by a few million years between sources: only a clear
    # contradiction counts. A range that does not touch the age at all; one far wider
    # than it (PBDB's every-occurrence range); or a Mesozoic animal past 66 Ma.
    slack = 1.0 + 0.1 * (max_ma - min_ma)
    span = max(max_ma - min_ma, 1.0)
    out = []
    for m in _MA.finditer(text):
        values = [float(v) for v in m.groups() if v]
        hi, lo = max(values), min(values)
        # "approximately 125 million years ago": a single figure is a rounded one
        margin = max(slack, 4.0, 0.05 * hi) if len(values) == 1 else slack
        apart = lo > max_ma + margin or hi < min_ma - margin
        too_wide = (
            (hi - lo) > 3 * span
            and (hi - lo) - span > 10
            and (hi > max_ma + slack or lo < min_ma - slack)
        )
        past_kpg = min_ma >= 66.0 and lo < 66.0 - 0.5
        if apart or too_wide or past_kpg:
            out.append(m.group(0))
    stages = stages_en(text)
    bounds = [b for st in stages if (b := _stage_bounds(st))]
    # a single figure in the taxobox is often one species' age (Brodavis: 80.5 Ma, its
    # other species are Maastrichtian): stages are only judged against a real range
    if (
        max_ma - min_ma >= 1
        and bounds
        and not any(o > min_ma - 2 and y < max_ma + 2 for o, y in bounds)
    ):
        out.append(", ".join(sorted(stages)))
    return out


def en_time_problems(text: str, taxon: str, age: tuple[float, float] | None) -> list[str]:
    """Problems of an English sentence with time: a stage in the wrong part of its
    period, or ages and stages the taxon's own age rules out."""
    problems = []
    if wrong := stage_epoch_conflicts(stages_en(text), epochs_en(text), text):
        problems.append(f"stage in another part of its period {wrong}")
    if age and (clash := age_conflicts(text, taxon, *age)):
        problems.append(f"outside the taxon's age {age[0]}-{age[1]} Ma: {clash}")
    return problems


# --- Spanish Wikipedia against the English one (Phase 7) ----------------------------

_BODY_LENGTH = re.compile(
    r"(\d+(?:[.,]\d+)?)(?:\s*(?:to|and|or|-|\u2013)\s*(\d+(?:[.,]\d+)?))?\s*"
    r"(?:meters|metres|m)\b(?:\s+(?:long|in length))?",
    re.IGNORECASE,
)
_PART = re.compile(
    r"\b(?:femur|humerus|tibia|fibula|skull|tooth|teeth|vertebra\w*|bone|ulna|radius|"
    r"scapula|pelvis|ilium|neck|tail|limb|leg|arm|jaw|mandible|claw|crest|frill|horn|"
    r"spine|sail|egg|track|footprint|heights?|tall|high|hip|wing|wingspan)\b",
    re.IGNORECASE,
)


_ATTRIBUTED = re.compile(
    r"\b(?:suggest\w*|propos\w*|according|some|other|later|study|studies|publication|"
    r"researchers?|authors?|argued|considered|juveniles?|hatchlings?|young|subadults?|"
    r"nest\w*|specimens?|species|individuals?|holotype|largest|smallest|maximum|minimum|"
    r"age of|over|more than|at least|exceed\w*)\b"
    r"|\b(?!The\b|This\b|Its\b|An?\b)[A-Z][a-z]+ (?:and \w+ )?"
    r"(?:estimated|suggested|proposed|calculated)\b",
    re.IGNORECASE,
)


def _body_lengths(text: str) -> list[float]:
    """Body lengths in metres a statement gives ("reached 18 to 22 meters long"), not
    the size of a bone, a part, a height or a wingspan."""
    out = []
    # clause by clause: "lengths of 18 to 22 meters and heights of 9.4 to 13 meters"
    for clause in re.split(r";|, | and (?=[^\W\d])", text):
        about_length = re.search(r"\b(?:lengths?|long|measur\w*|reach\w*)\b", clause)
        if _PART.search(clause) or not about_length:
            continue
        for m in _BODY_LENGTH.finditer(clause):
            out += [float(v.replace(",", ".")) for v in m.groups() if v]
    return out


def eswiki_conflicts(sentence: str, cited: list[dict], facts: list[dict]) -> list[str]:
    """An English sentence whose figure comes only from the Spanish Wikipedia while the
    English one, the cited source, gives a clearly different one for the same measure:
    *Brachiosaurus* "26 meters" (eswiki) against 18-22 m (enwiki)."""
    if not cited or not all(":eswiki:" in f.get("chunk_id", "") for f in cited):
        return []
    # An attributed estimate ("Holtz suggested", "some estimates") or the size of a
    # juvenile, a specimen or one species is another figure, not a contradiction.
    if _ATTRIBUTED.search(sentence):
        return []
    said = _body_lengths(sentence)
    english = [v for f in facts if ":enwiki:" in f.get("chunk_id", "")
               for v in _body_lengths(f.get("statement", ""))]  # fmt: skip
    if not said or not english:
        return []
    lo, hi = min(english), max(english)
    if all(v > hi * 1.15 or v < lo * 0.85 for v in said):
        return [f"{said} m from the Spanish Wikipedia; the English one gives {lo}-{hi} m"]
    return []
