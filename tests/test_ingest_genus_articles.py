"""Wikipedia articles and Wikidata ids of the encyclopedia genera (fake transport)."""

import datetime as dt
from urllib.parse import parse_qs

import httpx

from paleo.http import make_client
from paleo.ingest import genus_articles as ga

DAY = dt.date(2026, 11, 2)


def wikipedia(request):
    titles = request.url.params["titles"].split("|")
    pages, redirects = [], []
    for t in titles:
        if t == "Paperus":  # an article whose "lead image" is a PDF
            pages.append({"title": "Paperus", "pageimage": "10_24072_paper.pdf"})
        elif t == "Coloradia":  # the moth's article, with a lead image
            pages.append(
                {
                    "title": "Coloradia",
                    "pageprops": {"wikibase_item": "Q116579"},
                    "pageimage": "Coloradia_pandora_adult.jpg",
                }
            )
        elif t == "Rex":  # a disambiguation page
            pages.append({"title": "Rex", "pageprops": {"disambiguation": ""}})
        elif t == "Fregilupus":  # redirected to its common name
            redirects.append({"from": "Fregilupus", "to": "Hoopoe starling"})
            pages.append({"title": "Hoopoe starling", "pageprops": {"wikibase_item": "Q2"}})
        else:
            pages.append({"title": t, "missing": True})
    return {"query": {"redirects": redirects, "pages": pages}}


def wikidata(request):
    query = parse_qs(request.content.decode())["query"][0]
    rows = []
    if "P171" in query:  # ancestors of each item, compared with the roots in Python
        if "wd:Q116579" in query:  # the moth: insects, not a root of the scope
            rows.append(
                {
                    "item": {"value": "http://www.wikidata.org/entity/Q116579"},
                    "anc": {"value": "http://www.wikidata.org/entity/Q1390"},
                }
            )
        if "wd:Q2" in query:  # the starling descends from Archosauria
            rows.append(
                {
                    "item": {"value": "http://www.wikidata.org/entity/Q2"},
                    "anc": {"value": "http://www.wikidata.org/entity/Q130910"},
                }
            )
        return {"results": {"bindings": rows}}
    if "wd:Q116579" in query:
        rows.append(
            {
                "item": {"value": "http://www.wikidata.org/entity/Q116579"},
                "pbdb": {"value": "38639"},
            }
        )
    if "wd:Q2" in query:
        rows.append(
            {
                "item": {"value": "http://www.wikidata.org/entity/Q2"},
                "pbdb": {"value": "371453"},
                "es": {"value": "https://es.wikipedia.org/wiki/Abubilla_de_Reuni%C3%B3n"},
            }
        )
    return {"results": {"bindings": rows}}


def handler(request):
    if request.url.host == "query.wikidata.org":
        return httpx.Response(200, json=wikidata(request))
    return httpx.Response(200, json=wikipedia(request))


def test_lookups_store_the_article_wikidata_ids_and_lead_image(tmp_path):
    with make_client(transport=httpx.MockTransport(handler)) as client:
        r = ga.ingest_genus_articles(
            client, ["Coloradia", "Fregilupus", "Rex", "Nopeus", "Paperus"],
            raw_root=tmp_path, today=DAY,
        )  # fmt: skip
    assert (r.looked_up, r.with_article) == (5, 4)
    store = ga.store(tmp_path)
    moth = store.latest("Coloradia")["payload"]
    assert moth["pbdb_ids"] == ["38639"] and moth["in_scope_tree"] is False
    assert moth["lead_image"] == "Coloradia_pandora_adult.jpg"
    starling = store.latest("Fregilupus")["payload"]
    assert starling["en_title"] == "Hoopoe starling" and starling["redirected"]
    assert starling["es_title"] == "Abubilla de Reunión" and starling["in_scope_tree"]
    assert starling["scope_roots"] == ["Q130910"] and moth["scope_roots"] == []
    assert store.latest("Rex")["payload"]["disambiguation"]
    assert store.latest("Nopeus")["payload"]["en_title"] is None
    assert ga.lead_images(tmp_path) == ["Coloradia_pandora_adult.jpg"]


def test_the_budget_takes_never_looked_up_genera_first(tmp_path):
    seen = []

    def counting(request):
        if request.url.host != "query.wikidata.org":
            seen.extend(request.url.params["titles"].split("|"))
        return handler(request)

    with make_client(transport=httpx.MockTransport(counting)) as client:
        ga.ingest_genus_articles(client, ["Rex"], raw_root=tmp_path, today=DAY)
        later = DAY + dt.timedelta(days=40)  # Rex is stale again, but was looked up
        ga.ingest_genus_articles(
            client, ["Rex", "Coloradia"], raw_root=tmp_path, today=later, budget=1
        )
    assert seen == ["Rex", "Coloradia"]


def test_a_failing_wikidata_leaves_those_genera_for_the_next_run(tmp_path):
    def down(request):
        if request.url.host == "query.wikidata.org":
            return httpx.Response(400, text="query timeout")
        return handler(request)

    with make_client(transport=httpx.MockTransport(down)) as client:
        r = ga.ingest_genus_articles(client, ["Coloradia", "Nopeus"], raw_root=tmp_path, today=DAY)
    assert r.failed == 1  # Coloradia has an item whose lookup failed: not saved
    store = ga.store(tmp_path)
    assert store.latest("Coloradia") is None and not store.is_fresh("Coloradia", 30, DAY)
    assert store.latest("Nopeus")["payload"]["en_title"] is None  # no item: saved
