"""Narrative pages of the encyclopedia genera (Phase 3, H6): article texts, sources
and the resumable night batch (fake transport, no model)."""

import datetime as dt

import httpx
from typer.testing import CliRunner

from paleo import cli
from paleo.http import make_client
from paleo.ingest import genus_articles as ga
from paleo.ingest import pbdb
from paleo.narrative import sources

DAY = dt.date(2026, 11, 3)
WIKITEXT = (
    "{{Automatic taxobox|taxon=Testosaurus}}\n"
    "'''Testosaurus''' is an extinct genus of theropod dinosaur from the Late Cretaceous.\n\n"
    "== Discovery ==\nIts first fossils were found in 1901 in Montana by a field party."
)


def wiki_handler(asked: list[tuple[str, list[str]]]):
    def handler(request: httpx.Request) -> httpx.Response:
        lang = request.url.host.split(".")[0]
        titles = request.url.params["titles"].split("|")
        asked.append((lang, titles))
        pages = []
        for t in titles:
            if t == "Hugeosaurus" and len(titles) > 1:  # over the size cap: no content
                pages.append({"title": t, "pageid": 2})
            else:
                rev = {"revid": 7, "timestamp": "2026-11-01T00:00:00Z",
                       "slots": {"main": {"content": WIKITEXT}}}  # fmt: skip
                pages.append({"title": t, "pageid": 1, "revisions": [rev]})
        return httpx.Response(200, json={"query": {"pages": pages}})

    return handler


def test_genus_texts_are_stored_and_a_page_without_content_is_asked_alone(tmp_path):
    asked: list = []
    titles = {"Testosaurus": ("Testosaurus", "Testosaurus"), "Hugeosaurus": ("Hugeosaurus", None)}
    with make_client(transport=httpx.MockTransport(wiki_handler(asked))) as client:
        r = ga.ingest_genus_texts(client, titles, cache_root=tmp_path, today=DAY)
    assert r.found == {"en": 2, "es": 1}
    assert ("en", ["Hugeosaurus"]) in asked  # retried on its own
    stored = ga.text_store("en", tmp_path).latest("Hugeosaurus")["payload"]
    assert stored["found"] and stored["taxon"] == "Hugeosaurus"
    # The new taxa's article store is left alone.
    assert not (tmp_path / "wikipedia_articles").exists()
    with make_client(transport=httpx.MockTransport(wiki_handler(asked := []))) as client:
        again = ga.ingest_genus_texts(client, titles, cache_root=tmp_path, today=DAY)
    assert again.skipped_fresh == 2 and asked == []


def store_genus(cache, genus="Testosaurus", wikitext=WIKITEXT):
    payload = {"taxon": genus, "title": genus, "found": True, "revid": 7, "wikitext": wikitext}
    ga.text_store("en", cache).save_if_changed(genus, payload, DAY)


def store_catalog(raw):
    clade = pbdb.scope_clades()[0]
    record = {"taxon_name": "Testosaurus", "taxon_no": "99", "taxon_attr": "Smith 1902",
              "parent_name": "Tyrannosauridae", "class": "Reptilia",
              "type_taxon": "Testosaurus primus", "early_interval": "Campanian",
              "late_interval": "Maastrichtian", "firstapp_max_ma": 83.6,
              "lastapp_min_ma": 66.0, "n_occs": 4}  # fmt: skip
    pbdb.catalog_store(raw).save_if_changed(clade.pbdb_base_name, {"records": [record]}, DAY)
    sources._CATALOGS.clear()


def test_genus_chunks_read_the_article_and_the_catalog(tmp_path):
    raw, cache = tmp_path / "raw", tmp_path / "cache"
    store_genus(cache)
    store_catalog(raw)
    chunks = sources.genus_chunks_for(
        "Testosaurus", interim_root=tmp_path, raw_root=raw, cache_root=cache
    )
    kinds = [c.source for c in chunks]
    assert kinds.count("wikipedia_article") >= 2 and kinds[-1] == "pbdb"
    pbdb_text = chunks[-1].text
    assert "Smith 1902" in pbdb_text and "Testosaurus primus" in pbdb_text
    assert "Family" not in pbdb_text  # the catalog has no family: the line is left out
    assert all("oldid=7" in c.url for c in chunks if c.source == "wikipedia_article")


def test_long_articles_are_capped_from_the_top(tmp_path, monkeypatch):
    raw, cache = tmp_path / "raw", tmp_path / "cache"
    sections = "".join(f"\n\n== Part {i} ==\n" + "A sentence about bones. " * 30 for i in range(9))
    store_genus(cache, wikitext=WIKITEXT + sections)
    monkeypatch.setitem(sources.GENUS_SOURCE_CHARS, "en", 2_000)
    chunks = sources.genus_chunks_for(
        "Testosaurus", interim_root=tmp_path, raw_root=raw, cache_root=cache
    )
    article = [c for c in chunks if c.source == "wikipedia_article"]
    assert sum(len(c.text) for c in article) <= 2_000
    assert "taxobox" in article[0].title and "introduction" in article[1].title


def test_the_deadline_is_the_next_time_of_day():
    night = dt.datetime(2026, 11, 3, 1, 10)
    assert cli._deadline("07:45", night) == dt.datetime(2026, 11, 3, 7, 45)
    assert cli._deadline("07:45", night.replace(hour=23)) == dt.datetime(2026, 11, 4, 7, 45)
    assert cli._deadline(None, night) is None


def test_queue_puts_long_articles_first_and_leaves_out_new_taxa(tmp_path, monkeypatch):
    monkeypatch.setenv("PALEO_DATA_DIR", str(tmp_path))
    cache = tmp_path / "cache"  # where get_paths() puts the cache under PALEO_DATA_DIR
    store_genus(cache, "Shortus", "short")
    store_genus(cache, "Longus", "long " * 100)
    store_genus(cache, "Newus", "new " * 500)
    monkeypatch.setattr(cli, "_new_taxa", lambda only: ["Newus"])
    assert cli.genus_queue() == ["Longus", "Shortus"]
    assert cli.genus_queue(["shortus"]) == ["Shortus"]


def test_the_batch_skips_finished_pages_before_counting_the_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("PALEO_DATA_DIR", str(tmp_path))
    queue = ["Adone", "Btodo", "Ctodo", "Dtodo"]
    monkeypatch.setattr(cli, "genus_queue", lambda only=None: queue)
    monkeypatch.setattr(cli, "_scientific_names", set)
    monkeypatch.setattr(sources, "genus_chunks_for", lambda g, **kw: [g])
    monkeypatch.setattr(cli, "_facts_unchanged", lambda g, chunks: g == "Adone")
    monkeypatch.setattr("paleo.narrative.write.is_up_to_date", lambda *a: True)
    written = []

    def fake_write(llm, genus, chunks, names):
        if genus == "Ctodo":
            raise RuntimeError("model fell over")
        written.append(genus)
        return {"en": "verified", "es": "verified"}

    monkeypatch.setattr(cli, "_extract_one", lambda llm, g, chunks: "3 facts accepted")
    monkeypatch.setattr(cli, "_write_one", fake_write)
    result = CliRunner().invoke(cli.app, ["narrate", "--limit", "3"])
    assert result.exit_code == 0, result.output
    assert written == ["Btodo", "Dtodo"]  # Adone was up to date; Ctodo failed alone
    assert "Ctodo: skipped (RuntimeError" in result.output
    assert "3 processed, 1 up to date" in result.output


def test_an_answer_cut_short_is_asked_again_in_halves(tmp_path):
    from paleo.llm import LLMOutputError
    from paleo.narrative.facts import Extraction, extract_facts

    text = "Testosaurus lived in Montana 70 million years ago."
    chunks = [
        sources.Chunk(
            f"testosaurus:enwiki:{i}",
            "wikipedia_article",
            "en",
            "T",
            "u",
            "CC BY-SA 4.0",
            True,
            text,
        )
        for i in (1, 2)
    ]
    calls = []

    class FakeLLM:
        label = "fake"

        def complete_json(self, system, user, schema, max_tokens):
            ids = [c.chunk_id for c in chunks if c.chunk_id in user]
            calls.append(ids)
            if len(ids) > 1:
                raise LLMOutputError("Unterminated string")
            fact = {"statement": "It lived in Montana 70 million years ago.", "quote": text,
                    "category": "time_and_habitat", "chunk_id": ids[0]}  # fmt: skip
            return Extraction(facts=[fact])

    r = extract_facts(FakeLLM(), "Testosaurus", chunks, derived_root=tmp_path, cache_root=tmp_path)
    assert calls == [[c.chunk_id for c in chunks], [chunks[0].chunk_id], [chunks[1].chunk_id]]
    assert r.accepted == 1 and r.rejected == 1  # the second one is a duplicate


def test_a_long_article_reads_every_section_opening_and_skips_popular_culture(
    tmp_path, monkeypatch
):
    raw, cache = tmp_path / "raw", tmp_path / "cache"
    filler = "A sentence about the history of research. " * 40
    body = "".join(f"\n\n== History {i} ==\n" + filler for i in range(6))
    body += "\n\n== Paleobiology ==\n" + "It had a strong bite force for its size. " * 20
    body += "\n\n== Cultural significance ==\n" + "It starred in many films and books. " * 20
    store_genus(cache, wikitext=WIKITEXT + body)
    monkeypatch.setitem(sources.GENUS_SOURCE_CHARS, "en", 5_000)
    chunks = sources.genus_chunks_for(
        "Testosaurus", interim_root=tmp_path, raw_root=raw, cache_root=cache
    )
    titles = " ".join(c.title for c in chunks if c.source == "wikipedia_article")
    assert "Paleobiology" in titles  # read although six history sections come first
    assert "Cultural significance" not in titles
    # A short article is kept whole, as before (its sources and facts do not change).
    short = [sources.Chunk(str(i), "wikipedia_article", "en", f"T (S{i})", "u", "x", True, "abc")
             for i in range(3)]  # fmt: skip
    assert sources._capped(short, 5_000) == short
