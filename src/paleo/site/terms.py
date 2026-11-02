"""Deterministic translation of terms that come in English from the sources.

Geological units follow Spanish conventions (Cretácico Superior, pisos en
-iense); countries use their Spanish names. Anything without a translation is
kept as is and recorded in ``UNTRANSLATED`` so the site report can list it.
"""

from __future__ import annotations

import re

UNTRANSLATED: set[str] = set()

# Epochs and periods, longest first when matching.
_UNITS = {
    "Middle-Late Jurassic": "Jurásico Medio-Superior",
    "Early Cretaceous": "Cretácico Inferior",
    "Late Cretaceous": "Cretácico Superior",
    "Early Jurassic": "Jurásico Inferior",
    "Middle Jurassic": "Jurásico Medio",
    "Late Jurassic": "Jurásico Superior",
    "Early Triassic": "Triásico Inferior",
    "Middle Triassic": "Triásico Medio",
    "Late Triassic": "Triásico Superior",
    "Early Miocene": "Mioceno Inferior",
    "Middle Miocene": "Mioceno Medio",
    "Late Miocene": "Mioceno Superior",
    "Late Pliocene": "Plioceno Superior",
    "Early Pleistocene": "Pleistoceno Inferior",
    "Late Pleistocene": "Pleistoceno Superior",
    "Paleogene": "Paleógeno",
    "Neogene": "Neógeno",
    "Quaternary": "Cuaternario",
    "Cretaceous": "Cretácico",
    "Jurassic": "Jurásico",
    "Triassic": "Triásico",
    "Paleocene": "Paleoceno",
    "Eocene": "Eoceno",
    "Oligocene": "Oligoceno",
    "Miocene": "Mioceno",
    "Pliocene": "Plioceno",
    "Pleistocene": "Pleistoceno",
    "Holocene": "Holoceno",
}

# Stages (ICS) -> Spanish "-iense" forms.
_STAGES = {
    "Aalenian": "Aaleniense", "Albian": "Albiense", "Anisian": "Anisiense",
    "Aptian": "Aptiense", "Aquitanian": "Aquitaniense", "Bajocian": "Bajociense",
    "Barremian": "Barremiense", "Bartonian": "Bartoniense", "Bathonian": "Bathoniense",
    "Berriasian": "Berriasiense", "Burdigalian": "Burdigaliense", "Calabrian": "Calabriense",
    "Callovian": "Calloviense", "Campanian": "Campaniense", "Carnian": "Carniense",
    "Cenomanian": "Cenomaniense", "Chattian": "Chattiense", "Chibanian": "Chibaniense",
    "Coniacian": "Coniaciense", "Danian": "Daniense", "Gelasian": "Gelasiense",
    "Hauterivian": "Hauteriviense", "Hettangian": "Hettangiense",
    "Kimmeridgian": "Kimmeridgiense", "Ladinian": "Ladiniense", "Langhian": "Langhiense",
    "Lutetian": "Luteciense", "Maastrichtian": "Maastrichtiense", "Messinian": "Messiniense",
    "Norian": "Noriense", "Oxfordian": "Oxfordiense", "Piacenzian": "Piacenziense",
    "Pliensbachian": "Pliensbachiense", "Priabonian": "Priaboniense",
    "Rhaetian": "Rhaetiense", "Rupelian": "Rupeliense", "Santonian": "Santoniense",
    "Selandian": "Selandiense", "Serravallian": "Serravalliense",
    "Sinemurian": "Sinemuriense", "Thanetian": "Thanetiense", "Tithonian": "Titoniense",
    "Toarcian": "Toarciense", "Tortonian": "Tortoniense", "Turonian": "Turoniense",
    "Valanginian": "Valanginiense", "Ypresian": "Ypresiense", "Zanclean": "Zancliense",
}  # fmt: skip

_WORDS = {" or ": " o ", " to ": " a ", " and ": " y "}

COUNTRIES_ES = {
    "Antarctica": "Antártida", "Brazil": "Brasil", "Canada": "Canadá",
    "Denmark": "Dinamarca", "Egypt": "Egipto", "Ethiopia": "Etiopía", "Germany": "Alemania",
    "Japan": "Japón", "Mexico": "México", "Morocco": "Marruecos",
    "New Zealand": "Nueva Zelanda", "Niger": "Níger", "Poland": "Polonia",
    "Romania": "Rumanía", "South Korea": "Corea del Sur", "Spain": "España",
    "Taiwan": "Taiwán", "Thailand": "Tailandia", "United Kingdom": "Reino Unido",
    "United States": "Estados Unidos", "Zimbabwe": "Zimbabue", "France": "Francia",
    "Portugal": "Portugal", "Italy": "Italia", "Russia": "Rusia",
    "South Africa": "Sudáfrica", "Tanzania": "Tanzania", "Madagascar": "Madagascar",
    "New Mexico": "Nuevo México", "North Dakota": "Dakota del Norte",
    "South Dakota": "Dakota del Sur",
}  # fmt: skip
# Same name in both languages (not "untranslated").
_SAME = {
    "Argentina", "Australia", "Austria", "China", "Crimea", "India", "Indonesia",
    "Mongolia", "Uruguay", "Alberta", "Arizona", "Colorado", "Montana", "Wyoming",
}  # fmt: skip

GROUPS = {
    "non_avian_dinosaurs": {
        "es": ("dinosaurio no aviano", "Dinosaurios no avianos"),
        "en": ("non-avian dinosaur", "Non-avian dinosaurs"),
    },
    "birds": {"es": ("ave", "Aves"), "en": ("bird", "Birds")},
    "pseudosuchians": {
        "es": ("pseudosuquio", "Pseudosuquios"),
        "en": ("pseudosuchian", "Pseudosuchians"),
    },
    "pterosaurs": {"es": ("pterosaurio", "Pterosaurios"), "en": ("pterosaur", "Pterosaurs")},
    "other_archosaurs": {
        "es": ("arcosaurio", "Otros arcosaurios"),
        "en": ("archosaur", "Other archosaurs"),
    },
}

NOVELTY = {
    # (Spanish text, Spanish grammatical gender of its head noun, English text)
    "new_genus_and_species": ("Nuevo género y especie", "m", "New genus and species"),
    "new_species": ("Nueva especie", "f", "New species"),
    "new_subspecies": ("Nueva subespecie", "f", "New subspecies"),
    "new_genus": ("Nuevo género", "m", "New genus"),
    "new_genus_new_combination": (
        "Nuevo género para una especie ya conocida",
        "m",
        "New genus for a previously named species",
    ),
    "new_combination": ("Nueva combinación", "f", "New combination"),
    "replacement_name": ("Nombre de sustitución", "m", "Replacement name"),
}

STATUS = {
    "valid": {"es": "válido", "en": "valid"},
    "in_press": {"es": "en prensa", "en": "in press"},
    "disputed": {"es": "discutido", "en": "disputed"},
    "nomen_nudum": {"es": "nomen nudum", "en": "nomen nudum"},
    "preprint": {"es": "preprint", "en": "preprint"},
    "junior_synonym": {"es": "sinónimo posterior", "en": "junior synonym"},
}

_UNIT_RE = re.compile("|".join(re.escape(k) for k in sorted(_UNITS, key=len, reverse=True)))
_STAGE_RE = re.compile(r"\b(" + "|".join(_STAGES) + r")\b")
# Substages: Spanish puts the part after the stage, in lowercase.
_PART = {"early": "inferior", "middle": "medio", "late": "superior"}
_SUBSTAGE_RE = re.compile(r"\b(Early|Middle|Late|early|middle|late) (" + "|".join(_STAGES) + r")\b")


def age(text: str | None, lang: str) -> str | None:
    """'Late Cretaceous (Campanian)' -> 'Cretácico Superior (Campaniense)' in Spanish."""
    if not text or lang == "en":
        return text
    out = _UNIT_RE.sub(lambda m: _UNITS[m.group(0)], text)
    # Substages: "Late Campanian" -> "Campaniense superior".
    out = _SUBSTAGE_RE.sub(lambda m: f"{_STAGES[m.group(2)]} {_PART[m.group(1).lower()]}", out)
    out = _STAGE_RE.sub(lambda m: _STAGES[m.group(0)], out)
    for en, es in _WORDS.items():
        out = out.replace(en, es)
    if re.search(r"\b[A-Z][a-z]+(?:ian|ene|ic)\b", out):
        UNTRANSLATED.add(text)
    return out


def interval(name: str | None, lang: str) -> str | None:
    """A single PBDB interval name ('Campanian', 'Late Pleistocene')."""
    return age(name, lang)


def _country_rows() -> list[dict[str, str]]:
    """Every PBDB country with its English and Spanish names (dbt seed countries.csv)."""
    import csv

    from paleo.config import project_root

    path = project_root() / "dbt" / "seeds" / "countries.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


_COUNTRY_CODES = {r["country_code"].lower(): (r["name_en"], r["name_es"]) for r in _country_rows()}
COUNTRIES_ES.update({en: es for en, es in _COUNTRY_CODES.values() if en not in COUNTRIES_ES})


def country_name(code: str, lang: str) -> str:
    """Name of a PBDB country code ("ar", "uk", "o2"…) in ``lang``."""
    en, es = _COUNTRY_CODES.get(code.lower(), (code.upper(), code.upper()))
    return es if lang == "es" else en


def place(name: str | None, lang: str) -> str | None:
    if not name or lang == "en":
        return name
    if name in COUNTRIES_ES:
        return COUNTRIES_ES[name]
    if name not in _SAME:
        UNTRANSLATED.add(name)
    return name


def locality(name: str | None, lang: str) -> str | None:
    """'Dinosaur Park Formation' -> 'Formación Dinosaur Park' in Spanish."""
    if not name or lang == "en":
        return name
    for suffix, prefix in ((" Formation", "Formación "), (" Member", "Miembro ")):
        if name.endswith(suffix):
            return prefix + name[: -len(suffix)]
    return name


def group(key: str | None, lang: str, plural: bool = False) -> str | None:
    entry = GROUPS.get(key or "")
    return entry[lang][1 if plural else 0] if entry else None


def novelty(key: str | None, lang: str) -> tuple[str, str] | None:
    """(text, gender) of a normalized novelty; gender only matters in Spanish."""
    entry = NOVELTY.get(key or "")
    if not entry:
        return None
    return (entry[0], entry[1]) if lang == "es" else (entry[2], "n")


def status(key: str | None, lang: str) -> str | None:
    entry = STATUS.get(key or "")
    return entry[lang] if entry else None


# --------------------------------------------------------------------- search
# Spanish and English forms of scientific names, so a search for "abelisáuridos"
# or "espinosaurio" finds Abelisauridae or Spinosaurus. Generated by rules (the
# search ignores accents, so these forms carry none).

_CLADE_SUFFIXES = [  # latin suffix, Spanish, English
    ("idae", "idos", "ids"),
    ("inae", "inos", "ines"),
    ("oidea", "oideos", "oids"),
    ("iformes", "iformes", "iforms"),
    ("ini", "inos", "ins"),
]

# A few common names that no rule can derive.
COMMON_NAMES = {
    "Dromaeosauridae": ["raptor", "raptores", "raptors"],
    "Hadrosauridae": ["pico de pato", "duck-billed"],
    "Tyrannosauridae": ["tiranosaurio", "tyrannosaur"],
    "Crocodylia": ["cocodrilo", "crocodile"],
    "Gavialidae": ["gavial", "gharial"],
    "Alligatoridae": ["caiman", "aligator", "alligator"],
    "Pterosauria": ["pterodactilo", "pterodactyl"],
    "Ornithischia": ["ornitisquio", "ornithischian"],
    "Saurischia": ["saurisquio", "saurischian"],
}


def hispanize(word: str) -> str:
    """Latin spelling to Spanish spelling: Tyrannosaurus -> tiranosaurus,
    Spinosaurus -> espinosaurus, Pachycephalo- -> paquicefalo-."""
    w = word.lower()
    for old, new in (("ae", "e"), ("oe", "e"), ("ph", "f"), ("th", "t"), ("rh", "r"), ("y", "i")):
        w = w.replace(old, new)
    w = re.sub(r"ch(?=[ei])", "qu", w).replace("ch", "c")
    w = re.sub(r"([a-z])\1", r"\1", w.replace("ll", "\0")).replace("\0", "ll")  # nn -> n
    if re.match(r"s[bcdfgklmnpqtv]", w):
        w = "e" + w  # Spinosaurus -> espinosaurio
    return w


def clade_aliases(name: str | None) -> list[str]:
    """Abelisauridae -> ["abelisauridos", "abelisaurids"] plus common names."""
    if not name:
        return []
    out = list(COMMON_NAMES.get(name, []))
    for latin, es, en in _CLADE_SUFFIXES:
        if name.endswith(latin) and len(name) > len(latin) + 2:
            stem = name[: -len(latin)]
            out += [hispanize(stem) + es, stem.lower() + en]
            break
    return out


def genus_aliases(genus: str | None) -> list[str]:
    """Spinosaurus -> ["espinosaurio", "spinosaur"]."""
    if not genus:
        return []
    if genus.endswith("saurus"):
        stem = genus[: -len("saurus")]
        return [hispanize(stem) + "saurio", stem.lower() + "saur"]
    if genus.endswith("suchus"):
        return [hispanize(genus[: -len("suchus")]) + "suco"]
    spanish = hispanize(genus)
    return [spanish] if spanish != genus.lower() else []


# Periods and epochs by age (Ma, ICS 2023), so taxa dated only by a stage
# ("Maastrichtian") or by PBDB ranges are found by "Cretácico".
TIME_UNITS = [  # (oldest Ma, youngest Ma, English, Spanish)
    (251.902, 201.4, "Triassic", "Triásico"),
    (251.902, 247.2, "Early Triassic", "Triásico Inferior"),
    (247.2, 237.0, "Middle Triassic", "Triásico Medio"),
    (237.0, 201.4, "Late Triassic", "Triásico Superior"),
    (201.4, 145.0, "Jurassic", "Jurásico"),
    (201.4, 174.7, "Early Jurassic", "Jurásico Inferior"),
    (174.7, 161.5, "Middle Jurassic", "Jurásico Medio"),
    (161.5, 145.0, "Late Jurassic", "Jurásico Superior"),
    (145.0, 66.0, "Cretaceous", "Cretácico"),
    (145.0, 100.5, "Early Cretaceous", "Cretácico Inferior"),
    (100.5, 66.0, "Late Cretaceous", "Cretácico Superior"),
    (66.0, 23.03, "Paleogene", "Paleógeno"),
    (66.0, 56.0, "Paleocene", "Paleoceno"),
    (56.0, 33.9, "Eocene", "Eoceno"),
    (33.9, 23.03, "Oligocene", "Oligoceno"),
    (23.03, 2.58, "Neogene", "Neógeno"),
    (23.03, 5.333, "Miocene", "Mioceno"),
    (5.333, 2.58, "Pliocene", "Plioceno"),
    (2.58, 0.0, "Quaternary", "Cuaternario"),
    (2.58, 0.0117, "Pleistocene", "Pleistoceno"),
    (0.0117, 0.0, "Holocene", "Holoceno"),
]


PERIODS = {"Triassic", "Jurassic", "Cretaceous", "Paleogene", "Neogene", "Quaternary"}


def time_units(max_ma: float | None, min_ma: float | None) -> list[tuple[str, str]]:
    """(English, Spanish) names of the periods and epochs a range overlaps."""
    if max_ma is None:
        return []
    low = min_ma if min_ma is not None else max_ma
    return [(en, es) for old, young, en, es in TIME_UNITS if max_ma > young and low < old]
