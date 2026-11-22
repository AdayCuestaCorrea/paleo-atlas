"""The taxobox age (paleo.ranges) and the short classification line."""

from paleo.ranges import parse_fossil_range
from paleo.site import terms


def box(fossil_range: str, before: str = "") -> str:
    body = f"{{{{Automatic taxobox\n| fossil_range = {fossil_range}\n| taxon = X\n}}}}"
    return f"{before}{body}\nText."


def test_numbers_and_stage_names_of_the_taxobox():
    r = parse_fossil_range(box(
        "[[Late Jurassic]] ([[Kimmeridgian]] to [[Tithonian]]), "
        "{{Fossil range|155|145|latest=145}}{{Period fossil range|Jurassic|155|145}}"
    ))  # fmt: skip
    assert (r["max_ma"], r["min_ma"]) == (155.0, 145.0)
    assert (r["early_interval"], r["late_interval"]) == ("Kimmeridgian", "Tithonian")


def test_doubtful_records_are_left_out():
    r = parse_fossil_range(box(
        "[[Late Cretaceous]]<br />(late [[Maastrichtian]]), {{Fossil range|earliest=77|69|66}}"
        " Possible middle [[Campanian]] record"
    ))  # fmt: skip
    assert (r["max_ma"], r["min_ma"]) == (69.0, 66.0)
    assert r["early_interval"] == r["late_interval"] == "Late Maastrichtian"


def test_stage_names_in_place_of_numbers():
    r = parse_fossil_range(box(
        "[[Late Cretaceous]],<br />{{Fossil range|earliest=Albian|Cenomanian|Cenomanian|"
        "[[Cenomanian]] (possible [[Albian]] records)}}"
    ))  # fmt: skip
    assert (r["max_ma"], r["min_ma"]) == (100.5, 93.9)
    assert r["early_interval"] == "Cenomanian"


def test_epochs_only_and_unparsable_boxes():
    r = parse_fossil_range(box("[[Upper Cretaceous]]"))
    assert (r["max_ma"], r["min_ma"], r["early_interval"]) == (100.5, 66.0, None)
    r = parse_fossil_range(box("{{fossil_range|Quaternary}}"))
    assert (r["max_ma"], r["min_ma"]) == (2.58, 0.0)
    assert parse_fossil_range(box("unknown")) is None
    assert parse_fossil_range("No taxobox here.") is None


def test_a_taxobox_the_parser_cannot_close_is_read_from_its_lines():
    broken = "{{Use mdy dates|date=September 2026}}\n{{good article"  # never closed
    r = parse_fossil_range(box("[[Late Cretaceous]] ([[Maastrichtian]]), {{Fossil range|70|66}}",
                               before=broken + "\n"))  # fmt: skip
    assert (r["max_ma"], r["min_ma"], r["early_interval"]) == (70.0, 66.0, "Maastrichtian")


def test_short_lineage_names_well_known_clades_when_pbdb_has_no_order():
    lineage = [{"name": n} for n in ["Archosauria", "Dinosauria", "Theropoda", "Tetanurae",
                                     "Dromaeosauridae"]]  # fmt: skip
    taxon = {"family_name": "Dromaeosauridae", "order_name": None, "class_name": "Reptilia",
             "classification": lineage}  # fmt: skip
    assert terms.short_lineage(taxon) == ["Dromaeosauridae", "Theropoda", "Dinosauria"]
    taxon.update(order_name="Plesiosauria", family_name="Elasmosauridae")
    assert terms.short_lineage(taxon) == ["Elasmosauridae", "Plesiosauria", "Reptilia"]
