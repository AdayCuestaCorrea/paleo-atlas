"""GBIF downloads with a fake transport: request, polling, fetch, versioned record."""

import json

import httpx
import pytest

from paleo.http import make_client
from paleo.ingest import gbif


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setattr("paleo.llm.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("GBIF_USERNAME", "user-secret-123")
    monkeypatch.setenv("GBIF_PASSWORD", "pass-secret-456")
    monkeypatch.setenv("GBIF_MAIL", "m@example.org")


def test_missing_credentials_are_named_but_never_shown(monkeypatch):
    monkeypatch.setattr("paleo.llm.load_dotenv", lambda *a, **k: None)
    for name in ("GBIF_USERNAME", "GBIF_PASSWORD", "GBIF_MAIL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GBIF_USERNAME", "someone")
    with pytest.raises(gbif.GbifError) as err:
        gbif.credentials()
    assert "GBIF_PASSWORD" in str(err.value) and "someone" not in str(err.value)


def test_the_filter_keeps_fossils_of_the_included_taxa_minus_the_excluded():
    keep, drop = gbif.taxa_filter()
    assert 44 in keep and 359 in drop  # Chordata, without Mammalia
    pred = gbif.predicate(keep, drop)
    assert pred["predicates"][0] == {"type": "equals", "key": "BASIS_OF_RECORD",
                                     "value": "FOSSIL_SPECIMEN"}  # fmt: skip
    assert pred["predicates"][2]["type"] == "not"


def test_a_download_is_requested_waited_for_fetched_and_recorded(tmp_path, creds, monkeypatch):
    monkeypatch.setenv("PALEO_DATA_DIR", str(tmp_path / "data"))
    seen = {"polls": 0}

    def handler(request):
        if request.url.path.endswith("/download/request"):
            body = json.loads(request.content)
            assert body["predicate"]["predicates"][0]["value"] == "FOSSIL_SPECIMEN"
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(201, text="0001-2026")
        if request.url.path.endswith("/download/0001-2026"):
            seen["polls"] += 1
            done = seen["polls"] >= 2
            return httpx.Response(200, json={
                "key": "0001-2026", "status": "SUCCEEDED" if done else "RUNNING",
                "doi": "10.15468/dl.abc", "downloadLink": "https://x.test/0001.zip",
                "totalRecords": 123, "size": 4, "license": "CC_BY_NC_4_0",
                "created": "2026-11-02T10:00:00"})  # fmt: skip
        if request.url.host == "x.test":
            return httpx.Response(200, content=b"PK..")
        return httpx.Response(404)

    waits = []
    with make_client(transport=httpx.MockTransport(handler)) as client:
        wait = lambda c, k: gbif.wait_download(c, k, sleep=waits.append)  # noqa: E731
        rec, path = gbif.extract(client, raw_root=tmp_path / "raw", wait=wait)
    assert path.read_bytes() == b"PK.." and path.is_relative_to(tmp_path / "data" / "cache")
    assert rec["doi"] == "10.15468/dl.abc" and rec["total_records"] == 123
    assert waits == [30.0]  # polled until it succeeded
    stored = gbif.store(tmp_path / "raw").latest("0001-2026")["payload"]
    assert stored["citation"].endswith("https://doi.org/10.15468/dl.abc")
    saved = json.dumps(stored)  # the credentials are never stored
    assert "user-secret-123" not in saved and "pass-secret-456" not in saved


def test_a_failed_download_stops_with_its_status():
    def handler(request):
        return httpx.Response(200, json={"key": "k", "status": "FAILED"})

    with (
        make_client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(gbif.GbifError, match="FAILED"),
    ):
        gbif.wait_download(client, "k", sleep=lambda s: None)


def test_a_recent_download_is_reused_and_an_old_one_is_not(tmp_path, creds, monkeypatch):
    import datetime as dt

    monkeypatch.setenv("PALEO_DATA_DIR", str(tmp_path / "data"))
    pred = gbif.predicate(*gbif.taxa_filter())
    rec = {"key": "0001-2026", "status": "SUCCEEDED", "predicate": pred,
           "created": "2026-11-02T10:00:00", "doi": "10.15468/dl.abc"}  # fmt: skip
    gbif.store(tmp_path / "raw").save_if_changed("0001-2026", rec, dt.date(2026, 11, 2))
    gbif.store(tmp_path / "raw").flush()
    zip_path = gbif.cache_dir("0001-2026") / "0001-2026.zip"
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"PK..")
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(400, text="no")

    with make_client(transport=httpx.MockTransport(handler)) as client:
        got, path = gbif.extract(client, raw_root=tmp_path / "raw", today=dt.date(2026, 11, 20))
        assert (got["key"], path, requests) == ("0001-2026", zip_path, [])  # no network
        with pytest.raises(gbif.GbifError, match="HTTP 400"):  # 31 days later: a new request
            gbif.extract(client, raw_root=tmp_path / "raw", today=dt.date(2026, 12, 3))
    assert requests and requests[0].endswith("/download/request")
