"""Sources, fact extraction and writing with a fake model (no network, no GPU)."""

import json

import httpx

from paleo.llm import LLM, Provider
from paleo.narrative.facts import extract_facts
from paleo.narrative.sources import Chunk, _split, article_chunks, taxon_key
from paleo.narrative.write import select_facts, write_page

TAXON = "Testosaurus rex"


def chunk(cid, text, *, lang="en", public=True):
    return Chunk(cid, "wikipedia_article", lang, "Testosaurus", None, "CC BY-SA 4.0", public, text)


CHUNKS = [
    chunk(
        "t:enwiki:1",
        "Testosaurus rex was a theropod dinosaur that lived 70 million years ago in Spain.",
    ),
    chunk("t:abstract:1", "We describe a skull 1.2 m long from the Tremp Formation.", public=False),
]


def fake_model(answers):
    """Returns the queued JSON answers in order."""

    def handler(request):
        content = json.dumps(answers.pop(0))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 10}},
        )

    return handler


def make_llm(tmp_path, answers):
    client = httpx.Client(transport=httpx.MockTransport(fake_model(answers)))
    return LLM(
        Provider("test", "https://llm.test/v1"), "m", client=client, cache_dir=tmp_path / "llm"
    )


def test_taxon_key_matches_the_dbt_macro():
    assert taxon_key("Spinosaurus mirabilis") == "spinosaurus-mirabilis"
    assert taxon_key("Xenicus longipes perditus") == "xenicus-longipes-perditus"


def test_long_text_is_split_under_the_limit():
    text = "\n\n".join(["Sentence one is here. Sentence two is here."] * 400)
    pieces = _split(text, limit=1_000)
    assert len(pieces) > 1
    assert all(len(p) <= 1_000 for p in pieces)


def test_article_chunks_drop_references_and_keep_content_templates():
    record = {
        "found": True,
        "title": "Testosaurus",
        "revid": 1,
        "wikitext": "{{Speciesbox|genus=Testosaurus|fossil_range=Late Cretaceous}}\n"
        "'''Testosaurus''' is a {{dinogloss|theropod}} about {{convert|8|m|ft}} long.<ref>X</ref>\n"
        "== Description ==\nIt had a long snout and small arms, unlike most of its relatives.\n"
        "== References ==\n{{Reflist}}",
    }
    chunks = article_chunks(TAXON, "en", record)
    texts = "\n".join(c.text for c in chunks)
    assert "theropod about 8 m long" in texts
    assert "fossil_range: Late Cretaceous" in texts
    assert "Reflist" not in texts and "References" not in " ".join(c.title for c in chunks)
    assert all(c.public_quote and c.license == "CC BY-SA 4.0" for c in chunks)


def test_facts_are_verified_and_abstract_quotes_stay_private(tmp_path):
    answers = [
        {
            "facts": [
                {
                    "chunk_id": "t:enwiki:1",
                    "statement": "It was a meat-eating dinosaur from Spain.",
                    "category": "description",
                    "quote": "was a theropod dinosaur that lived 70 million years ago in Spain",
                },
                {
                    "chunk_id": "t:enwiki:1",
                    "statement": "It lived 80 million years ago.",
                    "category": "time_and_habitat",
                    "quote": "lived 80 million years ago",  # not in the chunk
                },
                {
                    "chunk_id": "t:abstract:1",
                    "statement": "Its skull measured 1.2 m.",
                    "category": "description",
                    "quote": "a skull 1.2 m long",
                },
            ]
        }
    ]
    llm = make_llm(tmp_path, answers)
    result = extract_facts(
        llm, TAXON, CHUNKS, derived_root=tmp_path / "derived", cache_root=tmp_path / "cache"
    )
    assert (result.accepted, result.rejected) == (2, 1)
    doc = json.loads(result.path.read_text())
    public = json.dumps(doc)
    assert "a skull 1.2 m long" not in public  # abstract quote kept out of the public file
    private = json.loads(
        (tmp_path / "cache" / "facts_private" / "testosaurus-rex.json").read_text()
    )
    assert "a skull 1.2 m long" in private.values()


def facts_file(tmp_path):
    facts = [
        {
            "fact_id": "F001",
            "statement": "It was a meat-eating dinosaur from Spain.",
            "category": "description",
            "quote": None,
        },
        {
            "fact_id": "F002",
            "statement": "Its skull measured 1.2 m.",
            "category": "description",
            "quote": None,
        },
    ]
    path = tmp_path / "facts.json"
    path.write_text(json.dumps({"taxon": TAXON, "taxon_key": "testosaurus-rex", "facts": facts}))
    return path


def test_verified_page_in_both_languages(tmp_path):
    answers = [
        {
            "sections": [
                {
                    "section": "description",
                    "sentences": [
                        {
                            "text": "This meat-eating dinosaur lived in what is now Spain.",
                            "fact_ids": ["F001"],
                        },
                        {"text": "Its skull was 1.2 m long.", "fact_ids": ["F002"]},
                    ],
                }
            ]
        },
        {
            "sentences": [
                {"index": 1, "text": "Este dinosaurio carnívoro vivió en lo que hoy es España."},
                {"index": 2, "text": "Su cráneo medía 1,2 m."},
            ]
        },
        {
            "sentences": [  # grammar pass leaves it as it is
                {"index": 1, "text": "Este dinosaurio carnívoro vivió en lo que hoy es España."},
                {"index": 2, "text": "Su cráneo medía 1,2 m."},
            ]
        },
    ]
    result = write_page(
        make_llm(tmp_path, answers),
        facts_file(tmp_path),
        CHUNKS,
        derived_root=tmp_path / "derived",
        scientific_names={"Testosaurus"},
    )
    assert result.status == {"en": "verified", "es": "verified"}
    es = json.loads((tmp_path / "derived" / "texts" / "testosaurus-rex.es.json").read_text())
    assert es["sections"][0]["sentences"][1] == {
        "text": "Su cráneo medía 1,2 m.",
        "fact_ids": ["F002"],
    }


def test_failed_text_goes_to_review_after_retries(tmp_path):
    bad = {
        "sections": [
            {
                "section": "description",
                "sentences": [
                    {"text": "It weighed 3 tonnes.", "fact_ids": ["F001"]},
                ],
            }
        ]
    }
    result = write_page(
        make_llm(tmp_path, [bad, bad, bad]),
        facts_file(tmp_path),
        CHUNKS,
        derived_root=tmp_path / "derived",
        scientific_names=set(),
    )
    assert result.status == {"en": "failed"}  # no Spanish for an unverified text
    assert (tmp_path / "derived" / "texts_review" / "testosaurus-rex.en.json").exists()
    assert not (tmp_path / "derived" / "texts" / "testosaurus-rex.en.json").exists()

    # A later verified text retires the failed one.
    write_page(make_llm(tmp_path / "again", one_sentence_answers()), facts_file(tmp_path), CHUNKS,
               derived_root=tmp_path / "derived", scientific_names=set())  # fmt: skip
    assert (tmp_path / "derived" / "texts" / "testosaurus-rex.en.json").exists()
    assert not (tmp_path / "derived" / "texts_review" / "testosaurus-rex.en.json").exists()


def test_fact_selection_is_balanced_and_capped():
    facts = [{"fact_id": f"F{i:03d}", "category": "description"} for i in range(30)]
    facts += [{"fact_id": "F900", "category": "debate"}]
    chosen = select_facts(facts, limit=10)
    assert len(chosen) == 10
    assert any(f["category"] == "debate" for f in chosen)


def test_pages_written_from_the_same_facts_are_up_to_date(tmp_path):
    from paleo.narrative.write import is_up_to_date

    answers = [
        {"sections": [{"section": "description", "sentences": [
            {"text": "This meat-eating dinosaur lived in what is now Spain.", "fact_ids": ["F001"]},
        ]}]},
        {"sentences": [
            {"index": 1, "text": "Este dinosaurio carnívoro vivió en lo que hoy es España."},
        ]},
        {"sentences": [
            {"index": 1, "text": "Este dinosaurio carnívoro vivió en lo que hoy es España."},
        ]},
    ]  # fmt: skip
    path = facts_file(tmp_path)
    derived = tmp_path / "derived"
    assert not is_up_to_date(path, derived)
    write_page(
        make_llm(tmp_path, answers), path, CHUNKS, derived_root=derived, scientific_names=set()
    )
    assert is_up_to_date(path, derived)
    doc = json.loads(path.read_text())
    doc["facts"].append({"fact_id": "F003", "statement": "New fact.", "category": "debate"})
    path.write_text(json.dumps(doc))
    assert not is_up_to_date(path, derived)  # facts changed: write again


def test_a_new_prompt_version_writes_again(tmp_path, monkeypatch):
    from paleo.narrative import write

    path = facts_file(tmp_path)
    derived = tmp_path / "derived"
    write_page(make_llm(tmp_path, one_sentence_answers()), path, CHUNKS,
               derived_root=derived, scientific_names=set())  # fmt: skip
    assert write.is_up_to_date(path, derived)
    monkeypatch.setattr(write, "prompt_versions", lambda: {"en": "write-en-v9", "es": "x"})
    assert not write.is_up_to_date(path, derived)


def one_sentence_answers(review="Este dinosaurio carnívoro vivió en lo que hoy es España."):
    return [
        {"sections": [{"section": "description", "sentences": [
            {"text": "This meat-eating dinosaur lived in what is now Spain.", "fact_ids": ["F001"]},
        ]}]},
        {"sentences": [
            {"index": 1, "text": "Este dinosaurio carnívoro vivió en lo que hoy es Espana."},
        ]},
        {"sentences": [{"index": 1, "text": review}]},
    ]  # fmt: skip


def written_es(tmp_path):
    path = tmp_path / "derived" / "texts" / "testosaurus-rex.es.json"
    return json.loads(path.read_text())


def test_grammar_review_is_kept_when_it_passes_the_checks(tmp_path):
    result = write_page(make_llm(tmp_path, one_sentence_answers()), facts_file(tmp_path), CHUNKS,
                        derived_root=tmp_path / "derived", scientific_names=set())  # fmt: skip
    assert result.review == "accepted"
    es = written_es(tmp_path)
    assert es["review"] == "accepted"
    assert es["sections"][0]["sentences"][0]["text"].endswith("España.")


def test_grammar_review_that_changes_the_facts_is_rejected(tmp_path):
    answers = one_sentence_answers(
        review="Este dinosaurio vivió hace 90 millones de años en España."
    )
    result = write_page(make_llm(tmp_path, answers), facts_file(tmp_path), CHUNKS,
                        derived_root=tmp_path / "derived", scientific_names=set())  # fmt: skip
    assert result.review == "rejected"
    assert written_es(tmp_path)["sections"][0]["sentences"][0]["text"].endswith("Espana.")


def test_sources_hash_ignores_private_chunks():
    from paleo.narrative.facts import sources_hash

    public = Chunk("t:enwiki:1", "wikipedia_article", "en", "T", None, "CC BY-SA 4.0", True, "x")
    abstract = Chunk("t:abstract:1", "crossref", "en", "T", None, "publisher", False, "y")
    assert sources_hash([public]) == sources_hash([public, abstract])


def test_paleobiology_topics_travel_with_the_sentence_and_are_saved_apart(tmp_path):
    from paleo.narrative import write

    text = write.WrittenText(sections=[
        write.WrittenSection(section="paleobiology", sentences=[
            write.WrittenSentence(text="It ate meat.", fact_ids=["F1"], topic="diet"),
            write.WrittenSentence(text="It grew fast.", fact_ids=["F2"]),
        ]),
        write.WrittenSection(section="curiosities", sentences=[
            write.WrittenSentence(text="Its bite was huge.", fact_ids=["F3"]),
        ]),
    ])  # fmt: skip
    flat = write._flatten(text)
    assert [s for _, _, s in flat] == ["curiosities", "paleobiology:diet", "paleobiology"]


def test_a_few_failed_sentences_are_left_out_but_not_many():
    from paleo.narrative.checks import SentenceReport, TextReport
    from paleo.narrative.write import _salvage

    sentences = [(f"S{i}", ["F1"], "description") for i in range(6)]

    def report(failed, text_level=()):
        return TextReport(
            [SentenceReport(i, f"S{i}", ["bad"] if i in failed else []) for i in range(6)],
            list(text_level),
        )

    assert [t for t, _, _ in _salvage(sentences, report({4}))] == ["S0", "S1", "S2", "S3", "S5"]
    assert _salvage(sentences, report({0, 1, 2, 3})) is None  # too many: the page fails
    assert _salvage(sentences, report({1}, ["too long"])) is None  # text-level problem


def test_padded_fact_ids_are_read_as_the_real_ones():
    from paleo.narrative.write import _canonical_id

    assert _canonical_id("F0113") == "F113"
    assert _canonical_id("F013") == "F013" and _canonical_id("F7") == "F007"
    assert _canonical_id("note") == "note"


def test_a_few_misaligned_spanish_sentences_are_left_out():
    from paleo.narrative.checks import SentenceReport, TextReport
    from paleo.narrative.write import _salvage_es

    en = [(f"Fact number {i} is {i}.", ["F1"], "description") for i in range(6)]
    good = [f"El hecho número {i} es {i}." for i in range(6)]
    clean = TextReport([SentenceReport(i, good[i], []) for i in range(6)])

    def es_of(adapted):
        return [(t, f, s) for t, (_, f, s) in zip(adapted, en, strict=False)]

    one_off = [*good[:2], "El hecho número 2 es 7.", *good[3:]]  # other number
    kept = _salvage_es(en, one_off, es_of(one_off), clean, set())
    assert [t for t, _, _ in kept] == good[:2] + good[3:]
    four_off = ["Otro." for _ in range(4)] + good[4:]
    assert _salvage_es(en, four_off, es_of(four_off), clean, set()) is None  # too many
    assert _salvage_es(en, good[:5], es_of(good[:5]), clean, set()) is None  # count differs


def test_failed_spanish_texts_are_rescued_without_a_model(tmp_path):
    import json

    from paleo.narrative.write import facts_hash, resalvage_es

    facts = [{"fact_id": f"F{i}", "statement": f"Fact {i} says {i} things.",
              "category": "description", "chunk_id": "c1"} for i in range(1, 7)]  # fmt: skip
    h = facts_hash(facts)

    def doc(lang, texts, status):
        sentences = [{"text": t, "fact_ids": [f"F{i + 1}"]} for i, t in enumerate(texts)]
        return {"taxon": "Testosaurus", "taxon_key": "testosaurus", "lang": lang, "status": status,
                "generator": "ollama/test", "prompt_version": "v", "facts_hash": h,
                "problems": ["x"],
                "sections": [{"section": "description", "sentences": sentences}]}  # fmt: skip

    derived = tmp_path / "derived"
    for folder in ("texts", "texts_review", "facts"):
        (derived / folder).mkdir(parents=True)
    (derived / "facts" / "testosaurus.json").write_text(
        json.dumps({"taxon": "Testosaurus", "taxon_key": "testosaurus", "facts": facts})
    )
    english = [
        f"Fact {i} says {i} things about the fossil record of this curious animal."
        for i in range(1, 7)
    ]
    (derived / "texts" / "testosaurus.en.json").write_text(
        json.dumps(doc("en", english, "verified"))
    )
    spanish = [
        f"El hecho {i} cuenta {i} cosas sobre el registro fósil de este curioso animal."
        for i in range(1, 7)
    ]
    spanish[3] = (
        "El hecho 4 cuenta 9 cosas sobre el registro fósil de este curioso animal."  # other number
    )
    (derived / "texts_review" / "testosaurus.es.json").write_text(
        json.dumps(doc("es", spanish, "failed"))
    )

    out = resalvage_es(derived, lambda genus: [], set())
    assert out["salvaged"] == ["testosaurus"]
    saved = json.loads((derived / "texts" / "testosaurus.es.json").read_text())
    texts = [s["text"] for s in saved["sections"][0]["sentences"]]
    assert saved["status"] == "verified" and saved["review"] == "skipped" and len(texts) == 5
    assert not any("9 cosas" in t for t in texts)
    assert not (derived / "texts_review" / "testosaurus.es.json").exists()
    # Run again: nothing left to rescue.
    assert resalvage_es(derived, lambda genus: [], set()) == {
        "salvaged": [],
        "still_failed": [],
        "skipped": [],
    }
