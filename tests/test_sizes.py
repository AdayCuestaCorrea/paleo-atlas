"""Body sizes for the comparator: the rule that reads lengths from verified facts."""

import json

import pytest

from paleo import sizes


def cand(statement: str, taxon: str = "Tyrannosaurus", key: str = "x", fid: str = "F001"):
    return sizes.classify(sizes.Candidate(key, fid, statement, "", f"{key}:enwiki:2"), taxon)


def spans(text: str) -> list[tuple[float, float]]:
    return [(r.min_m, r.max_m) for r in sizes.readings(text)]


def test_readings_ranges_units_and_words():
    assert spans("between 11.1 and 13 meters long") == [(11.1, 13.0)]
    assert spans("measured 22 to 24 feet long") == [(6.706, 7.315)]
    assert spans("about 60 centimeters long") == [(0.6, 0.6)]
    assert spans("up to six meters in length") == [(6.0, 6.0)]
    assert spans("de 4,5 m") == [(4.5, 4.5)]  # decimal comma
    # A conversion in brackets is the same reading, not a second length.
    assert spans("reached around 12 meters (39.7 feet) in length") == [(12.0, 12.0)]
    assert spans("reaching 153 mm or 6 inches in length") == [(0.153, 0.153)]


def test_qualifiers():
    assert [r.qualifier for r in sizes.readings("could reach up to 13 meters")] == ["up_to"]
    assert [r.qualifier for r in sizes.readings("a total length of over 12 meters")] == ["at_least"]
    assert [r.qualifier for r in sizes.readings("4 to 5 meters long")] == ["range"]


@pytest.mark.parametrize(
    ("taxon", "statement"),
    [
        ("Saurornitholestes", "Saurornitholestes measured approximately 1.8 meters in length."),
        ("Tyrannosaurus", "Adult T. rex reached between 11.1 and 13 meters in length."),
        # The height is another dimension, not a second length.
        (
            "Gallimimus",
            "Gallimimus was approximately 6 meters long and 1.9 meters tall at the hip.",
        ),
    ],
)
def test_accepted_by_the_rule(taxon, statement):
    c = cand(statement, taxon)
    assert c.status == "accepted" and len(c.readings) == 1


@pytest.mark.parametrize(
    "statement",
    [
        "The largest known Tyrannosaurus skulls measure up to 1.52 meters in length.",
        "The enlarged pedal claw on the second digit was 7.5 mm long.",
        "Estimates suggest a maximum running speed of 12.57 to 13.82 m/s.",
        "The fossilized cypress trees were estimated to be 15.3 meters tall.",
    ],
)
def test_rejected_by_the_rule(statement):
    assert cand(statement).status == "rejected"


@pytest.mark.parametrize(
    "statement",
    [
        "The known specimen of Haolong is a nearly complete juvenile measuring about 2.45 meters.",
        "Despite being known only from fragmentary remains, it was 30 to 35 meters long.",
        "It is debated whether lengths of 5 meters or more for D. terrelli are accurate.",
        # The animal is not the subject: a part of it is (only the model can tell).
        "The humeri of Eurotrochilus measure between 6.0 and 6.5 millimeters.",
        "Tyrannosaurus possessed gill rakers that were 3 to 12 centimeters long.",
        "Specimens of T. rex measured between 11.1 and 13 meters long.",
        # A part and the body in one sentence: the model decides which number is which.
        "Acrocanthosaurus had an estimated skull length of 1.23 to 1.29 meters and a body "
        "length of 11 to 12 meters.",
    ],
)
def test_doubtful_goes_to_the_model(statement):
    assert cand(statement).status == "doubtful"


def test_model_numbers_must_be_in_the_sentence():
    s = "Acrocanthosaurus had a skull 1.23 to 1.29 meters long and a body length of 11 to 12 m."
    ok = sizes.apply_label(cand(s), {"adult_body_length": True, "min_m": 11.0, "max_m": 12.0})
    assert ok.status == "accepted" and (ok.readings[0].min_m, ok.readings[0].max_m) == (11, 12)
    made_up = sizes.apply_label(cand(s), {"adult_body_length": True, "min_m": 11.5, "max_m": 12.0})
    assert made_up.status == "rejected"
    no = sizes.apply_label(cand(s), {"adult_body_length": False, "min_m": None, "max_m": None})
    assert no.status == "rejected"


def test_main_estimate_is_the_one_closest_to_the_median(tmp_path):
    facts = {"taxon": "Dunkleosteus", "taxon_key": "dunk", "citations": {
        "dunk:enwiki:2": {"title": "Dunkleosteus", "url": "https://en.wikipedia.org/wiki/D?oldid=1",
                          "license": "CC BY-SA 4.0"}}}  # fmt: skip
    (tmp_path / "dunk.json").write_text(json.dumps(facts))
    cs = [
        cand("Dunkleosteus was about 3.4 meters long.", "Dunkleosteus", "dunk", "F1"),
        cand("Dunkleosteus measured 3 to 4 meters long.", "Dunkleosteus", "dunk", "F2"),
        cand("D. terrelli was estimated at 10 meters long.", "Dunkleosteus", "dunk", "F3"),
    ]
    (row,) = sizes.taxon_sizes(cs, tmp_path)
    assert row["main_fact_id"] == "F2"  # middle 3.5 is closest to the median (3.5)
    assert (row["span_min_m"], row["span_max_m"]) == (3.0, 10.0)
    assert [e["fact_id"] for e in row["estimates"]][-1] == "F3"
    assert row["estimates"][0]["source_url"].endswith("oldid=1")
