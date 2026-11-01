import datetime as dt
import json

import httpx

from paleo.http import make_client
from paleo.ingest import crossref

DAY = dt.date(2026, 11, 2)
DOI = "10.1126/science.adx5486"


def work(**extra):
    return {
        "DOI": DOI,
        "type": "journal-article",
        "title": ["Scimitar-crested <i>Spinosaurus</i> species"],
        "container-title": ["Science"],
        "ISSN": ["0036-8075"],
        "abstract": "<jats:p>Copyrighted abstract text.</jats:p>",
        "score": 1.0,
        "indexed": {"date-time": "2026-11-01T00:00:00Z"},
        **extra,
    }


def handler_for(messages):
    def handler(request):
        doi = request.url.path.removeprefix("/works/")
        if doi not in messages:
            return httpx.Response(404, text="Resource not found.")
        return httpx.Response(200, json={"status": "ok", "message": messages[doi]})

    return handler


def test_abstract_is_never_written_to_the_raw_store(tmp_path):
    raw, cache = tmp_path / "raw", tmp_path / "cache"
    with make_client(httpx.MockTransport(handler_for({DOI: work()}))) as client:
        crossref.ingest_dois(client, [DOI], raw_root=raw, cache_root=cache, today=DAY)
    stored = crossref.store(raw).latest(DOI)
    assert stored["payload"]["work"]["title"][0].startswith("Scimitar")
    assert "abstract" not in json.dumps(stored)
    assert not any("abstract" in p.read_text() for p in raw.rglob("*.json"))
    cached = list((cache / "crossref_abstracts").glob("*.json"))
    assert len(cached) == 1
    assert "Copyrighted abstract" in cached[0].read_text()


def test_volatile_fields_do_not_create_versions(tmp_path):
    messages = {DOI: work()}
    with make_client(httpx.MockTransport(handler_for(messages))) as client:
        crossref.ingest_dois(client, [DOI], raw_root=tmp_path, cache_root=tmp_path, today=DAY)
        messages[DOI] = work(score=9.9, indexed={"date-time": "2026-12-01T00:00:00Z"})
        result = crossref.ingest_dois(
            client, [DOI], raw_root=tmp_path, cache_root=tmp_path, refresh=True
        )
    assert result.new_versions == 0


def test_a_new_retraction_creates_a_new_version(tmp_path):
    messages = {DOI: work()}
    retraction = [{"DOI": "10.1/r", "type": "retraction", "source": "retraction-watch"}]
    with make_client(httpx.MockTransport(handler_for(messages))) as client:
        crossref.ingest_dois(client, [DOI], raw_root=tmp_path, cache_root=tmp_path, today=DAY)
        messages[DOI] = work(**{"updated-by": retraction})
        result = crossref.ingest_dois(
            client,
            [DOI],
            raw_root=tmp_path,
            cache_root=tmp_path,
            refresh=True,
            today=DAY + dt.timedelta(days=30),
        )
    assert result.new_versions == 1
    latest = crossref.store(tmp_path).latest(DOI)["payload"]["work"]
    assert latest["updated-by"][0]["type"] == "retraction"


def test_doi_unknown_to_crossref_is_stored_as_not_found(tmp_path):
    other = "10.5281/zenodo.22944014"  # a DataCite DOI
    with make_client(httpx.MockTransport(handler_for({}))) as client:
        result = crossref.ingest_dois(
            client, [other], raw_root=tmp_path, cache_root=tmp_path, today=DAY
        )
    assert (result.found, result.not_found) == (0, 1)
    assert crossref.store(tmp_path).latest(other)["payload"] == {"doi": other, "found": False}


def test_dois_of_interest_are_normalized(tmp_path):
    folder = tmp_path / "wikipedia" / "page" / "1"
    folder.mkdir(parents=True)
    (folder / "new_taxa.jsonl").write_text(
        json.dumps({"references": [{"doi": "10.1/ABC "}]}) + "\n"
    )
    (folder / "research.jsonl").write_text(
        json.dumps({"references": [{"doi": "10.1/abc"}, {"doi": None}]}) + "\n"
    )
    assert crossref.dois_of_interest(tmp_path) == ["10.1/abc"]
