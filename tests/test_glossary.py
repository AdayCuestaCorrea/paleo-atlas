"""Glossary (§12.2, Phase 5): terms from the verified pages, sources, checked definitions."""

import json

import httpx

from paleo.glossary import terms, write
from paleo.http import make_client
from paleo.ingest import glossary


def page(tmp_path, key, lang, sentences, status="verified"):
    body = {"lang": lang, "status": status, "sections": [
        {"section": "description", "sentences": [{"text": t, "fact_ids": [f"F{n}"]}
                                                 for n, t in enumerate(sentences)]}]}  # fmt: skip
    (tmp_path / f"{key}.{lang}.json").write_text(json.dumps(body), encoding="utf-8")


def test_frequencies_count_pages_not_occurrences():
    texts = ["The holotype is a skull. The holotype was found.", "A holotype of Spinosaurus."]
    freq = terms.page_frequencies(texts, exclude={"spinosaurus"})
    assert freq["holotype"] == 2  # twice in the first page counts once
    assert "spinosaurus" not in freq and "of spinosaurus" not in freq
    assert "the holotype" not in freq  # a function word is never part of a term


def test_forms_match_whole_words_in_any_case():
    pattern = terms.form_pattern(["vertebra", "vertebrae"])
    assert pattern.search("Its Vertebrae were hollow")
    assert not pattern.search("an invertebrate") and not pattern.search("vertebral")
    assert (
        terms.pages_with(["vertebra here", "nothing", "two vertebrae"], ["vertebra", "vertebrae"])
        == 2
    )


def test_spanish_comes_from_the_aligned_sentences(tmp_path):
    page(tmp_path, "a", "en", ["It lived in the Campanian.", "Its holotype is a skull."])
    page(tmp_path, "a", "es", ["Vivió en el Campaniense.", "Su holotipo es un cráneo."])
    page(tmp_path, "b", "en", ["Draft."], status="rejected")
    pairs = terms.aligned_sentences(tmp_path)
    assert pairs == [("It lived in the Campanian.", "Vivió en el Campaniense."),
                     ("Its holotype is a skull.", "Su holotipo es un cráneo.")]  # fmt: skip

    class FakeLLM:
        def complete_json(self, system, user, output, max_tokens):
            return output.model_validate(
                {
                    "terms": [
                        {"index": 1, "term": "holotipo", "forms": ["holotipo", "ejemplar tipo"]}
                    ]
                }
            )

    guess = terms.Term(en="holotype", es="holotypo", category="anatomy")
    (fixed,) = terms.spanish_terms(FakeLLM(), [guess], pairs)
    assert (fixed.es, fixed.forms_es) == (
        "holotipo",
        ["holotipo"],
    )  # a form not in the text is dropped


def test_merging_and_time_units_use_the_site_names():
    picked = [
        terms.Term(en="theropod", es="terópodo", forms_en=["theropods"], category="animals"),
        terms.Term(en="theropod dinosaur", es="terópodo", category="animals"),
        terms.Term(en="campanian", es="Campaniano", category="time"),
    ]
    merged = terms.merge_terms(picked)
    assert [t.en for t in merged] == ["theropod", "Campanian"]
    assert "theropod dinosaur" in merged[0].forms_en
    assert merged[1].es == "Campaniense" and "Campaniano" in merged[1].forms_es
    assert terms.LATIN.search("Tyrannosauridae") and not terms.LATIN.search("pelvis")


def test_a_lead_is_accepted_only_if_it_names_the_term():
    ok = {"title": "Holotype", "lead": "A holotype is a single specimen.", "disambiguation": False}
    assert glossary.accepted(ok, ["holotype"])
    assert not glossary.accepted({**ok, "lead": "A type is a specimen."}, ["holotype"])
    assert not glossary.accepted({**ok, "disambiguation": True}, ["holotype"])
    assert not glossary.accepted({"title": None}, ["holotype"])
    group = {"title": "Nodosauridae", "lead": "Nodosauridae is a family.", "disambiguation": False}
    assert glossary.accepted(group, ["nodosaurid", "nodosaurids"])  # the Latin group


def test_sources_keep_the_revision_and_the_spanish_article(tmp_path):
    def handler(request):
        lang = request.url.host.split(".")[0]
        if lang == "en":
            pages = [{"title": "Holotype", "extract": "A holotype is a single specimen.",
                      "revisions": [{"revid": 11}],
                      "langlinks": [{"title": "Holotipo"}]}]  # fmt: skip
            return httpx.Response(200, json={"query": {"pages": pages}})
        pages = [{"title": "Holotipo", "extract": "Un holotipo es un ejemplar.",
                  "revisions": [{"revid": 22}]}]  # fmt: skip
        return httpx.Response(200, json={"query": {"pages": pages}})

    term = {"term_id": "holotype", "term_en": "holotype", "term_es": "holotipo",
            "all_en": ["holotype"], "all_es": ["holotipo"]}  # fmt: skip
    with make_client(httpx.MockTransport(handler)) as client:
        r = glossary.ingest_glossary_sources(client, [term], raw_root=tmp_path / "raw",
                                             cache_root=tmp_path / "cache")  # fmt: skip
    assert r.accepted == {"en": 1, "es": 1}
    index = glossary.index_store(tmp_path / "raw").latest("holotype")["payload"]
    assert index["en"] == {"title": "Holotype", "revid": 11, "accepted": True}
    assert "lead" not in json.dumps(index)  # the text stays in the cache
    lead = glossary.lead_store("es", tmp_path / "cache").latest("holotype")["payload"]
    assert (lead["title"], lead["revid"]) == ("Holotipo", 22)


SOURCE = ("A holotype is a single physical example of an organism, known to have been used "
          "when the species was formally described in 1832.")  # fmt: skip


def test_each_check_catches_its_problem():
    good = "The one specimen that scientists used to describe a species for the first time."
    assert write.deterministic_problems(good, SOURCE, ["holotype"]) == []
    copied = ("It is a single physical example of an organism, known to have been used by "
              "scientists.")  # fmt: skip
    assert any(
        p.startswith("copied") for p in write.deterministic_problems(copied, SOURCE, ["holotype"])
    )
    assert write.deterministic_problems("A specimen.", SOURCE, ["holotype"]) == ["length: 2 words"]
    circular = (
        "The holotype specimen that scientists used to describe a species for the first time."
    )
    assert "circular: uses the term" in write.deterministic_problems(circular, SOURCE, ["holotype"])
    number = "The specimen used to describe a species for the first time, usually since 1758 or so."
    assert write.deterministic_problems(number, SOURCE, ["holotype"]) == [
        "numbers not in the source: 1758"
    ]


class Writer:
    label = "fake/writer"

    def __init__(self, text):
        self.text, self.calls = text, 0

    def complete_json(self, system, user, output, max_tokens):
        self.calls += 1
        n = user.count("TERM:")
        if output is write.Verdicts:
            return output.model_validate(
                {
                    "items": [
                        {"index": i, "supported": "invented" not in user} for i in range(1, n + 1)
                    ]
                }
            )
        return output.model_validate(
            {"definitions": [{"index": i, "definition": self.text} for i in range(1, n + 1)]}
        )


def test_definitions_are_written_once_and_the_judge_can_reject(tmp_path):
    cache, derived = tmp_path / "cache", tmp_path / "derived"
    glossary.lead_store("en", cache).save_if_changed(
        "holotype", {"term_id": "holotype", "title": "Holotype", "revid": 11, "lead": SOURCE}
    )
    glossary.lead_store("en", cache).flush()
    raw = tmp_path / "raw"
    glossary.index_store(raw).save_if_changed(
        "holotype",
        {
            "term_id": "holotype",
            "en": {"title": "Holotype", "revid": 11, "accepted": True},
            "es": {"title": None, "revid": None, "accepted": False},
        },
    )
    glossary.index_store(raw).flush()
    term = {"term_id": "holotype", "term_en": "holotype", "term_es": "holotipo",
            "all_en": ["holotype"], "all_es": ["holotipo"]}  # fmt: skip
    good = "The one specimen that scientists used to describe a species for the first time."
    llm = Writer(good)
    r = write.write_definitions(
        llm, llm, [term], derived_root=derived, cache_root=cache, raw_root=raw
    )
    assert r.verified == {"en": 1, "es": 1}  # Spanish written from the English lead
    es = json.loads(write.definition_path(derived, "holotype", "es").read_text())
    assert es["source"] == {"lang": "en", "title": "Holotype", "revid": 11}
    calls = llm.calls
    again = write.write_definitions(
        llm, llm, [term], derived_root=derived, cache_root=cache, raw_root=raw
    )
    assert again.up_to_date == 2 and llm.calls == calls

    other = tmp_path / "other"
    bad = Writer("An invented specimen that scientists used to describe a species long ago.")
    r = write.write_definitions(
        bad, bad, [term], derived_root=other, cache_root=cache, raw_root=raw
    )
    assert r.rejected == {"en": 1, "es": 1}
    en = json.loads(write.definition_path(other, "holotype", "en").read_text())
    assert en["status"] == "rejected" and en["problems"][0].startswith("judge:")


# ------------------------------------------------------------------ the website

ROWS = [
    {"term_id": "holotype", "category": "classification", "term_en": "holotype",
     "term_es": "holotipo", "forms_en": ["holotypes"], "forms_es": ["holotipos"],
     "pages_en": 5, "pages_es": 4,
     "definition_en": "The single specimen a species was described from.",
     "definition_es": "Ejemplar único con el que se describió una especie.",
     "source_title_en": "Holotype", "source_revid_en": 1, "source_lang_es": "es",
     "source_title_es": "Holotipo", "source_revid_es": 2},
    {"term_id": "species", "category": "classification", "term_en": "species",
     "term_es": "especie", "forms_en": [], "forms_es": ["especies"], "pages_en": 9, "pages_es": 9,
     "definition_en": "A group of organisms that can breed.", "definition_es": None,
     "source_title_en": "Species", "source_revid_en": 3, "source_lang_es": None,
     "source_title_es": None, "source_revid_es": None},
]  # fmt: skip


def test_terms_are_marked_once_and_definitions_mark_other_terms():
    from paleo.site.glossary import Glossary

    g = Glossary(ROWS, "en", "/pa/en/glossary.html")
    used: set[str] = set()
    out = g.mark("Two Holotypes &amp; a holotype.", used)
    assert out.count('class="gl"') == 1 and 'data-gl="holotype">Holotypes</a>' in out
    assert g.mark("another holotype", used) == "another holotype"  # once per page
    assert 'data-gl="species"' in g.definition_html("holotype")
    assert 'data-gl="holotype"' not in g.definition_html("holotype")  # never itself
    data = g.page_data({"holotype"})
    assert set(data) == {"holotype", "species"}  # the closure of what popovers open
    assert data["holotype"]["url"].endswith("title=Holotype&oldid=1")
    es = Glossary(ROWS, "es", "/pa/es/glosario.html")
    assert set(es.terms) == {"holotype"}  # no Spanish definition published for species
    assert es.source("holotype")["url"].startswith("https://es.wikipedia.org/")


def test_prose_marks_terms_outside_names_and_pages_carry_their_data():
    import datetime as dt

    from paleo.site.build import Page, SiteBuilder
    from paleo.site.data import SiteData

    taxa = [{"taxon_name": n, "taxon_key": k, "page_type": "genus", "image_url": None}
            for n, k in (("Tyrannosaurus", "tyrannosaurus"), ("Holotypus", "holotypus"))
            ]  # fmt: skip
    b = SiteBuilder(SiteData(taxa, {}, {}, {}, {}, dt.date(2026, 11, 1), glossary=ROWS),
                    base="/pa")  # fmt: skip
    b._marked = {"glossary": set(), "taxa": set()}
    out = str(b.prose("The holotype of Tyrannosaurus is a holotype.", "en", None))
    assert out.count('class="gl"') == 1
    assert '<a class="taxon-link" href="/pa/en/taxa/tyrannosaurus.html"' in out
    assert b._marked["taxa"] == {"tyrannosaurus"}
    b._marked = None
    assert 'class="gl"' not in str(b.prose("A holotype.", "en", None))  # only taxon pages
    pages = [p for p in b.pages() if p.kind == "glossary"]
    assert {p.lang for p in pages} == {"es", "en"}
    html = b.render(next(p for p in pages if p.lang == "en"))
    assert 'id="holotype"' in html and 'id="species"' in html
    assert isinstance(pages[0], Page)
