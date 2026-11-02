"""The GBIF reconciliation job, defined once (both engines follow it to the letter).

Input
  * GBIF records (simple download, columns lower-cased): gbifid, genus,
    scientificname, verbatimscientificname, family, countrycode, decimallatitude,
    decimallongitude, institutioncode, and issue (GBIF's quality flags: a list in
    Parquet, a ';'-separated string in CSV; optional).
  * PBDB genera of the encyclopedia: taxon_name, family_name.

Reconciliation, per distinct GBIF name (a few thousand), in this order:
  1. ``exact``:    GBIF's interpreted genus is a PBDB genus.
  2. ``synonym``:  the genus of the verbatim (original) name is a PBDB genus: GBIF
                   moved it to another name that PBDB does not use.
  3. ``typo``:     one edit away (Levenshtein <= 1) from exactly one PBDB genus with
                   the same first letter and the same family (or no family known).
  4. otherwise ``unmatched``, with a reason: ``no_name`` or ``not_in_catalog``.

Coordinates: a record flagged with one of COORDINATE_ISSUES (e.g. the point is not
in the country it names) still counts as a specimen, but gives no point on the map.

Outputs (Parquet, rows sorted by their key so both engines write the same bytes of data):
  * genus_specimens: genus, specimens, institutions, countries (codes, most first),
    points (lat/lon rounded to POINT_STEP degrees with their count), by_method,
    top_institutions (the TOP_INSTITUTIONS with most specimens: code and count,
    most first, then by code).
  * institutions: institution_code, specimens, genera.
  * countries: country_code, specimens, genera.
  * unmatched: name, records, reason (the TOP_UNMATCHED commonest).
"""

POINT_STEP = 0.5  # degrees: enough for a world map, small enough to ship
TOP_UNMATCHED = 500
TOP_INSTITUTIONS = 5
METHODS = ("exact", "synonym", "typo")
OUTPUTS = ("genus_specimens", "institutions", "countries", "unmatched")
GBIF_COLUMNS = (
    "gbifid", "genus", "scientificname", "verbatimscientificname", "family",
    "countrycode", "decimallatitude", "decimallongitude", "institutioncode",
)  # fmt: skip
# GBIF flags that make a record's coordinates unusable for the map (the record still counts).
# PRESUMED_NEGATED_* / PRESUMED_SWAPPED_* are not here: GBIF already fixed those coordinates.
COORDINATE_ISSUES = (
    "ZERO_COORDINATE", "COORDINATE_INVALID", "COORDINATE_OUT_OF_RANGE",
    "COUNTRY_COORDINATE_MISMATCH", "CONTINENT_COORDINATE_MISMATCH",
)  # fmt: skip
