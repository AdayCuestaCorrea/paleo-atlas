"""Polite HTTP client shared by every ingestion step.

Rules (ALCANCE.md §5): identifiable User-Agent, requests in series (never in
parallel), gzip, and retries with exponential backoff on throttling or
transient server errors. MediaWiki's ``maxlag`` errors are retried as well.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from paleo.config import USER_AGENT

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    """Raised when a request fails (after every retry, for transient errors)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Client with our identity. ``transport`` lets tests inject a mock."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
        transport=transport,
    )


def get_json(
    client: httpx.Client,
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    retries: int = 5,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """GET ``url`` and return its JSON body, retrying transient failures.

    Retries on HTTP 429/5xx, network errors and MediaWiki ``maxlag`` errors,
    honouring ``Retry-After`` when the server sends it.
    """
    last_error = "unknown error"
    for attempt in range(retries + 1):
        wait = backoff * 2**attempt
        try:
            response = client.get(url, params=params, headers=headers)
        except httpx.TransportError as exc:
            last_error = f"network error: {exc}"
        else:
            if response.status_code in RETRY_STATUS:
                last_error = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = max(wait, float(retry_after))
            elif response.is_error:
                raise HttpError(
                    f"HTTP {response.status_code} for {response.url}", response.status_code
                )
            else:
                body = response.json()
                error = body.get("error") if isinstance(body, dict) else None
                if error and error.get("code") == "maxlag":
                    last_error = "MediaWiki maxlag"
                elif error:
                    raise HttpError(f"API error {error.get('code')}: {error.get('info')}")
                else:
                    return body
        if attempt < retries:
            log.warning("Retrying %s in %.0fs (%s)", url, wait, last_error)
            sleep(wait)
    raise HttpError(f"Giving up on {url} after {retries + 1} attempts: {last_error}")
