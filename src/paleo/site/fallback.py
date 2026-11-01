"""Fallback text of a taxon page, built only from structured fields (§11.4).

Used when there is no verified narrative text yet. No LLM involved: every word
comes from the data, and each part is left out when its field is missing.
"""

from __future__ import annotations

from typing import Any

from paleo.site import terms


def _join(items: list[str], lang: str) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    conj = " y " if lang == "es" else " and "
    return ", ".join(items[:-1]) + conj + items[-1]


def fallback_text(taxon: dict[str, Any], lang: str) -> str | None:
    """One sentence such as "Nuevo género y especie de dinosaurio no aviano del
    Cretácico Superior (Campaniense) de la Formación Dinosaur Park, en Canadá,
    descrito por Holmes et al. en 2026." Returns None for known taxa."""
    if taxon.get("page_type") != "new":
        return None
    nov = terms.novelty(taxon.get("novelty"), lang)
    group = terms.group(taxon.get("taxon_group"), lang)
    age = terms.age(taxon.get("age_text"), lang)
    loc = terms.locality(taxon.get("type_locality"), lang)
    countries = [terms.place(c, lang) for c in taxon.get("countries") or []]
    regions = [terms.place(r, lang) for r in taxon.get("regions") or []]
    where = _join(countries, lang)
    if where and regions:
        where += f" ({_join(regions, lang)})"
    authors = taxon.get("name_authors")
    year = taxon.get("naming_year")

    if lang == "es":
        head, gender = nov if nov else ("Nuevo taxón", "m")
        parts = [head]
        if group:
            parts.append(f"de {group}")
        if age:
            parts.append(f"del {age}")
        if loc:
            parts.append(f"de la {loc}" if loc.startswith("Formación") else f"de {loc}")
        sentence = " ".join(parts)
        if where:
            sentence += f", en {where}"
        if authors:
            participle = "descrita" if gender == "f" else "descrito"
            sentence += f", {participle} por {authors}"
            if year:
                sentence += f" en {year}"
        return sentence + "."

    head = nov[0] if nov else "New taxon"
    parts = [head]
    if group:
        parts.append(f"of {group}")
    if age:
        parts.append(f"from the {age}")
    if loc:
        parts.append(f"of the {loc}" if loc.endswith("Formation") else f"of {loc}")
    sentence = " ".join(parts)
    if where:
        sentence += f", {where}"
    if authors:
        sentence += f", described by {authors}"
        if year:
            sentence += f" in {year}"
    return sentence + "."
