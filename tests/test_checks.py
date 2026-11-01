from paleo.narrative.checks import (
    check_alignment,
    check_fact,
    check_text,
    copied_runs,
    names,
    ngrams,
    numbers,
    words,
)

SOURCE = (
    "The holotype comprises a fragmentary skull including the right premaxilla, both maxillae, "
    "the nasal crest, part of the right dentary and five maxillary teeth. It lived in the Late "
    "Cretaceous Farak Formation of Niger about 95 million years ago and weighed 1,742.8 kg."
)
FACTS = {
    "F1": "The holotype is a partial skull with five teeth.",
    "F2": "It lived in the Farak Formation of Niger about 95 million years ago.",
    "F3": "Its estimated mass is 1,742.8 kg.",
}


def test_numbers_are_language_neutral():
    assert numbers("1,5 m y 1.5 m") == {"1.5"}
    assert numbers("1,742.8 kg") == numbers("1.742,8 kg") == numbers("1 742,8 kg") == {"1742.8"}
    assert numbers("between 10 and 14 m, in 2026") == {"10", "14", "2026"}


def test_fact_needs_a_verbatim_quote():
    quote = "weighed 1,742.8 kg"
    assert check_fact("Its estimated mass is 1,742.8 kg.", quote, SOURCE) is None
    assert "not found" in check_fact("Mass 1,742.8 kg.", "weighed about 1,743 kg", SOURCE)
    assert "too short" in check_fact("Niger.", "Niger", SOURCE)


def test_fact_numbers_must_be_in_the_quote():
    reason = check_fact("It weighed 1,742.8 kg 95 million years ago.", "weighed 1,742.8 kg", SOURCE)
    assert "numbers not in the quote" in reason and "95" in reason


def test_fact_copying_source_prose_is_rejected():
    statement = (
        "The holotype has the nasal crest, part of the right dentary and five maxillary teeth."
    )
    quote = "the nasal crest, part of the right dentary and five maxillary teeth"
    assert "copies the source wording" in check_fact(statement, quote, SOURCE)


def test_good_text_passes():
    sentences = [
        ("Only part of the skull is known, with five teeth.", ["F1"]),
        ("It lived in the Farak Formation of Niger about 95 million years ago.", ["F2"]),
    ]
    report = check_text(sentences, FACTS, [], check_names=True)
    assert report.passed, report.summary()


def test_sentence_without_citation_fails():
    report = check_text([("A big animal.", [])], FACTS, [])
    assert "no citation" in report.sentences[0].problems


def test_unknown_fact_id_fails():
    report = check_text([("A big animal.", ["F9"])], FACTS, [])
    assert "unknown" in report.sentences[0].problems[0]


def test_rounded_or_invented_numbers_fail():
    report = check_text([("It weighed about 1,743 kg.", ["F3"])], FACTS, [])
    assert "numbers not in the cited facts" in report.sentences[0].problems[0]


def test_numbers_must_come_from_the_cited_fact_not_another():
    report = check_text([("It weighed 1,742.8 kg.", ["F2"])], FACTS, [])
    assert not report.passed


def test_invented_name_fails_but_known_names_pass():
    ok = check_text([("Fossils come from Niger.", ["F2"])], FACTS, [])
    assert ok.passed
    bad = check_text([("Fossils come from Morocco.", ["F2"])], FACTS, [])
    assert "Morocco" in bad.sentences[0].problems[0]


def test_copied_prose_fails():
    sentence = (
        "Fossils include the nasal crest, part of the right dentary and five maxillary teeth."
    )
    report = check_text([(sentence, ["F1"])], FACTS, [SOURCE], check_names=False)
    assert any("copies" in p for p in report.sentences[0].problems)


def test_shared_runs_of_names_are_not_copying():
    grams = ngrams(words(SOURCE))
    assert copied_runs("from the Late Cretaceous Farak Formation of Niger", grams) == []


def test_species_epithets_are_not_ordinary_words():
    grams = ngrams(words("assigned to Bahariasaurus the sauropods Rebbachisaurus tamesnensis and"))
    text = "assigned to Bahariasaurus the sauropods Rebbachisaurus tamesnensis and"
    assert copied_runs(text, grams) == []


def test_repeating_a_fact_fails():
    sentences = [("It lived in Niger.", ["F2"]), ("Again, it lived in Niger.", ["F2"])]
    report = check_text(sentences, FACTS, [])
    assert any("repeats" in p for p in report.sentences[1].problems)


def test_too_long_text_fails():
    long = " ".join(["word"] * 600)
    assert not check_text([(long, ["F1"])], FACTS, []).passed


def test_names_skip_the_first_word_and_function_words():
    assert names("Spinosaurus lived in Niger. The animal") == {"Niger"}


def test_alignment_keeps_numbers_and_scientific_names():
    english = [("Spinosaurus mirabilis weighed 1,742.8 kg.", ["F3"])]
    assert (
        check_alignment(english, ["Spinosaurus mirabilis pesaba 1 742,8 kg."], {"Spinosaurus"})
        == []
    )
    assert check_alignment(english, ["Pesaba 1 742,8 kg."], {"Spinosaurus"})
    assert check_alignment(english, ["Spinosaurus pesaba 1 743 kg."], {"Spinosaurus"})
    assert check_alignment(english, ["Uno.", "Dos."], {"Spinosaurus"})
