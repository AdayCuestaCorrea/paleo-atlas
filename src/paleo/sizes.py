"""Body sizes of the taxa, for the size comparator (ALCANCE §11.3).

A size is only published when a verified fact states it: the facts in
``derived/facts/<taxon>.json`` are sentences already checked against a literal quote of
their source (the Wikipedia article at a given revision). From each fact that talks
about a length, a deterministic rule reads the numbers (ranges, "up to", feet and inches
converted to metres) and throws away what is clearly not the length of a whole adult
body: skulls, bones, teeth, wingspans, juveniles. What the rule cannot decide is labelled
"doubtful" and goes to an LLM, which only answers "adult body length: yes/no" and the
numbers; its numbers must match the rule's reading of the same sentence.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from paleo.store import _atomic_write

FT = 0.3048
INCH = 0.0254
UNITS = {
    "m": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "centimetre": 0.01, "centimetres": 0.01,
    "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "millimetre": 0.001, "millimetres": 0.001,
    "ft": FT, "foot": FT, "feet": FT, "in": INCH, "inch": INCH, "inches": INCH,
}  # fmt: skip
_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = "|".join(sorted(UNITS, key=len, reverse=True))
# "12", "12.3 to 12.8", "between 4 and 5", "4-5", "4\u20135"; then the unit.
LENGTH = re.compile(
    rf"(?:between\s+)?(?P<a>{_NUM})(?:\s*(?:m|cm|mm|ft|feet)?\s*(?:to|and|-|\u2013|\u2014)\s*(?P<b>{_NUM}))?"
    rf"\s*(?P<unit>{_UNIT})\b(?!\s*/\s*s)(?!\w)",
    re.I,
)
# A length mention must be about length: "long", "length", "measuring" near the number.
LENGTHY = re.compile(r"\b(long|length|lengths|longitud|measur\w*|reach\w*|grew|grow\w*)\b", re.I)
# Words that make the number about a part, not the whole body.
PARTS = re.compile(
    r"\b(skull|skulls|cranium|head|jaw|jaws|mandible|snout|rostrum|tooth|teeth|tusk|claw|claws|"
    r"femur|femora|humerus|tibia|fibula|ulna|radius|ilium|ischium|pubis|pelvis|sacrum|scapula|"
    r"coracoid|vertebra|vertebrae|centrum|rib|ribs|spine|spines|sail|plate|plates|spike|spikes|"
    r"horn|horns|frill|crest|neck|tail|arm|arms|leg|legs|hand|foot|feet long bones|limb|limbs|"
    r"wing|wings|wingspan|wingspans|finger|toe|digit|egg|eggs|footprint|footprints|track|tracks|"
    r"trackway|burrow|carapace|plastron|shell|fin|fins|feather|feathers|quill|scale|scales|"
    r"armor|armour|osteoderm|osteoderms|bone|bones|specimen block|slab|nest|filament|filaments|"
    r"pteroid|dentary|maxilla|premaxilla|orbit|metatarsal|metacarpal|phalanx|phalanges|cervical|"
    r"dorsal|caudal|sacral|gastralia|beak|bill|antorbital|fenestra|crown|root|denticle|denticles|"
    r"orbital|tibiotarsus|tarsometatarsus|carpometacarpus|furcula|synsacrum|braincase|quadrate|"
    r"ilia|section)\b",
    re.I,
)
YOUNG = re.compile(
    r"\b(juvenile|juveniles|subadult|sub-adult|hatchling|hatchlings|embryo|embryos|infant|"
    r"baby|babies|young|newborn|neonate|neonates|immature|yearling)\b",
    re.I,
)
UP_TO = re.compile(r"\b(up to|as much as|as long as|maximum|max\.?|largest|at most)\b", re.I)
AT_LEAST = re.compile(r"\b(at least|more than|over|exceed\w*|over)\b", re.I)
OTHER_DIM = re.compile(r"\b(tall|height|high|wide|width|deep|depth|thick|diameter|across)\b", re.I)
MAX_REASONABLE_M = 60.0  # longer than any animal ever described


def to_float(s: str) -> float:
    return float(s.replace(",", "."))


@dataclass
class Reading:
    """One length expression read in a sentence, in metres."""

    min_m: float
    max_m: float
    qualifier: str  # "range" | "about" | "up_to" | "at_least"
    text: str
    unit: str


@dataclass
class Candidate:
    taxon_key: str
    fact_id: str
    statement: str
    quote: str
    chunk_id: str
    readings: list[Reading] = field(default_factory=list)
    status: str = ""  # "accepted" | "rejected" | "doubtful"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}  # fmt: skip
_WORD_NUM = re.compile(rf"\b({'|'.join(WORDS)})(?=[\s-]+(?:{_UNIT})\b)", re.I)
# What follows a number says which dimension it is.
AFTER_LENGTH = re.compile(
    r"^\W{0,3}(?:\w+\W+){0,2}?(long|in (?:total |body |overall )?length)\b", re.I
)
AFTER_OTHER = re.compile(
    r"^\W{0,3}(?:\w+\W+){0,2}?(tall|high|in height|at the (?:hips?|shoulders?)|wide|in width|"
    r"deep|thick|in diameter|across|wingspan|in wingspan)\b",
    re.I,
)
BEFORE_OTHER = re.compile(
    r"\b(height|width|wingspan|depth|diameter|mass|weigh\w*)\s+"
    r"(?:of\s+)?(?:about\s+|around\s+|up to\s+)?$",
    re.I,
)
PARTIAL = re.compile(
    r"\b(fragmentary|fragments?|partial|incomplete|preserved|known only from|single (?:bone|"
    r"vertebra|tooth|femur|specimen))\b",
    re.I,
)
# The sentence questions a figure rather than stating it.
DOUBT = re.compile(
    r"\b(debat\w*|disput\w*|doubt\w*|unlikely|overestimat\w*|underestimat\w*|exaggerat\w*|"
    r"questionable|poorly supported|not supported|unsupported|rejected|refuted|erroneous)\b",
    re.I,
)
# The sentence says the figure is an old one (kept in the list, never the main estimate
# when there are others).
SUPERSEDED = re.compile(
    r"\b(early|earlier|initial|initially|original|originally|historical|historically|"
    r"first estimated|media|news reports?|at the time|once thought|previously|older|old)\b",
    re.I,
)
# A clause ends at these: the part a number is about is named in its own clause.
CLAUSE = re.compile(r"[;,()]|\b(?:and|while|whereas|but|with)\b", re.I)


def normalise(text: str) -> str:
    return _WORD_NUM.sub(lambda m: str(WORDS[m.group(1).lower()]), text)


def readings(text: str) -> list[Reading]:
    """Length expressions of a sentence, with conversions of the same value merged
    ("12 meters (39.7 feet)" is one reading)."""
    text = normalise(text)
    out: list[Reading] = []
    for m in LENGTH.finditer(text):
        unit = m.group("unit").lower()
        if unit == "in" and not re.search(
            r"\d\s*in\b(?!\s+(length|the|a|an|height|width))", m.group(0)
        ):
            continue  # "in" is far more often a preposition than inches
        k = UNITS[unit]
        a = to_float(m.group("a")) * k
        b = to_float(m.group("b")) * k if m.group("b") else a
        before = text[max(0, m.start() - 30) : m.start()]
        qual = "range" if m.group("b") else "about"
        if UP_TO.search(before) and not m.group("b"):
            qual = "up_to"
        elif AT_LEAST.search(before) and not m.group("b"):
            qual = "at_least"
        r = Reading(round(min(a, b), 3), round(max(a, b), 3), qual, m.group(0), unit)
        r.start, r.end = m.start(), m.end()  # type: ignore[attr-defined]
        prev = out[-1] if out else None
        gap = text[prev.end : m.start()] if prev else ""  # type: ignore[attr-defined]
        if prev and re.fullmatch(r"\s*(\(|or|/|,)?\s*(about|approximately|~)?\s*", gap) and \
                abs(prev.max_m - r.max_m) <= 0.05 * max(prev.max_m, r.max_m):  # fmt: skip
            prev.end = m.end()  # type: ignore[attr-defined]
            continue
        out.append(r)
    return out


def dimension(text: str, r: Reading) -> str:
    """'length', 'other' or 'unknown' for one reading, from the words around it."""
    after = text[r.end : r.end + 40]  # type: ignore[attr-defined]
    if AFTER_OTHER.search(after) and not AFTER_LENGTH.search(after):
        return "other"
    if BEFORE_OTHER.search(text[max(0, r.start - 25) : r.start]):  # type: ignore[attr-defined]
        return "other"
    return "length"


def clause(text: str, r: Reading) -> str:
    """The clause around a reading: from the last separator before it to the next after."""
    cuts = [m for m in CLAUSE.finditer(text)]
    lo = max([m.end() for m in cuts if m.end() <= r.start] or [0])  # type: ignore[attr-defined]
    hi = min([m.start() for m in cuts if m.start() >= r.end] or [len(text)])  # type: ignore[attr-defined]
    return text[lo:hi]


SIZE_VERB = (
    r"(?:(?:probably|likely|typically|generally|possibly|usually|also|then)\s+)?"
    r"(?:was|were|is|are|measured|measures|measuring|reached|reaches|"
    r"reaching|grew|grows|attained|averaged|could reach|may have reached|would have reached|"
    r"had (?:an? )?(?:estimated |total |body |maximum )*length|"
    r"(?:is|was|has been|have been) estimated)\b"
)


def subject(statement: str, taxon: str | None) -> bool:
    """Clear form only: the sentence opens with the animal as its subject ("Saurornitholestes
    measured...", "Adult T. rex reached...", "The type species A. giganteus was...") and a
    size verb follows. Anything else ("The humeri of Eurotrochilus measure...",
    "Leedsichthys possessed gill rakers that were...") goes to the model."""
    if not taxon:
        return False
    genus = re.escape(taxon.split()[0])
    name = rf"(?:{genus}|{genus[0]}\.\s?[a-z]+)(?:\s+[a-z]+)?"
    lead = r"^(?:the\s+)?(?:(?:adult|largest|type|known|average|typical)\s+)*(?:species\s+)?"
    return bool(re.match(rf"{lead}{name}(?!'s)\s+{SIZE_VERB}", statement, re.I))


def classify(c: Candidate, taxon: str | None = None) -> Candidate:
    """Accept, reject or leave as doubtful one fact that mentions a length."""
    s = normalise(c.statement)
    every = readings(c.statement)
    if not every:
        c.status, c.reason = "rejected", "no length"
        return c
    if not LENGTHY.search(s):
        c.status, c.reason = "rejected", "no length word"
        return c
    lengths = [r for r in every if dimension(s, r) == "length"]
    whole = re.compile(r"\b(body|total|overall|whole|entire)\b", re.I)
    of_parts = [r for r in lengths if PARTS.search(clause(s, r)) and not whole.search(clause(s, r))]
    body = [r for r in lengths if r not in of_parts]
    c.readings = body
    if not body:
        c.status, c.reason = "rejected", "part or other dimension"
        return c
    if any(r.max_m > MAX_REASONABLE_M for r in body):
        c.status, c.reason = "doubtful", "too long"
        return c
    young, partial = YOUNG.search(s), PARTIAL.search(s) or DOUBT.search(s)
    parts = PARTS.search(s)
    whole = subject(s, taxon)
    if len(body) == 1 and not young and not partial and not parts and whole:
        c.status, c.reason = "accepted", "rule"
    else:
        why = [w for w, hit in (("young", young), ("partial", partial), ("part", parts),
                                ("no subject", not whole)) if hit]  # fmt: skip
        if len(body) > 1:
            why.append(f"{len(body)} lengths")
        c.status, c.reason = "doubtful", ", ".join(why)
    return c


def candidates(facts_doc: dict[str, Any]) -> list[Candidate]:
    out = []
    for f in facts_doc.get("facts", []):
        if LENGTH.search(f["statement"]):
            c = Candidate(
                facts_doc["taxon_key"], f["fact_id"], f["statement"], f["quote"], f["chunk_id"]
            )
            out.append(classify(c, facts_doc.get("taxon")))
    return out


def scan(facts_dir: Path) -> list[Candidate]:
    out = []
    for path in sorted(facts_dir.glob("*.json")):
        out.extend(candidates(json.loads(path.read_text(encoding="utf-8"))))
    return out


# --------------------------------------------------------------------------- LLM labels

BATCH = 25


class SizeLabel(BaseModel):
    index: int
    adult_body_length: bool
    min_m: float | None = None
    max_m: float | None = None


class SizeLabels(BaseModel):
    items: list[SizeLabel]


def labels_path(derived_root: Path) -> Path:
    return derived_root / "sizes" / "labels.json"


def sizes_path(derived_root: Path) -> Path:
    return derived_root / "sizes" / "sizes.json"


def label_key(c: Candidate) -> str:
    return f"{c.taxon_key}:{c.fact_id}"


def input_hash(c: Candidate) -> str:
    return hashlib.sha1(c.statement.encode()).hexdigest()[:12]


def load_labels(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["key"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


def save_json(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(rows, ensure_ascii=False, indent=1) + "\n")


def _matches(value: float, c: Candidate) -> bool:
    """The model's number must be one the sentence states (its own reading, 2 % slack)."""
    ends = [v for r in readings(c.statement) for v in (r.min_m, r.max_m)]
    return any(abs(value - e) <= 0.02 * max(e, 0.001) for e in ends)


def apply_label(c: Candidate, row: dict[str, Any]) -> Candidate:
    """Turn a doubtful candidate into accepted or rejected with the model's answer."""
    if not row["adult_body_length"]:
        c.status, c.reason = "rejected", "llm: not an adult body length"
    elif row["min_m"] is None or row["max_m"] is None:
        c.status, c.reason = "rejected", "llm: no numbers"
    elif not (_matches(row["min_m"], c) and _matches(row["max_m"], c)):
        c.status, c.reason = "rejected", "llm: numbers not in the sentence"
    else:
        lo, hi = sorted((row["min_m"], row["max_m"]))
        qual = (
            "range"
            if lo != hi
            else next((r.qualifier for r in c.readings if r.max_m == hi), "about")
        )
        c.readings = [Reading(lo, hi, qual, "", "m")]
        c.status, c.reason = "accepted", "llm"
    return c


def label_doubtful(llm: Any, cands: list[Candidate], derived_root: Path, names: dict[str, str],
                   limit: int | None = None) -> tuple[int, int]:  # fmt: skip
    """Ask the model about the doubtful candidates not labelled yet (or whose sentence or
    the prompt changed). Returns (asked, left out by the model)."""
    from paleo.narrative.facts import prompt

    system, version = prompt("size_label")
    path = labels_path(derived_root)
    rows = load_labels(path)
    pending = [
        c for c in cands if c.status == "doubtful"
        and not ((r := rows.get(label_key(c))) and r["input_hash"] == input_hash(c)
                 and r["prompt_version"] == version)
    ]  # fmt: skip
    if limit:
        pending = pending[:limit]
    stamp = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    asked = missing = 0
    for start in range(0, len(pending), BATCH):
        batch = pending[start : start + BATCH]
        lines = [f"{i}. [{names.get(c.taxon_key, c.taxon_key)}] {c.statement}"
                 for i, c in enumerate(batch, start=1)]  # fmt: skip
        answer = llm.complete_json(system, "\n".join(lines), SizeLabels, max_tokens=3_000)
        by_index = {item.index: item for item in answer.items}
        for i, c in enumerate(batch, start=1):
            asked += 1
            if i not in by_index:
                missing += 1
                continue
            a = by_index[i]
            rows[label_key(c)] = {
                "key": label_key(c), "adult_body_length": a.adult_body_length,
                "min_m": a.min_m, "max_m": a.max_m, "input_hash": input_hash(c),
                "generator": llm.label, "prompt_version": version, "labelled_at": stamp,
            }  # fmt: skip
        save_json(path, [rows[k] for k in sorted(rows)])  # keep progress if the quota runs out
    return asked, missing


# --------------------------------------------------------------------------- per taxon


def resolve(cands: list[Candidate], derived_root: Path) -> list[Candidate]:
    """Apply the stored model labels to the doubtful candidates (those without a label
    stay doubtful and are not published)."""
    from paleo.narrative.facts import prompt

    _, version = prompt("size_label")
    rows = load_labels(labels_path(derived_root))
    for c in cands:
        r = rows.get(label_key(c))
        if c.status == "doubtful" and r and r["input_hash"] == input_hash(c) \
                and r["prompt_version"] == version:  # fmt: skip
            apply_label(c, r)
    return cands


def taxon_sizes(cands: list[Candidate], facts_dir: Path) -> list[dict[str, Any]]:
    """One row per taxon with an accepted length. The main estimate is the fact whose
    middle value is closest to the median of all the taxon's estimates (robust to an old
    or extreme figure); the others are listed, and the span of all of them is given."""
    by_taxon: dict[str, list[Candidate]] = {}
    for c in cands:
        # A figure the sentence itself questions ("not supported by scientific
        # literature", "it is debated whether...") is never published.
        if c.status == "accepted" and not DOUBT.search(c.statement):
            by_taxon.setdefault(c.taxon_key, []).append(c)
    out = []
    for key, cs in sorted(by_taxon.items()):
        doc = json.loads((facts_dir / f"{key}.json").read_text(encoding="utf-8"))
        cites = doc.get("citations", {})
        est = []
        for c in cs:
            r = (
                c.readings[0]
                if len(c.readings) == 1
                else Reading(
                    min(x.min_m for x in c.readings),
                    max(x.max_m for x in c.readings),
                    "range",
                    "",
                    "m",
                )
            )
            src = cites.get(c.chunk_id, {})
            est.append({
                "fact_id": c.fact_id, "min_m": r.min_m, "max_m": r.max_m,
                "qualifier": r.qualifier, "method": c.reason, "statement": c.statement,
                "quote": c.quote, "chunk_id": c.chunk_id, "source_title": src.get("title"),
                "source_url": src.get("url"), "source_license": src.get("license"),
                "partial_remains": bool(PARTIAL.search(c.statement) or PARTIAL.search(c.quote)),
                "superseded": bool(SUPERSEDED.search(c.statement)),
            })  # fmt: skip
        mids = [(e["min_m"] + e["max_m"]) / 2 for e in est]
        current = [i for i, e in enumerate(est) if not e["superseded"]] or list(range(len(est)))
        med = statistics.median(mids[i] for i in current)
        med_all = statistics.median(mids)  # breaks a tie between two current estimates
        order = sorted(
            range(len(est)),
            key=lambda i: (
                i not in current,
                abs(mids[i] - med),
                abs(mids[i] - med_all),
                est[i]["fact_id"],
            ),
        )
        main = est[order[0]]
        out.append({
            "taxon_key": key, "taxon": doc.get("taxon"),
            "min_m": main["min_m"], "max_m": main["max_m"], "qualifier": main["qualifier"],
            "main_fact_id": main["fact_id"],
            "span_min_m": min(e["min_m"] for e in est), "span_max_m": max(e["max_m"] for e in est),
            "partial_remains": any(e["partial_remains"] for e in est),
            "only_old_estimates": main["superseded"],
            "estimates": [est[i] for i in order],
        })  # fmt: skip
    return out


# --------------------------------------------------------------------------- silhouettes

# PhyloPic's image host answers browsers without CORS headers, so a CSS mask or a canvas
# cannot read its files: the comparator serves its own copies. Only plain vector drawing
# survives the cleaning (served from the site's origin, a script in an SVG would run).
SVG_NS = "http://www.w3.org/2000/svg"
SVG_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "polygon", "polyline", "line"}
SVG_ATTRS = {
    "viewBox", "width", "height", "version", "d", "transform", "fill", "fill-rule",
    "clip-rule", "fill-opacity", "opacity", "stroke", "stroke-width", "cx", "cy", "r", "rx",
    "ry", "x", "y", "x1", "y1", "x2", "y2", "points", "preserveAspectRatio",
}  # fmt: skip


def silhouettes_dir(derived_root: Path) -> Path:
    return derived_root / "silhouettes"


def clean_svg(raw: bytes) -> bytes | None:
    """The drawing of an SVG with nothing else (no metadata, scripts, links, styles or
    foreign content), or None if it holds an element that is not plain drawing."""
    import xml.etree.ElementTree as ET

    text = raw.decode("utf-8", errors="replace")
    # A public DOCTYPE (potrace writes one) is dropped; an internal subset or an entity
    # is never parsed.
    text = re.sub(r"<!DOCTYPE[^>\[]*>", "", text, count=1)
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def clean(node: ET.Element) -> ET.Element | None:
        name = local(node.tag)
        if name in ("metadata", "title", "desc"):
            return None
        if name not in SVG_TAGS:
            raise ValueError(name)
        out = ET.Element(f"{{{SVG_NS}}}{name}")
        for k, v in node.attrib.items():
            if name == "svg" and k in ("width", "height"):
                continue  # the viewBox gives the proportions
            if k in SVG_ATTRS and "url(" not in v and "javascript" not in v.lower():
                out.set(k, v)
        for child in node:
            c = clean(child)
            if c is not None:
                out.append(c)
        return out

    if local(root.tag) != "svg" or "viewBox" not in root.attrib:
        return None
    try:
        tree = clean(root)
    except ValueError:
        return None
    ET.register_namespace("", SVG_NS)
    return ET.tostring(tree, encoding="utf-8")  # type: ignore[arg-type]


def fetch_silhouettes(client: Any, wanted: dict[str, str], derived_root: Path) -> dict[str, int]:
    """Download (once) and clean the silhouettes the comparator draws: uuid -> URL.
    Returns counts: present, downloaded, rejected (not plain drawing), failed."""
    folder = silhouettes_dir(derived_root)
    folder.mkdir(parents=True, exist_ok=True)
    counts = {"present": 0, "downloaded": 0, "rejected": 0, "failed": 0}
    for uuid, url in sorted(wanted.items()):
        if not re.fullmatch(r"[0-9a-f-]{36}", uuid):
            counts["rejected"] += 1
            continue
        path = folder / f"{uuid}.svg"
        if path.exists():
            counts["present"] += 1
            continue
        try:
            r = client.get(url)
            r.raise_for_status()
        except Exception:  # retried on the next run
            counts["failed"] += 1
            continue
        svg = clean_svg(r.content)
        if svg is None:
            counts["rejected"] += 1
            continue
        _atomic_write(path, svg.decode("utf-8") + "\n")
        counts["downloaded"] += 1
    return counts
