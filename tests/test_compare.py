"""Size comparator: the card's numbers and sentence, and the index (site/compare.py)."""

from paleo.site import compare

D = compare.DASH


def test_lengths_and_ranges_in_both_languages():
    assert compare.fmt_len(0.42, "es") == "42 cm"
    assert compare.fmt_len(2.07, "es") == "2,07 m" and compare.fmt_len(2.07, "en") == "2.07 m"
    assert compare.fmt_len(12.83, "en") == "12.8 m"
    assert compare.fmt_range(11.1, 13, "range", "es") == f"11,1{D}13 m"
    assert compare.fmt_range(0.42, 0.83, "range", "en") == f"42{D}83 cm"
    assert compare.fmt_range(13, 13, "up_to", "es") == "hasta 13 m"
    assert compare.fmt_range(12, 12, "at_least", "en") == "over 12 m"


def test_the_sentence_counts_average_men_or_a_fraction_of_one():
    assert compare.phrase(11.1, 13, "es").startswith("Medía lo que 6 o 7 hombres promedio")
    assert "autobús" in compare.phrase(11.1, 13, "es")
    assert compare.phrase(30, 37, "en").endswith("longer than a bus.")
    assert "menos de la mitad" in compare.phrase(0.42, 0.83, "es")
    assert compare.phrase(1.5, 2.07, "en") == "About as long as a person is tall."


def test_the_index_lists_drawable_taxa_and_references_only():
    row = {
        "taxon_key": "trex", "min_m": 12.3, "max_m": 12.8, "qualifier": "range",
        "silhouette_uuid": "u1", "silhouette_aspect": 0.32, "silhouette_level": "taxon",
        "silhouette_node": "Tyrannosaurus", "silhouette_author": "Conty",
        "silhouette_license": "CC BY 3.0", "silhouette_license_url": "https://cc/by",
        "silhouette_page_url": "https://phylopic/u1", "span_min_m": 10.7, "span_max_m": 13,
        "estimate_count": 2, "partial_remains": False, "only_old_estimates": False,
        "in_comparator": True,
        "estimates": [{"source_title": "Tyrannosaurus (introduction)", "source_url": "https://w",
                       "quote": "q"}],
    }  # fmt: skip
    no_file = {**row, "taxon_key": "other", "silhouette_uuid": "u2"}
    refs = [
        {"ref_id": "man", "kind": "people", "name_es": "Hombre promedio", "name_en": "Average man",
         "axis": "height", "min_m": 1.761, "max_m": 1.761, "box_w_m": 0.56, "box_h_m": 1.761,
         "shape": "person", "phylopic_uuid": None, "source_title": "NCD-RisC",
         "source_url": "https://doi", "source_note_es": "a", "source_note_en": "b"},
        {"ref_id": "elephant", "kind": "animals", "name_es": "Elefante", "name_en": "Elephant",
         "axis": "height", "min_m": 3.04, "max_m": 3.36, "box_w_m": None, "box_h_m": None,
         "shape": None, "phylopic_uuid": "u9", "silhouette_aspect": 0.93,
         "source_title": "W", "source_url": "https://w", "source_note_es": "a",
         "source_note_en": "b"},
    ]  # fmt: skip
    labels = {k: k for k in compare.LABELS}
    ix = compare.build_compare(
        {"trex": row, "other": no_file}, refs, {"trex": "Tyrannosaurus"}, "en",
        lambda k: f"/en/taxa/{k}.html", "/pa/static", labels, available={"u1"},
    )  # fmt: skip
    assert [t["k"] for t in ix["taxa"]] == ["trex"]
    t = ix["taxa"][0]
    assert (
        t["s"] == "/pa/static/sil/u1.svg"
        and t["st"] == "Tyrannosaurus"
        and t["u"].endswith("trex.html")
    )
    assert [r["k"] for r in ix["refs"]] == ["man"]  # no copy of the elephant's silhouette
    assert ix["refs"][0]["s"] == "/pa/static/compare/person.svg" and ix["hash"] == "compare"
