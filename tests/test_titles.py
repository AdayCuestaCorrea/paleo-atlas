"""Spanish study titles with a fake model."""

import json

from paleo.ingest import crossref
from paleo.narrative.titles import check_title, titles_path, translate_titles
from test_narrative import make_llm

NAMES = {"Spinosaurus"}


def test_check_title_keeps_numbers_and_scientific_names():
    src = "A 95-million-year-old Spinosaurus from Niger"
    assert check_title(src, "Un Spinosaurus de hace 95 millones de años de Níger", NAMES) == []
    assert "numbers changed" in check_title(src, "Un Spinosaurus de hace 90 millones", NAMES)
    assert "name lost: Spinosaurus" in check_title(src, "Un espinosaurio de hace 95 m.a.", NAMES)
    assert check_title(src, "", NAMES) == ["empty translation"]
    assert check_title("A 1.5 m skull", "Un cráneo de 1,5 m", NAMES) == []


def store_works(raw, titles, languages=None):
    works = crossref.store(raw)
    for doi, title in titles.items():
        work = {"title": [title], "language": (languages or {}).get(doi)}
        works.save_if_changed(doi, {"doi": doi, "found": True, "work": work})
    works.flush()


def test_titles_are_translated_once_and_bad_ones_rejected(tmp_path):
    raw, derived = tmp_path / "raw", tmp_path / "derived"
    store_works(raw, {
        "10.1/a": "A new <i>Spinosaurus</i> from Niger",
        "10.1/b": "Teeth from 2 sites",
    })  # fmt: skip
    answers = [{"sentences": [
        {"index": 1, "text": "Un nuevo Spinosaurus de Níger"},
        {"index": 2, "text": "Dientes de 3 yacimientos"},  # number changed: rejected
    ]}]  # fmt: skip
    result = translate_titles(
        make_llm(tmp_path, answers), raw_root=raw, derived_root=derived, scientific_names=NAMES
    )
    assert (result.translated, result.rejected) == (1, 1)
    rows = json.loads(titles_path(derived).read_text())
    assert [(r["doi"], r["title_es"]) for r in rows] == [
        ("10.1/a", "Un nuevo Spinosaurus de Níger")
    ]

    again = [{"sentences": [{"index": 1, "text": "Dientes de 2 yacimientos"}]}]
    result = translate_titles(
        make_llm(tmp_path, again), raw_root=raw, derived_root=derived, scientific_names=NAMES
    )
    assert (result.up_to_date, result.translated) == (1, 1)  # only the rejected one again


def test_titles_already_in_spanish_are_not_translated(tmp_path):
    raw, derived = tmp_path / "raw", tmp_path / "derived"
    store_works(raw, {"10.1/es": "Un nuevo Spinosaurus de Níger", "10.1/en": "A new Spinosaurus"},
                languages={"10.1/es": "es", "10.1/en": "en"})  # fmt: skip
    # A translation made before the language was read is dropped.
    titles_path(derived).parent.mkdir(parents=True)
    titles_path(derived).write_text(json.dumps([{"doi": "10.1/es", "title": "x", "title_es": "y",
                                                 "prompt_version": "old"}]))  # fmt: skip
    answers = [{"sentences": [{"index": 1, "text": "Un nuevo Spinosaurus"}]}]
    result = translate_titles(
        make_llm(tmp_path, answers), raw_root=raw, derived_root=derived, scientific_names=NAMES
    )
    assert (result.total, result.translated) == (1, 1)
    assert [r["doi"] for r in json.loads(titles_path(derived).read_text())] == ["10.1/en"]
