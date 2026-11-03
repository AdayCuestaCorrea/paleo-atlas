"""History backwards (Phase 3, H4): PBDB opinions and the yearly pages of past years
feed each taxon's timeline, never the pages, texts or "Latest" of the year."""

import datetime as dt

import httpx

from paleo.config import WikipediaPage
from paleo.http import make_client
from paleo.ingest import pbdb
from paleo.ingest import wikipedia as wiki
from paleo.interim import latest_revision_dirs
from paleo.parse import wikipedia as wiki_parse
from paleo.site.build import claim
from paleo.site.data import SiteData, history
from paleo.site.fallback import basic_sources

DAY = dt.date(2026, 11, 3)


def opinion(oid, tid, sta="belongs to", year="1900", rid=None, otp="U", spl="original spelling"):
    return {"oid": f"opn:{oid}", "otp": otp, "rnk": 5, "nam": "Brontosaurus", "tid": tid,
            "sta": sta, "prl": "Apatosaurus", "spl": spl, "oat": "A", "opy": year,
            "rid": rid or f"ref:{oid}"}  # fmt: skip


def test_only_references_that_can_become_events_are_asked_for():
    rows = [
        opinion(1, "txn:1", year="1879"),  # earliest of txn:1: its description
        opinion(2, "txn:1", year="1950"),  # one more plain "belongs to": not an event
        opinion(3, "txn:1", "subjective synonym of", "1903"),
        opinion(4, "txn:1", year="2015", otp="C"),  # current classification
        opinion(5, "txn:2", year="1990", rid=None),
    ]
    assert pbdb.event_reference_ids(rows) == {"ref:1", "ref:3", "ref:4", "ref:5"}


class FakeOpinions:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/refs/list.json"):
            ids = request.url.params["ref_id"].split(",")
            refs = [{"oid": f"ref:{i}", "tit": "T"} for i in ids]
            return httpx.Response(200, json={"records": refs})
        rows = [opinion(1, "txn:1", year="1879"), opinion(3, "txn:1", "subjective synonym of")]
        return httpx.Response(200, json={"elapsed_time": 0.1, "records": rows})


def test_opinions_are_fetched_monthly_per_block_with_their_references(tmp_path):
    fake = FakeOpinions()
    clades = [c for c in pbdb.scope_clades() if c.pbdb_base_name == "Archosauria"]
    with make_client(transport=httpx.MockTransport(fake)) as client:
        r = pbdb.ingest_opinions(client, clades, raw_root=tmp_path, today=DAY)
        assert (r.records, r.new_versions, r.refs) == (2, 1, 2)
        again = pbdb.ingest_opinions(client, clades, raw_root=tmp_path, today=DAY)
        assert again.skipped_fresh == 1 and len(fake.requests) == 2
        # A month later the opinions are asked again, but known references are not.
        month = DAY + dt.timedelta(31)
        later = pbdb.ingest_opinions(client, clades, raw_root=tmp_path, today=month)
    assert later.refs == 0 and len(fake.requests) == 3
    stored = pbdb.refs_store(tmp_path).latest("Archosauria")["payload"]["records"]
    assert [r["oid"] for r in stored] == ["ref:1", "ref:3"]


def wiki_handler(asked):
    def handler(request):
        title = request.url.params["titles"]
        asked.append(title)
        page = {"title": title, "missing": True}
        if not title.startswith("2010"):
            rev = {"revid": 9, "timestamp": "2025-12-30T00:00:00Z",
                   "slots": {"main": {"content": "x"}}}  # fmt: skip
            page = {"title": title, "pageid": 1, "revisions": [rev]}
        return httpx.Response(200, json={"query": {"pages": [page]}})

    return handler


def test_past_pages_go_to_their_own_folder_and_are_checked_monthly(tmp_path):
    pages = [WikipediaPage("archosaurs", "{year} in archosaur paleontology", True, 2010)]
    assert wiki.past_titles(pages, 2012) == [
        "2010 in archosaur paleontology",
        "2011 in archosaur paleontology",
    ]
    asked = []
    with make_client(transport=httpx.MockTransport(wiki_handler(asked))) as client:
        r = wiki.ingest_past(client, pages, 2012, raw_root=tmp_path, today=DAY)
        assert (r.pages, r.missing, r.new_revisions) == (2, 1, 1)
        assert wiki.stored_revids("2011 in archosaur paleontology", tmp_path, wiki.PAST) == [9]
        assert not (tmp_path / "wikipedia").exists()  # this year's folder is untouched
        n = len(asked)
        again = wiki.ingest_past(client, pages, 2012, raw_root=tmp_path, today=DAY)
        assert again.skipped_fresh == 2
        assert len(asked) == n


def test_past_pages_are_invisible_to_the_steps_of_the_year(tmp_path):
    parsed = wiki_parse.parse_page("2015 in archosaur paleontology", 5, "", None)
    out = wiki_parse.write_interim(parsed, tmp_path, wiki.PAST)
    assert out.parts[-3] == wiki.PAST
    assert latest_revision_dirs(tmp_path) == []  # what names, studies and texts read


def event(year, origin="backfill", precision="year", **kw):
    return {"event_date": dt.date(year, 1, 1), "origin": origin, "date_precision": precision,
            "event_type": "synonymized", "taxon_key": "brontosaurus", **kw}  # fmt: skip


def test_the_history_backwards_is_grouped_by_decade_and_kept_out_of_latest():
    events = [
        event(2026, "tracked", "day", event_type="new_study"),
        event(2015, event_type="revalidated"),
        event(2004),
        event(1903),
    ]
    h = history(events)
    assert [e["event_date"].year for e in h["recent"]] == [2026]
    assert [(d, len(items)) for d, items in h["decades"]] == [(2010, 1), (2000, 1), (1900, 1)]
    assert h["backfill"] == 3
    data = SiteData([{"taxon_key": "brontosaurus"}], {"brontosaurus": events}, {}, {}, {},
                    built_on=dt.date(2026, 11, 3))  # fmt: skip
    data.events["brontosaurus"].append(event(2015, precision="day"))  # dated, but history
    assert [e["event_type"] for e in data.all_events()] == ["new_study"]


def test_claims_put_both_names_in_italics_and_escape_them():
    assert str(claim("{name}, synonym of {other}", "Brontosaurus", "Apatosaurus")) == (
        "<em>Brontosaurus</em>, synonym of <em>Apatosaurus</em>"
    )
    assert "&lt;b&gt;" in str(claim("{name}", "<b>"))


def test_genera_cite_the_past_pages_of_their_history_not_this_years_page():
    genus = {"page_type": "genus", "taxon_name": "Brontosaurus", "pbdb_has_taxon": True,
             "pbdb_taxon_no": "txn:52986"}  # fmt: skip
    events = [
        event(2015, source_title="2015 in archosaur paleontology", doi="10.7717/peerj.857"),
        event(1903, source_title="Paleobiology Database", doi="10.1/riggs"),
    ]
    urls = [s["url"] for s in basic_sources(genus, events, "2026 in archosaur paleontology")]
    assert urls == [
        "https://en.wikipedia.org/wiki/2015_in_archosaur_paleontology",
        "https://paleobiodb.org/classic/basicTaxonInfo?taxon_no=52986",
    ]
