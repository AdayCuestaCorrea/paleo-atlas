"""News from paleontology feeds (F9, ALCANCE.md §5; Phase 5).

Only outlets whose terms allow reuse are read (seed ``dbt/seeds/news_feeds.csv``):
the headline, the link, the date and, where allowed, the feed's own summary,
unmodified. One raw-store key per article (a hash of its canonical link), so an
article in several feeds of the same outlet is stored once; it is stored again only
if its headline, date or summary change.
"""

from __future__ import annotations

import csv
import datetime as dt
import email.utils
import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from paleo.config import project_root
from paleo.http import HttpError, get_text
from paleo.store import RawStore

log = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"
TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|src$)", re.I)


@dataclass(frozen=True)
class Feed:
    feed: str
    outlet: str
    lang: str
    url: str
    store_summary: bool


@dataclass
class NewsResult:
    feeds: int = 0
    items: int = 0
    new_versions: int = 0
    failed: list[str] = field(default_factory=list)


def store(raw_root: Path | None = None) -> RawStore:
    return RawStore("news", "items", raw_root=raw_root)


def load_feeds(seed: Path | None = None) -> list[Feed]:
    path = seed or project_root() / "dbt" / "seeds" / "news_feeds.csv"
    with path.open(encoding="utf-8") as f:
        return [
            Feed(r["feed"], r["outlet"], r["lang"], r["url"], r["store_summary"] == "true")
            for r in csv.DictReader(f)
        ]


def canonical_url(url: str) -> str:
    """The article's link without tracking parameters or fragment, on https, so the
    same article keeps one key whichever feed it came from."""
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not TRACKING.match(k)])
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    return urlunsplit((scheme, parts.netloc.lower(), parts.path, query, ""))


def item_key(url: str) -> str:
    return hashlib.sha1(canonical_url(url).encode()).hexdigest()[:16]


def _text(value: str | None) -> str:
    """Plain text: tags stripped, entities decoded, spaces collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def _date(value: str | None) -> str | None:
    """RFC 822 (RSS) or ISO 8601 (Atom) → ISO 8601 in UTC."""
    if not value:
        return None
    try:
        when = email.utils.parsedate_to_datetime(value)
    except TypeError, ValueError:
        try:
            when = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    return when.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")


def parse_feed(body: str, feed: Feed) -> list[dict[str, Any]]:
    """The articles of an RSS 2.0 or Atom feed, as raw-store payloads."""
    root = ET.fromstring(body)
    out = []
    for item in root.iter("item"):  # RSS 2.0
        link = (item.findtext("link") or item.findtext("guid") or "").strip()
        out.append((link, item.findtext("title"), item.findtext("pubDate"),
                    item.findtext("description")))  # fmt: skip
    for entry in root.iter(ATOM + "entry"):  # Atom
        links = entry.findall(ATOM + "link")
        link = next((a.get("href") for a in links if a.get("rel", "alternate") == "alternate"),
                    links[0].get("href") if links else "")  # fmt: skip
        published = entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated")
        out.append((link or "", entry.findtext(ATOM + "title"), published,
                    entry.findtext(ATOM + "summary")))  # fmt: skip
    payloads = []
    for link, title, published, summary in out:
        if not link or not _text(title):
            continue
        payload = {
            "url": canonical_url(link),
            "outlet": feed.outlet,
            "lang": feed.lang,
            "title": _text(title),
            "published": _date(published),
        }
        if feed.store_summary and _text(summary):
            payload["summary"] = _text(summary)
        payloads.append(payload)
    return payloads


def fetch_feed(client: httpx.Client, feed: Feed) -> list[dict[str, Any]]:
    return parse_feed(get_text(client, feed.url, retries=2), feed)


def ingest_feeds(
    client: httpx.Client,
    feeds: list[Feed],
    *,
    raw_root: Path | None = None,
    today: dt.date | None = None,
) -> NewsResult:
    """Every article of every feed; a feed that fails is logged and skipped."""
    items = store(raw_root)
    result, seen = NewsResult(feeds=len(feeds)), set()
    for feed in feeds:
        try:
            payloads = fetch_feed(client, feed)
        except (HttpError, httpx.HTTPError, ET.ParseError) as exc:
            log.warning("News feed %s failed: %s", feed.feed, exc)
            result.failed.append(feed.feed)
            continue
        for payload in payloads:
            key = item_key(payload["url"])
            if key in seen:  # the same article in another feed of the outlet
                continue
            seen.add(key)
            result.items += 1
            result.new_versions += items.save_if_changed(key, payload, today).created
    items.flush()
    return result


def has_new_items(client: httpx.Client, feeds: list[Feed], raw_root: Path | None = None) -> bool:
    """Whether any feed lists an article not stored yet (nothing is saved)."""
    stored = set(store(raw_root).stored_keys())
    for feed in feeds:
        try:
            payloads = fetch_feed(client, feed)
        except (HttpError, httpx.HTTPError, ET.ParseError) as exc:
            log.warning("News feed %s failed: %s", feed.feed, exc)
            continue
        if any(item_key(p["url"]) not in stored for p in payloads):
            return True
    return False
