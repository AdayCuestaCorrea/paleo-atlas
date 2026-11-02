"""Ingestion tests with a mocked transport: no network access."""

import json

import httpx
import pytest

from paleo.config import USER_AGENT
from paleo.http import HttpError, get_json, make_client
from paleo.ingest import wikipedia as wiki

TITLE = "2026 in archosaur paleontology"


def mediawiki_response(revid: int, content: str | None = None) -> dict:
    revision = {"revid": revid, "timestamp": "2026-11-01T08:48:46Z"}
    if content is not None:
        revision["slots"] = {"main": {"content": content}}
    return {"query": {"pages": [{"pageid": 81645351, "title": TITLE, "revisions": [revision]}]}}


class FakeWikipedia:
    """Serves a fixed revision and records every request it receives."""

    def __init__(self, revid: int = 100, content: str = "== Birds ==") -> None:
        self.revid = revid
        self.content = content
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        with_content = "content" in request.url.params.get("rvprop", "")
        body = mediawiki_response(self.revid, self.content if with_content else None)
        return httpx.Response(200, json=body)

    @property
    def content_requests(self) -> int:
        return sum("content" in r.url.params.get("rvprop", "") for r in self.requests)


@pytest.fixture
def fake():
    return FakeWikipedia()


@pytest.fixture
def client(fake):
    with make_client(httpx.MockTransport(fake)) as c:
        yield c


def test_user_agent_identifies_the_bot(client, fake):
    wiki.latest_revision(client, TITLE)
    ua = fake.requests[0].headers["User-Agent"]
    assert ua == USER_AGENT
    assert "bot" in ua
    assert "github.com/AdayCuestaCorrea/paleo-atlas" in ua
    assert "@" in ua  # contact address


def test_requests_ask_for_maxlag_and_json(client, fake):
    wiki.latest_revision(client, TITLE)
    params = fake.requests[0].url.params
    assert params["maxlag"] == "5"
    assert params["format"] == "json"


def test_ingest_stores_raw_revision_with_metadata(client, tmp_path):
    result = wiki.ingest_page(client, TITLE, raw_root=tmp_path)
    assert result.created
    assert result.path == tmp_path / "wikipedia" / "2026_in_archosaur_paleontology" / "100.json"
    record = json.loads(result.path.read_text(encoding="utf-8"))
    assert record["revid"] == 100
    assert record["wikitext"] == "== Birds =="
    assert record["license"].startswith("CC BY-SA 4.0")


def test_ingest_is_idempotent_per_revision(client, fake, tmp_path):
    wiki.ingest_page(client, TITLE, raw_root=tmp_path)
    second = wiki.ingest_page(client, TITLE, raw_root=tmp_path)
    assert not second.created
    assert fake.content_requests == 1  # the content is not downloaded again
    assert wiki.stored_revids(TITLE, tmp_path) == [100]


def test_new_revision_is_detected_and_stored_alongside(client, fake, tmp_path):
    wiki.ingest_page(client, TITLE, raw_root=tmp_path)
    assert not wiki.has_new_revision(client, TITLE, tmp_path)
    fake.revid = 101
    assert wiki.has_new_revision(client, TITLE, tmp_path)
    wiki.ingest_page(client, TITLE, raw_root=tmp_path)
    assert wiki.stored_revids(TITLE, tmp_path) == [100, 101]


def test_missing_page_raises(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"query": {"pages": [{"title": TITLE, "missing": True}]}})

    with make_client(httpx.MockTransport(handler)) as c, pytest.raises(LookupError):
        wiki.latest_revision(c, TITLE)


def test_retries_on_server_error_and_maxlag():
    replies = [
        httpx.Response(503),
        httpx.Response(200, json={"error": {"code": "maxlag", "info": "lagged"}}),
        httpx.Response(200, json={"ok": True}),
    ]
    waits: list[float] = []
    with make_client(httpx.MockTransport(lambda r: replies.pop(0))) as c:
        body = get_json(c, "https://example.org/api", sleep=waits.append)
    assert body == {"ok": True}
    assert waits == [2.0, 4.0]  # exponential backoff


def test_gives_up_after_the_last_retry():
    transport = httpx.MockTransport(lambda r: httpx.Response(503))
    with make_client(transport) as c, pytest.raises(HttpError, match="after 3 attempts"):
        get_json(c, "https://example.org/api", retries=2, sleep=lambda s: None)


def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    with make_client(httpx.MockTransport(handler)) as c, pytest.raises(HttpError):
        get_json(c, "https://example.org/api", sleep=lambda s: None)
    assert len(calls) == 1


def test_check_exits_2_when_the_check_itself_fails(monkeypatch):
    from typer.testing import CliRunner

    from paleo import cli
    from paleo.http import HttpError

    def boom(*args, **kwargs):
        raise HttpError("HTTP 503 for the API", 503)

    monkeypatch.setattr(cli.wiki_ingest, "has_new_revision", boom)
    result = CliRunner().invoke(cli.app, ["check"])
    assert result.exit_code == 2  # not 1: an outage must not pass for "no changes"
