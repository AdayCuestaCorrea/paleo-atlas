"""Fallback text of a taxon page, built only from structured fields (§11.4).

Used when there is no verified narrative text yet. No LLM involved: every word
comes from the data, and each part is left out when its field is missing.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

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
    descrito por Holmes et al. en 2026." Known taxa get a sentence from PBDB."""
    if taxon.get("page_type") != "new":
        return _known_text(taxon, lang)
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


_RANKS = {  # rank -> (Spanish, gender, English)
    "genus": ("Género", "m", "Genus"),
    "species": ("Especie", "f", "Species"),
    "subspecies": ("Subespecie", "f", "Subspecies"),
}


def _ma(value: float | None, lang: str) -> str | None:
    if value is None:
        return None
    text = f"{value:g}"
    return text.replace(".", ",") if lang == "es" else text


def _known_text(taxon: dict[str, Any], lang: str) -> str | None:
    """ "Género de dinosaurio no aviano de la familia Tyrannosauridae, que vivió del
    Campaniense al Maastrichtiense (hace 83,6 a 66 millones de años)."""
    rank = _RANKS.get(taxon.get("taxon_rank") or "")
    group = terms.group(taxon.get("taxon_group"), lang)
    if not rank or not group:
        return None
    family = taxon.get("family_name")
    early = terms.interval(taxon.get("early_interval"), lang)
    late = terms.interval(taxon.get("late_interval"), lang) or early
    oldest = _ma(taxon.get("first_appearance_max_ma"), lang)
    youngest = _ma(taxon.get("last_appearance_min_ma"), lang)
    if lang == "es":
        sentence = f"{rank[0]} de {group}"
        if family:
            sentence += f" de la familia {family}"
        if early:
            span = f"en el {early}" if early == late else f"del {early} al {late}"
            sentence += f", que vivió {span}"
            if oldest and youngest:
                sentence += f" (hace {oldest} a {youngest} millones de años)"
        return sentence + "."
    sentence = f"{rank[2]} of {group}"
    if family:
        sentence += f" in the family {family}"
    if early:
        span = f"in the {early}" if early == late else f"from the {early} to the {late}"
        sentence += f", which lived {span}"
        if oldest and youngest:
            sentence += f" ({oldest} to {youngest} million years ago)"
    return sentence + "."


def _wiki_url(lang: str, title: str) -> str:
    return f"https://{lang}.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))


def basic_sources(
    taxon: dict[str, Any], events: list[dict[str, Any]], year_page: str, lang: str = "en"
) -> list[dict[str, str]]:
    """Sources of a page without narrative text: the Wikipedia yearly page, PBDB and
    the naming study, so the sources are always visible (§11.1). An encyclopedia
    genus only cites the yearly page when a study of that page is about it."""
    out = []
    if taxon.get("page_type") != "genus" or events:
        out.append({
            "title": f"Wikipedia: {year_page}",
            "url": "https://en.wikipedia.org/wiki/" + year_page.replace(" ", "_"),
            "note": "CC BY-SA 4.0",
        })  # fmt: skip
    # The taxon's own article (verified against PBDB for the encyclopedia genera).
    es_title, en_title = taxon.get("wikipedia_article_es"), taxon.get("wikipedia_article")
    if lang == "es" and es_title:
        out.append({"title": f"Wikipedia: {es_title}", "url": _wiki_url("es", es_title),
                    "note": "CC BY-SA 4.0"})  # fmt: skip
    elif en_title:
        out.append({"title": f"Wikipedia: {en_title}", "url": _wiki_url("en", en_title),
                    "note": "CC BY-SA 4.0"})  # fmt: skip
    if taxon.get("pbdb_has_taxon") and taxon.get("pbdb_taxon_no"):
        out.append({
            "title": f"Paleobiology Database: {taxon['taxon_name']}",
            "url": "https://paleobiodb.org/classic/basicTaxonInfo?taxon_no="
            + str(taxon["pbdb_taxon_no"]).removeprefix("txn:"),
            "note": "CC BY 4.0",
        })  # fmt: skip
    for e in events:
        if e.get("doi"):
            out.append({"title": e.get("title") or e["doi"], "url": f"https://doi.org/{e['doi']}",
                        "note": f"DOI {e['doi']}"})  # fmt: skip
    seen: set[str] = set()
    return [s for s in out if not (s["url"] in seen or seen.add(s["url"]))]
