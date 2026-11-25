"""Phase 7 checks of the texts, found reviewing 15 pages (eval/fichas)."""

import json

from paleo.narrative.checks import (
    _align_one,
    en_time_problems,
    eswiki_conflicts,
    fix_clade_rank,
)
from paleo.narrative.write import fix_es, recheck_quality


def test_ages_the_taxobox_rules_out():
    iguanodon = (126.0, 122.0)
    assert en_time_problems(
        "The genus lived from the Kimmeridgian to the Maastrichtian stages, between 154.8 and "
        "66 million years ago.", "Iguanodon", iguanodon,
    )  # fmt: skip
    assert en_time_problems(
        "Carnotaurus fossils date to the Maastrichtian to lower Danian ages, approximately 69 "
        "to 64 million years ago.", "Carnotaurus", (69.0, 66.0),
    )  # fmt: skip
    # a close estimate, a rounded figure, another subject: not contradictions
    assert not en_time_problems(
        "Spinosaurus lived during the Cenomanian, 100 to 94 million years ago.",
        "Spinosaurus", (100.5, 93.9),
    )  # fmt: skip
    assert not en_time_problems(
        "It lived approximately 125 million years ago.", "Moabosaurus", (121.4, 113.2)
    )
    assert not en_time_problems(
        "Non-avian dinosaurs went extinct 66 million years ago.", "Stegosaurus", (155.0, 145.0)
    )
    assert not en_time_problems(
        "Eotriceratops is 2 million years older than Triceratops.", "Eotriceratops", (68.0, 67.0)
    )


def test_a_stage_in_the_wrong_part_of_its_period():
    assert en_time_problems(
        "Giganotosaurus lived during the Cenomanian stage of the Early Cretaceous.",
        "Giganotosaurus", None,
    )  # fmt: skip
    # contrasting two datings, or a range with one stage that fits: fine
    assert not en_time_problems(
        "While originally thought to be Late Cretaceous, it was re-dated to the early Albian.",
        "Alnashetri", None,
    )  # fmt: skip
    assert not en_time_problems(
        "It lived during the Middle Devonian, from the Givetian to the Frasnian.", "X", None
    )


def test_spanish_that_changes_the_meaning():
    def problems(en, es):
        return _align_one(en, es, set())

    assert problems("One of the largest flightless maniraptorans.",
                    "Uno de los maniraptoros voladores más grandes.")  # fmt: skip
    assert problems("Collected at the head of the Missouri River.",
                    "Recolectado en la cabecera del río Misisipi.")  # fmt: skip
    assert problems("Comparable in size to a Eurasian magpie.",
                    "De tamaño comparable al de un gorrión europeo.")  # fmt: skip
    assert problems("Coombs noted that the fragments were cervical.",
                    "Coombs escribió, noting que los fragmentos eran cervicales.")  # fmt: skip
    assert problems("It belongs to the group Parasaurolophini.",
                    "Pertenece al grupo parafilético Parasaurolophini.")  # fmt: skip
    assert problems("Basal theropods such as ceratosaurs.",
                    "Terópodos basales como los ceratópsidos.")  # fmt: skip
    # names that look like common words, and titles copied as they are
    assert not problems("A tibia from the North Horn Formation.",
                        "Una tibia de la Formación North Horn.")  # fmt: skip
    assert not problems("It was published in The Science of Nature.",
                        "Se publicó en The Science of Nature.")  # fmt: skip


def test_spanish_that_names_another_period():
    def bad(en, es):
        return [p for p in _align_one(en, es, set()) if "period" in p]

    # found on 2026-11-25: Palaeocene (British spelling) adapted as Eocene, and back
    assert bad("It lived during the Late Palaeocene, within the Danian stage.",
               "Vivió durante el Eoceno Superior, dentro del piso daniano.")  # fmt: skip
    assert bad("Fossils come from Early Eocene London Clay deposits.",
               "Los fósiles proceden de la arcilla de Londres del Paleoceno Inferior.")  # fmt: skip
    # the Mississippian is the Lower Carboniferous
    assert bad("Fossils were found in Mississippian deposits of Belgium.",
               "Se hallaron fósiles en depósitos del Carbonífero Superior de Bélgica.")  # fmt: skip
    # naming the period of a stage the English gives is fine, and so are the right ones
    assert not bad("It lived during the Late Maastrichtian stage.",
                   "Vivió durante el piso maastrichtiense del Cretácico Superior.")  # fmt: skip
    assert not bad("It lived during the Pennsylvanian and Permian periods.",
                   "Vivió durante el Carbonífero Superior y el Pérmico.")  # fmt: skip
    assert not bad("It lived in the Late Palaeocene.", "Vivió en el Paleoceno Superior.")
    assert not bad(
        "A jaw found at the Cretaceous-Paleogene boundary.",
        "Una mandíbula hallada en el límite entre el Cretácico y el Paleoceno.",
    )
    assert not bad(
        "Fossils date from the Eo-Oligocene boundary.",
        "Los fósiles proceden del límite entre el Eoceno y el Oligoceno.",
    )


def test_clade_word_put_at_the_english_rank():
    fixed = fix_clade_rank(
        "Entradasuchus was a crocodyliform.", "Entradasuchus era un cocodrilomorfo."
    )
    assert fixed == "Entradasuchus era un crocodiliforme."
    assert fix_clade_rank(
        "A small tyrannosauroid theropod.", "Un pequeño terópodo tiranosáurido."
    ) == ("Un pequeño terópodo tiranosauroideo.")
    # the English names both ranks: nothing to put right
    same = "dentro de los hadrosáuridos"
    assert fix_clade_rank("the hadrosaurine Saurolophus, within the hadrosaurids", same) == same


def test_fixed_spanish_replacements_of_phase_7():
    assert fix_es("El especimen tipo") == "El espécimen tipo"
    assert fix_es("piso Tithoniense") == "piso Titoniense"
    assert fix_es("Dos otras especies") == "Otras dos especies"
    assert fix_es("El garrote caudal servía") == "La maza caudal servía"
    assert fix_es("que las cuernas estaban cubiertas") == "que los cuernos estaban cubiertos"
    assert fix_es("Una cuerna triangular situada") == "Un cuerno triangular situado"
    assert fix_es("unas 200 a 400 kilogramas") == "unos 200 a 400 kilogramos"


def test_a_length_from_the_spanish_wikipedia_that_the_english_one_contradicts():
    facts = [
        {"fact_id": "F044", "chunk_id": "b:enwiki:10", "statement":
         "Brachiosaurus has been estimated to reach lengths of 18 to 22 meters and heights of "
         "9.4 to 13 meters."},
        {"fact_id": "F097", "chunk_id": "b:eswiki:4",
         "statement": "The estimated length of Brachiosaurus is 26 meters."},
    ]  # fmt: skip
    assert eswiki_conflicts(
        "The estimated length of Brachiosaurus is 26 meters.", [facts[1]], facts
    )
    assert not eswiki_conflicts("It reached about 21 meters long.", [facts[1]], facts)
    # an attributed estimate is another figure, not a contradiction
    assert not eswiki_conflicts("Gregory Paul estimated a length of 26 meters.", [facts[1]], facts)


def _write(path, taxon, key, lang, sentences):
    doc = {"taxon": taxon, "taxon_key": key, "lang": lang, "status": "verified",
           "generator": "test", "prompt_version": "v", "facts_hash": "h", "problems": [],
           "sections": [{"section": "time_and_habitat",
                         "sentences": [{"text": t, "fact_ids": [f"F00{i}"]}
                                       for i, t in enumerate(sentences, 1)]}]}  # fmt: skip
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_recheck_leaves_out_the_sentence_in_both_languages(tmp_path):
    texts = tmp_path / "texts"
    texts.mkdir()
    en = [
        "Iguanodon was a large herbivorous ornithopod dinosaur from Europe and its relatives.",
        "Iguanodon lived in the Barremian, about 126 to 122 million years ago, in Belgium.",
        "The genus lived from the Kimmeridgian to the Maastrichtian, 154.8 to 66 million years "
        "ago.",
        "Many skeletons were found in a coal mine at Bernissart in Belgium in the year 1878.",
    ]
    es = [
        "Iguanodon fue un gran dinosaurio ornitópodo herbívoro de Europa y sus parientes.",
        "Iguanodon vivió en el Barremiense, hace unos 126 a 122 millones de años, en Bélgica.",
        "El género vivió del Kimmeridgiense al Maastrichtiense, hace 154,8 a 66 millones de años.",
        "Se hallaron muchos esqueletos en una mina de carbón de Bernissart, Bélgica, en el año "
        "1878.",
    ]
    _write(texts / "iguanodon.en.json", "Iguanodon", "iguanodon", "en", en)
    _write(texts / "iguanodon.es.json", "Iguanodon", "iguanodon", "es", es)
    out = recheck_quality(tmp_path, {"Iguanodon": (126.0, 122.0)})
    assert out["en_dropped"] == ["iguanodon"] and out["es_changed"] == ["iguanodon"]
    for lang, kept in (("en", en), ("es", es)):
        doc = json.loads((texts / f"iguanodon.{lang}.json").read_text(encoding="utf-8"))
        texts_now = [s["text"] for sec in doc["sections"] for s in sec["sentences"]]
        assert texts_now == [kept[0], kept[1], kept[3]]


def test_a_short_page_with_only_a_fixed_word_stays(tmp_path):
    texts = tmp_path / "texts"
    texts.mkdir()
    _write(
        texts / "palaeospiza.en.json",
        "Palaeospiza",
        "palaeospiza",
        "en",
        [
            "Palaeospiza was a small perching bird found in the lake beds of Colorado.",
            "It lived in the Priabonian stage, from 37.71 to 33.9 million years ago.",
        ],
    )
    _write(
        texts / "palaeospiza.es.json",
        "Palaeospiza",
        "palaeospiza",
        "es",
        [
            "Palaeospiza fue un pequeño pájaro hallado en los lechos lacustres de Colorado.",
            "Vivió en el piso priabonense, hace entre 37,71 y 33,9 millones de años.",
        ],
    )
    out = recheck_quality(tmp_path, {})
    assert out["es_changed"] == ["palaeospiza"] and out["failed"] == []
    doc = json.loads((texts / "palaeospiza.es.json").read_text(encoding="utf-8"))
    assert "priaboniense" in doc["sections"][0]["sentences"][1]["text"]


def test_misspelled_spanish_stages():
    assert fix_es("del Kimmeríjico Tardío") == "del Kimmeridgiense Tardío"
    assert fix_es("el títónico temprano") == "el titoniense temprano"
    assert fix_es("piso caloviense") == "piso calloviense"
    assert fix_es("al noreste de Maastricht") == "al noreste de Maastricht"
    assert fix_es("la arcilla de Kimmeridge") == "la arcilla de Kimmeridge"
    assert fix_es("habitó la etapa valanginiana") == "habitó el piso valanginiense"
