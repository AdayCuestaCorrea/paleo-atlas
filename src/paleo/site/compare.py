"""Size comparator (ALCANCE.md §11.3): numbers and sentences for the card on a taxon
page, and the index the comparator's window and page load (es/comparar.json,
en/compare.json). The drawing itself is site/static/compare.js."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

PERSON_M = 1.761  # average man of the reference seed (NCD-RisC, Spain, age 19, 2019)
HASH = {"es": "comparar", "en": "compare"}
DASH = chr(0x2013)  # en dash between the two ends of a range
OWN_SHAPES = ("person", "bus", "house", "hoop")


def fmt_len(v: float, lang: str) -> str:
    """'42 cm', '2,07 m' / '2.07 m', '13 m': centimetres under a metre, otherwise up to two
    decimals under 10 m and one above."""
    if v < 1:
        return f"{round(v * 100):g} cm"
    s = f"{round(v, 2 if v < 10 else 1):g}"
    return (s.replace(".", ",") if lang == "es" else s) + " m"


def fmt_range(lo: float, hi: float, qualifier: str, lang: str) -> str:
    if lo == hi:
        prefix = {
            "up_to": {"es": "hasta ", "en": "up to "},
            "at_least": {"es": "más de ", "en": "over "},
        }.get(qualifier, {}).get(lang, "")
        return prefix + fmt_len(hi, lang)
    if hi < 1:
        return f"{round(lo * 100):g}{DASH}{fmt_len(hi, lang)}"
    return f"{fmt_len(lo, lang).removesuffix(' m').removesuffix(' cm')}{DASH}{fmt_len(hi, lang)}"


def phrase(lo: float, hi: float, lang: str) -> str:
    """A deterministic sentence for the card, in people lying in a row (or a fraction of
    a person's height for the small ones)."""
    a, b = round(lo / PERSON_M), round(hi / PERSON_M)
    if hi >= 2.6:
        n = (f"unos {b}" if lang == "es" else f"about {b}") if a == b else (
            f"{a} o {b}" if lang == "es" else f"{a} or {b}")  # fmt: skip
        if lang == "es":
            s = f"Medía lo que {n} hombres promedio tumbados en fila"
            if hi >= 10 and lo <= 13.5:
                s += ": como un autobús"
            elif hi > 13.5:
                s += ": más que un autobús"
        else:
            s = f"As long as {n} average men lying head to toe"
            if hi >= 10 and lo <= 13.5:
                s += ": about a bus"
            elif hi > 13.5:
                s += ": longer than a bus"
        return s + "."
    if hi >= 1.3:
        return ("Medía de largo más o menos lo que mide de alto una persona." if lang == "es"
                else "About as long as a person is tall.")  # fmt: skip
    f = hi / PERSON_M
    if lang == "es":
        frac = ("menos de un tercio" if f <= 0.3 else "menos de la mitad" if f <= 0.55
                else "unas tres cuartas partes" if f <= 0.8 else "casi lo mismo")  # fmt: skip
        return f"De la cabeza a la cola, {frac} de lo que mide de alto un hombre promedio."
    frac = ("less than a third" if f <= 0.3 else "less than half" if f <= 0.55
            else "about three quarters" if f <= 0.8 else "almost as much")  # fmt: skip
    return f"Head to tail, {frac} of an average man's height."


def sil_url(static: str, uuid: str) -> str:
    """The site's own clean copy of a PhyloPic silhouette (paleo sizes silhouettes)."""
    return f"{static}/sil/{uuid}.svg"


def taxon_entry(row: dict[str, Any], name: str, url: str, static: str) -> dict[str, Any]:
    """One taxon of the index: short keys, since the index lists every taxon."""
    main = row["estimates"][0]
    return {
        "k": row["taxon_key"], "n": name, "u": url,
        "lo": row["min_m"], "hi": row["max_m"], "q": row["qualifier"],
        "s": sil_url(static, row["silhouette_uuid"]), "a": row["silhouette_aspect"],
        "lv": row["silhouette_level"], "nd": row["silhouette_node"],
        "au": row["silhouette_author"], "li": row["silhouette_license"],
        "lu": row["silhouette_license_url"], "pg": row["silhouette_page_url"],
        "st": (main.get("source_title") or "").split(" (")[0], "su": main.get("source_url"),
        "qt": main.get("quote"),
        "sp": [row["span_min_m"], row["span_max_m"]], "ne": row["estimate_count"],
        "pr": bool(row["partial_remains"]), "old": bool(row["only_old_estimates"]),
    }  # fmt: skip


def ref_entry(ref: dict[str, Any], lang: str, static: str) -> dict[str, Any]:
    own = bool(ref.get("shape"))
    uuid = ref.get("phylopic_uuid")
    return {
        "k": ref["ref_id"], "kind": ref["kind"], "n": ref[f"name_{lang}"], "ax": ref["axis"],
        "lo": ref["min_m"], "hi": ref["max_m"],
        "box": [ref["box_w_m"], ref["box_h_m"]] if own else None,
        "s": f"{static}/compare/{ref['shape']}.svg" if own
        else sil_url(static, uuid),
        "a": None if own else ref["silhouette_aspect"],
        "au": ref.get("silhouette_author") or None, "li": ref.get("silhouette_license"),
        "lu": ref.get("silhouette_license_url"),
        "pg": None if own else f"https://www.phylopic.org/images/{uuid}",
        "st": ref["source_title"], "su": ref["source_url"], "note": ref[f"source_note_{lang}"],
    }  # fmt: skip


LABELS = (
    "cmp_title", "cmp_min", "cmp_max", "cmp_sizes", "cmp_reset", "cmp_reset_done",
    "cmp_copy", "cmp_copied", "cmp_close", "cmp_hint", "cmp_records", "cmp_longest",
    "cmp_smallest", "cmp_add", "cmp_search", "cmp_more", "cmp_kind_taxon", "cmp_kind_people",
    "cmp_kind_animals", "cmp_kind_objects", "cmp_remove", "cmp_long", "cmp_tall",
    "cmp_height_approx", "cmp_sil_taxon", "cmp_sil_genus", "cmp_sil_clade", "cmp_sil_group",
    "cmp_sil_proxy", "cmp_sil_own", "cmp_source", "cmp_estimates", "cmp_partial", "cmp_old",
    "cmp_error", "cmp_warn", "cmp_history", "cmp_max_items", "cmp_aria", "cmp_measure",
    "cmp_page", "cmp_details", "cmp_none",
)  # fmt: skip


def build_compare(
    sizes: dict[str, dict[str, Any]], refs: list[dict[str, Any]], names: dict[str, str],
    lang: str, url_of: Callable[[str], str], static: str, labels: dict[str, str],
    available: set[str],
) -> dict[str, Any]:  # fmt: skip
    """The index of one language: every taxon whose silhouette the site serves
    (``available``: uuids with a clean copy) and the references that can be drawn."""
    taxa = [
        taxon_entry(row, names.get(key, key), url_of(key), static)
        for key, row in sorted(sizes.items(), key=lambda kv: names.get(kv[0], kv[0]))
        if row.get("in_comparator") and row.get("silhouette_uuid") in available
    ]
    refs = [r for r in refs if r.get("shape") or r.get("phylopic_uuid") in available]
    return {
        "lang": lang, "hash": HASH[lang], "person": PERSON_M,
        "taxa": taxa, "refs": [ref_entry(r, lang, static) for r in refs],
        "labels": {k: labels[k] for k in LABELS},
    }  # fmt: skip
