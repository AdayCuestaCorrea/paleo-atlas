"""DOAJ lookups of the journals' ISSNs (secondary reliability signal, §10)."""

import datetime as dt

import httpx

from paleo.http import make_client
from paleo.ingest import crossref, doaj

DAY = dt.date(2026, 11, 2)


def handler(request):
    assert "bot" not in request.headers["user-agent"]  # DOAJ answers 403 to bots
    if "2167-8359" in request.url.path:
        return httpx.Response(200, json={"total": 1, "results": [{
            "id": "abc", "bibjson": {"title": "PeerJ", "eissn": "2167-8359",
                                     "license": [{"type": "CC BY"}]},
        }]})  # fmt: skip
    return httpx.Response(200, json={"total": 0, "results": []})


def test_journals_are_looked_up_once_and_stored(tmp_path):
    works = crossref.store(tmp_path)
    found = {"doi": "10.1/a", "found": True, "work": {"ISSN": ["2167-8359", "0036-8075"]}}
    works.save_if_changed("10.1/a", found, DAY)
    works.save_if_changed("10.1/b", {"doi": "10.1/b", "found": False}, DAY)
    works.flush()
    issns = doaj.issns_of_interest(tmp_path)
    assert issns == ["0036-8075", "2167-8359"]

    with make_client(httpx.MockTransport(handler)) as client:
        r = doaj.ingest_issns(client, issns, raw_root=tmp_path, today=DAY)
        assert (r.listed, r.not_listed, r.new_versions) == (1, 1, 2)
        again = doaj.ingest_issns(client, issns, raw_root=tmp_path, today=DAY)
    assert again.skipped_fresh == 2
    stored = doaj.store(tmp_path).latest("2167-8359")["payload"]
    assert stored["listed"] and stored["title"] == "PeerJ" and stored["licenses"] == ["CC BY"]
