"""Recognizing scientific names in free text (file names, prose).

A heuristic, not a taxonomy: capitalized words with suffixes that are common in
vertebrate palaeontology ("-saurus", "-suchus", "-raptor"...). "-ia" is left
out on purpose: it would catch place names such as Patagonia.
"""

from __future__ import annotations

import re

GENUS_LIKE = re.compile(
    r"\b[A-Z][a-z]+(?:saurus|suchus|raptor|mimus|nyx|odon|don|ops|ornis|pteryx|titan|"
    r"venator|venatrix|lophus|ceratops|therium|ichthys|dactylus|gnathus|cephalus|rhynchus|"
    r"pterus|long|tops|lestes|ichnus|chelys|avis|osteus|onyx|cetus|dracon|spinus)\b"
)


# A latin-looking species epithet, and bone names that look latin but are not.
_EPITHET = re.compile(r"[a-z]{3,}(?:us|um|is|ae|ii|i|a|ans|ens|ax|ex|ix|yx|ops)")
_ANATOMY = {
    "vertebra", "maxilla", "premaxilla", "tibia", "fibula", "ulna", "scapula", "mandibula",
    "humerus", "radius", "ilium", "ischium", "pubis", "sacrum", "cranium", "tarsus",
    "metatarsus", "carpus", "astragalus", "calcaneum", "holotypus", "fauna", "media",
}  # fmt: skip


def mentions_other_taxon(text: str, taxon: str) -> bool:
    """True if ``text`` names a genus other than the taxon's, or another species
    of the same genus ("Spinosaurus aegyptiacus" on the page of S. mirabilis)."""
    genus, _, epithet = taxon.partition(" ")
    for match in GENUS_LIKE.finditer(text):
        if match.group(0) != genus:
            return True
        following = re.match(r"[\s_]+([a-z]+)", text[match.end() :])
        other = following.group(1) if following else ""
        if epithet and other != epithet and _EPITHET.fullmatch(other) and other not in _ANATOMY:
            return True
    return False
