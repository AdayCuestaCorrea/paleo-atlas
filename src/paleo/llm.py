"""Provider-agnostic LLM access (OpenAI-compatible chat API).

The same code talks to a local model through Ollama (development and large
batches, no quota) or to Groq (scheduled runs in GitHub Actions). Switching
provider is configuration, not code — free tiers change or disappear, so the
pipeline must not depend on one of them (ALCANCE.md, decision A18).

Three safeguards keep generation within free quotas:

* **Structured output** — every call returns JSON validated with pydantic.
* **Rate limiter** — requests/tokens per minute and tokens per day per model;
  when the daily quota is gone, :class:`QuotaExhausted` is raised and the
  taxon page keeps its fallback text until the next run.
* **Content cache** — the same prompt to the same model is answered from disk,
  so a page is generated once per change, never on every run.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from paleo.config import get_paths, project_root
from paleo.http import HttpError, post_json
from paleo.store import _atomic_write

log = logging.getLogger(__name__)

# Rough token estimate used before a call (the response reports exact usage).
CHARS_PER_TOKEN = 4


class QuotaExhausted(RuntimeError):
    """The daily token or request quota of a model is used up."""


class LLMOutputError(RuntimeError):
    """The model did not return valid JSON for the requested schema."""


@dataclass(frozen=True)
class Limits:
    requests_per_minute: int
    tokens_per_minute: int
    requests_per_day: int
    tokens_per_day: int


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_env: tuple[str, ...] = ()
    limits: Limits | None = None  # None = local, no quota
    extra_body: dict[str, Any] = field(default_factory=dict)

    def api_key(self) -> str | None:
        load_dotenv()
        for var in self.api_key_env:
            if value := os.environ.get(var):
                return value
        return None


# Groq free-tier limits of the user's account (checked 2026-11-02), per model.
GROQ_FREE = Limits(
    requests_per_minute=30, tokens_per_minute=8_000, requests_per_day=1_000, tokens_per_day=200_000
)

PROVIDERS: dict[str, Provider] = {
    "ollama": Provider(
        "ollama",
        os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        # Qwen models "think" by default in Ollama; we only want the answer.
        extra_body={"reasoning_effort": "none"},
    ),
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1",
        # The repo secret is GROQ_API_KEY; the local .env uses GROQ_KEY.
        api_key_env=("GROQ_API_KEY", "GROQ_KEY"),
        limits=GROQ_FREE,
        extra_body={"reasoning_effort": "low"},
    ),
}


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from the repo's ``.env`` without overriding the env."""
    path = path or project_root() / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


# --------------------------------------------------------------------------- quota


class RateLimiter:
    """Per-model request/token budget: waits per minute, stops per day.

    Daily usage is persisted (local cache, never versioned) so separate runs
    on the same day share the budget.
    """

    def __init__(
        self,
        limits: Limits,
        usage_path: Path,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], dt.date] = dt.date.today,
    ) -> None:
        self.limits = limits
        self.usage_path = usage_path
        self.clock = clock
        self.sleep = sleep
        self.today = today
        self._window: deque[tuple[float, int]] = deque()

    def _load(self) -> dict[str, Any]:
        if self.usage_path.exists():
            return json.loads(self.usage_path.read_text(encoding="utf-8"))
        return {}

    def _day(self, model: str) -> dict[str, int]:
        usage = self._load().get(self.today().isoformat(), {})
        return usage.get(model, {"requests": 0, "tokens": 0})

    def acquire(self, model: str, estimated_tokens: int) -> None:
        """Block until a call of ``estimated_tokens`` fits; raise if the day is spent."""
        if estimated_tokens > self.limits.tokens_per_minute:
            raise ValueError(
                f"{model}: a single call of ~{estimated_tokens} tokens exceeds the "
                f"{self.limits.tokens_per_minute} tokens/minute limit; split the input"
            )
        day = self._day(model)
        if (
            day["requests"] + 1 > self.limits.requests_per_day
            or day["tokens"] + estimated_tokens > self.limits.tokens_per_day
        ):
            raise QuotaExhausted(f"{model}: daily quota used ({day['tokens']} tokens)")
        while True:
            now = self.clock()
            while self._window and now - self._window[0][0] >= 60:
                self._window.popleft()
            tokens = sum(t for _, t in self._window)
            if (
                len(self._window) < self.limits.requests_per_minute
                and tokens + estimated_tokens <= self.limits.tokens_per_minute
            ):
                return
            self.sleep(max(0.5, 60 - (now - self._window[0][0])))

    def record(self, model: str, tokens: int) -> None:
        self._window.append((self.clock(), tokens))
        usage = self._load()
        day = usage.setdefault(self.today().isoformat(), {}).setdefault(
            model, {"requests": 0, "tokens": 0}
        )
        day["requests"] += 1
        day["tokens"] += tokens
        # Keep only the last week to stay small.
        for key in sorted(usage)[:-7]:
            del usage[key]
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(self.usage_path, json.dumps(usage, indent=1) + "\n")


# --------------------------------------------------------------------------- client


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)


def parse_json(content: str) -> Any:
    """JSON from a model answer, tolerating markdown fences and leading prose."""
    text = _FENCE.sub("", content.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
        if start < 0:
            raise
        return json.loads(text[start:])


@dataclass
class CallStats:
    calls: int = 0
    cached: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


class LLM:
    """Chat client for one provider and model, returning validated JSON."""

    def __init__(
        self,
        provider: str | Provider,
        model: str,
        *,
        client: httpx.Client | None = None,
        cache_dir: Path | None = None,
        limiter: RateLimiter | None = None,
        temperature: float = 0.2,
        timeout: float = 600.0,
    ) -> None:
        self.provider = PROVIDERS[provider] if isinstance(provider, str) else provider
        self.model = model
        self.temperature = temperature
        cache_root = get_paths().data / "cache"
        self.cache_dir = cache_dir if cache_dir is not None else cache_root / "llm"
        if limiter is None and self.provider.limits is not None:
            limiter = RateLimiter(self.provider.limits, cache_root / "llm_usage.json")
        self.limiter = limiter
        self.client = client or httpx.Client(timeout=httpx.Timeout(timeout))
        self.stats = CallStats()
        self._schema_mode = "json_schema"  # downgraded to json_object if unsupported

    @property
    def label(self) -> str:
        return f"{self.provider.name}/{self.model}"

    def _cache_path(self, payload: dict[str, Any]) -> Path:
        key = json.dumps(
            {"provider": self.provider.name, **payload}, sort_keys=True, ensure_ascii=False
        )
        return self.cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}.json"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider.api_key_env:
            key = self.provider.api_key()
            if not key:
                names = " or ".join(self.provider.api_key_env)
                raise RuntimeError(f"Missing API key for {self.provider.name}: set {names}")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _response_format(self, schema_name: str, schema: dict[str, Any]) -> dict[str, Any]:
        if self._schema_mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": False},
            }
        return {"type": "json_object"}

    def complete_json[T: BaseModel](
        self,
        system: str,
        user: str,
        output: type[T],
        *,
        max_tokens: int = 2_000,
        use_cache: bool = True,
    ) -> T:
        """Ask for an answer matching ``output`` (a pydantic model) and validate it."""
        schema = output.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": f"{system}\n\nAnswer with JSON matching this schema:\n"
                f"{json.dumps(schema, ensure_ascii=False)}",
            },
            {"role": "user", "content": user},
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            **self.provider.extra_body,
        }
        cache_key = {k: payload[k] for k in ("model", "messages", "temperature", "max_tokens")}
        cache_path = self._cache_path(cache_key)
        if use_cache and cache_path.exists():
            self.stats.cached += 1
            content = json.loads(cache_path.read_text(encoding="utf-8"))["content"]
            return output.model_validate(parse_json(content))

        payload["response_format"] = self._response_format(output.__name__, schema)
        # A cut or malformed answer gets one more try with twice the room; the cache
        # keeps the first key, so a later run reuses the good answer.
        for attempt in range(2):
            try:
                content = self._answer(payload, messages)
                result = output.model_validate(parse_json(content))
                break
            except (json.JSONDecodeError, ValidationError, HttpError) as exc:
                if isinstance(exc, HttpError) and "json_validate_failed" not in str(exc):
                    raise
                if attempt:
                    raise LLMOutputError(f"{self.label}: invalid output ({exc})") from exc
                log.warning("%s: invalid output, retrying with more tokens (%s)", self.label, exc)
                payload["max_tokens"] = max_tokens * 2
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        record = {"model": self.label, "created": dt.datetime.now(dt.UTC).isoformat()}
        _atomic_write(cache_path, json.dumps({**record, "content": content}, ensure_ascii=False))
        return result

    def _answer(self, payload: dict[str, Any], messages: list[dict[str, str]]) -> str:
        estimated = (
            sum(len(m["content"]) for m in messages) // CHARS_PER_TOKEN + payload["max_tokens"]
        )
        if self.limiter:
            self.limiter.acquire(self.model, estimated)
        started = time.monotonic()
        body = self._post(payload)
        self.stats.seconds += time.monotonic() - started
        usage = body.get("usage") or {}
        self.stats.calls += 1
        self.stats.prompt_tokens += usage.get("prompt_tokens", 0)
        self.stats.completion_tokens += usage.get("completion_tokens", 0)
        if self.limiter:
            self.limiter.record(self.model, usage.get("total_tokens", estimated))
        return body["choices"][0]["message"].get("content") or ""

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.provider.base_url}/chat/completions"
        try:
            return post_json(self.client, url, payload, headers=self._headers(), retries=4)
        except HttpError as exc:
            # An answer that failed the server's own JSON check is an invalid output
            # (complete_json retries it), not a sign that json_schema is unsupported.
            if exc.status_code == 400 and "json_validate_failed" in str(exc):
                raise
            # Some models reject json_schema: retry once in plain JSON mode.
            if exc.status_code == 400 and self._schema_mode == "json_schema":
                log.warning("%s: json_schema not accepted, falling back to json_object", self.label)
                self._schema_mode = "json_object"
                payload["response_format"] = {"type": "json_object"}
                return post_json(self.client, url, payload, headers=self._headers(), retries=4)
            raise
