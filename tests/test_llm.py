import datetime as dt
import json

import httpx
import pytest
from pydantic import BaseModel

from paleo.llm import LLM, Limits, LLMOutputError, Provider, QuotaExhausted, RateLimiter, parse_json

LOCAL = Provider("test", "https://llm.test/v1")
LIMITS = Limits(
    requests_per_minute=2, tokens_per_minute=1_000, requests_per_day=5, tokens_per_day=3_000
)


class Answer(BaseModel):
    answer: str
    number: int


def reply(content, tokens=100):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": tokens // 2,
                "completion_tokens": tokens // 2,
                "total_tokens": tokens,
            },
        },
    )


def make_llm(tmp_path, handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLM(LOCAL, "m", client=client, cache_dir=tmp_path / "cache", **kwargs)


def test_valid_json_is_parsed_and_validated(tmp_path):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return reply('{"answer": "ok", "number": 42}')

    llm = make_llm(tmp_path, handler)
    assert llm.complete_json("sys", "user", Answer) == Answer(answer="ok", number=42)
    sent = seen[0]
    assert sent["response_format"]["type"] == "json_schema"
    assert "Answer with JSON matching this schema" in sent["messages"][0]["content"]


def test_answers_are_cached_by_content(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return reply('{"answer": "ok", "number": 1}')

    llm = make_llm(tmp_path, handler)
    llm.complete_json("sys", "user", Answer)
    llm.complete_json("sys", "user", Answer)
    llm.complete_json("sys", "other user", Answer)
    assert len(calls) == 2
    assert llm.stats.cached == 1


def test_invalid_output_raises(tmp_path):
    llm = make_llm(tmp_path, lambda r: reply('{"answer": "ok"}'))
    with pytest.raises(LLMOutputError):
        llm.complete_json("sys", "user", Answer)


def test_cut_answer_is_retried_once_with_more_tokens(tmp_path):
    sent = []
    answers = ['{"answer": "o', '{"answer": "ok", "number": 7}']

    def handler(request):
        sent.append(json.loads(request.content)["max_tokens"])
        return reply(answers.pop(0))

    llm = make_llm(tmp_path, handler)
    assert llm.complete_json("sys", "user", Answer, max_tokens=100).number == 7
    assert sent == [100, 200]
    assert llm.complete_json("sys", "user", Answer, max_tokens=100).number == 7  # cached
    assert llm.stats.calls == 2


def test_json_schema_is_downgraded_when_rejected(tmp_path):
    formats = []

    def handler(request):
        body = json.loads(request.content)
        formats.append(body["response_format"]["type"])
        if body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": {"message": "json_schema not supported"}})
        return reply('{"answer": "ok", "number": 2}')

    llm = make_llm(tmp_path, handler)
    assert llm.complete_json("sys", "user", Answer).number == 2
    assert formats == ["json_schema", "json_object"]


def test_an_answer_the_server_finds_invalid_is_an_invalid_output(tmp_path):
    """Groq checks the JSON itself and answers 400 json_validate_failed: retried like a
    cut answer, then LLMOutputError (the caller skips the batch), and json_schema stays."""
    formats = []
    error = {"code": "json_validate_failed", "message": "Failed to validate JSON."}
    failed = httpx.Response(400, json={"error": error})

    def handler(request):
        formats.append(json.loads(request.content)["response_format"]["type"])
        return failed if len(formats) < 3 else reply('{"answer": "ok", "number": 3}')

    llm = make_llm(tmp_path, handler)
    with pytest.raises(LLMOutputError):
        llm.complete_json("sys", "user", Answer)
    assert llm.complete_json("sys", "user", Answer).number == 3
    assert formats == ["json_schema"] * 3


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here it is: {"a": 1}') == {"a": 1}


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_limiter_waits_when_the_minute_budget_is_used(tmp_path):
    clock = FakeClock()
    limiter = RateLimiter(LIMITS, tmp_path / "usage.json", clock=clock, sleep=clock.sleep)
    limiter.acquire("m", 600)
    limiter.record("m", 600)
    limiter.acquire("m", 600)  # 1,200 > 1,000 tokens/minute: must wait for the window
    assert clock.sleeps and clock.now >= 60


def test_limiter_stops_when_the_day_is_spent(tmp_path):
    day = dt.date(2026, 11, 2)
    limiter = RateLimiter(LIMITS, tmp_path / "usage.json", today=lambda: day, sleep=lambda s: None)
    for _ in range(3):
        limiter.record("m", 900)
    with pytest.raises(QuotaExhausted):
        limiter.acquire("m", 500)
    # Another day starts with a fresh budget.
    other = RateLimiter(LIMITS, tmp_path / "usage.json", today=lambda: day + dt.timedelta(days=1))
    other.acquire("m", 500)


def test_a_single_call_bigger_than_the_minute_budget_is_refused(tmp_path):
    limiter = RateLimiter(LIMITS, tmp_path / "usage.json")
    with pytest.raises(ValueError, match="split the input"):
        limiter.acquire("m", 5_000)


def test_usage_is_recorded_from_the_response(tmp_path):
    limiter = RateLimiter(LIMITS, tmp_path / "usage.json", sleep=lambda s: None)
    llm = make_llm(
        tmp_path, lambda r: reply('{"answer": "ok", "number": 3}', tokens=321), limiter=limiter
    )
    llm.complete_json("sys", "user", Answer, max_tokens=100)
    usage = json.loads((tmp_path / "usage.json").read_text())
    (day,) = usage.values()
    assert day["m"] == {"requests": 1, "tokens": 321}
