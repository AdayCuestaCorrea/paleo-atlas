"""News feeds (F9): RSS and Atom, one key per article, summaries only where allowed."""

import datetime as dt

import httpx

from paleo.http import make_client
from paleo.ingest import news

DAY = dt.date(2026, 11, 7)

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>SD</title>
<item><title>Scientists just found dinosaur blood</title>
  <link>http://www.example.org/releases/a.htm?utm_source=rss&amp;id=7#top</link>
  <description>Traces of &lt;b&gt;ancient&lt;/b&gt; blood.</description>
  <pubDate>Fri, 06 Nov 2026 06:28:01 EST</pubDate></item>
<item><title>   </title><link>https://www.example.org/empty.htm</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>TC</title>
<entry><title>Traces of dinosaur blood found</title>
  <link rel="alternate" type="text/html" href="https://tc.example.org/traces-123"/>
  <published>2026-11-05T19:00:00Z</published><updated>2026-11-06T08:00:00Z</updated>
  <summary>A world first.</summary></entry>
</feed>"""

SD = news.Feed("sd", "ScienceDaily", "en", "https://feeds.example.org/sd.xml", True)
SD2 = news.Feed("sd2", "ScienceDaily", "en", "https://feeds.example.org/sd2.xml", True)
TC = news.Feed("tc", "The Conversation", "en", "https://feeds.example.org/tc.atom", False)
DOWN = news.Feed("down", "Down", "es", "https://feeds.example.org/down.xml", True)


def handler(request):
    path = request.url.path
    if path.endswith(("sd.xml", "sd2.xml")):
        return httpx.Response(200, text=RSS)
    if path.endswith("tc.atom"):
        return httpx.Response(200, text=ATOM)
    return httpx.Response(404, text="gone")


def test_links_are_canonical():
    url = "http://WWW.Example.org/a.htm?utm_source=rss&id=7&fbclid=x#top"
    assert news.canonical_url(url) == "https://www.example.org/a.htm?id=7"
    assert news.item_key(url) == news.item_key("https://www.example.org/a.htm?id=7")


def test_rss_and_atom_items_are_parsed():
    (sd,) = news.parse_feed(RSS, SD)  # the item without a headline is skipped
    assert sd == {
        "url": "https://www.example.org/releases/a.htm?id=7",
        "outlet": "ScienceDaily",
        "lang": "en",
        "title": "Scientists just found dinosaur blood",
        "published": "2026-11-06T11:28:01Z",
        "summary": "Traces of ancient blood.",
    }
    (tc,) = news.parse_feed(ATOM, TC)
    assert tc["url"] == "https://tc.example.org/traces-123"
    assert tc["published"] == "2026-11-05T19:00:00Z"  # published, not updated
    assert "summary" not in tc  # this outlet's summary is not kept


def test_ingest_stores_each_article_once_and_survives_a_failing_feed(tmp_path):
    with make_client(httpx.MockTransport(handler)) as client:
        r = news.ingest_feeds(client, [SD, SD2, TC, DOWN], raw_root=tmp_path, today=DAY)
        assert (r.feeds, r.items, r.new_versions, r.failed) == (4, 2, 2, ["down"])
        assert not news.has_new_items(client, [SD, TC, DOWN], raw_root=tmp_path)
        again = news.ingest_feeds(client, [SD, TC], raw_root=tmp_path, today=DAY)
    assert again.new_versions == 0
    stored = news.store(tmp_path)
    assert len(stored.stored_keys()) == 2


def test_a_new_article_is_news(tmp_path):
    with make_client(httpx.MockTransport(handler)) as client:
        news.ingest_feeds(client, [SD], raw_root=tmp_path, today=DAY)
        assert news.has_new_items(client, [SD, TC], raw_root=tmp_path)


def test_the_seed_lists_only_outlets_with_a_license():
    feeds = news.load_feeds()
    assert {f.outlet for f in feeds} == {"ScienceDaily", "The Conversation", "SINC"}
    assert {f.lang for f in feeds} == {"es", "en"}
