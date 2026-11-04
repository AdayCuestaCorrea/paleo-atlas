"""Home page: explorer facets and data, the curiosity carousel and the rendered page."""

import datetime as dt
import re

from paleo.site import explore
from paleo.site.indices import build_indices

COMMONS = (
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6f/Bicharracosaurus_dionidei.png/"
    "960px-Bicharracosaurus_dionidei.png?utm_source=commons.wikimedia.org&utm_content=thumbnail"
)


def genus(name, group="non_avian_dinosaurs", oldest=None, youngest=None, codes=None, **extra):
    return {"taxon_key": name.lower(), "taxon_name": name, "page_type": "genus",
            "taxon_rank": "genus", "taxon_group": group, "family_name": None,
            "first_appearance_max_ma": oldest, "last_appearance_min_ma": youngest,
            "country_codes": codes, **extra}  # fmt: skip


def new_species(name, age, countries, group="pterosaurs"):
    return {"taxon_key": name.lower().replace(" ", "-"), "taxon_name": name, "page_type": "new",
            "taxon_rank": "species", "taxon_group": group, "age_text": age,
            "countries": countries, "country": (countries or [None])[0], "image_url": None,
            "image_source": None, "family_name": None}  # fmt: skip


def text(*curiosities, other="Something else."):
    return {"sections": [
        {"section": "description", "sentences": [{"text": other}]},
        {"section": "curiosities", "sentences": [{"text": c} for c in curiosities]},
    ]}  # fmt: skip


# ----------------------------------------------------------------------- facets


def test_facets_from_ages_words_codes_and_names():
    t = genus("Allosaurus", oldest=155, youngest=145.5, codes=["US", "PT"])
    assert explore.facets(t) == (["jurassic"], "non_avian_dinosaurs", ["us", "pt"])
    # A genus spanning the boundary is in both periods.
    assert explore.facets(genus("X", oldest=150, youngest=140))[0] == ["jurassic", "cretaceous"]
    # New taxa: dated in words, countries by name (an unknown name is left out).
    s = new_species(
        "Hintighernia x", "Early Cretaceous (Valanginian)", ["United Kingdom", "Crimea"]
    )
    assert explore.facets(s) == (["cretaceous"], "pterosaurs", ["uk"])
    assert explore.facets({"taxon_key": "x", "taxon_name": "X"}) == ([], None, [])


def test_genus_facets_agree_with_the_encyclopedia_indices():
    taxa = [
        genus("Tyrannosaurus", oldest=68, youngest=66, codes=["US", "CA"]),
        genus("Allosaurus", oldest=155, youngest=145.5, codes=["US", "PT"]),
        genus("Archaeopteryx", "birds", 151, 149, ["DE"]),
        genus("Dunkleosteus", "placoderms", 382, 358, ["US", "MA"]),
    ]
    idx = build_indices(taxa, ["non_avian_dinosaurs", "birds", "placoderms"])
    entries = explore.explore_entries(
        taxa, groups=["non_avian_dinosaurs", "birds", "placoderms"], curiosities=set(), ranks={}
    )
    for group in idx.groups:
        assert idx.group_count(group) == sum(e["group"] == group for e in entries)
    for period in idx.periods:
        assert idx.period_count(period) == sum(period in e["periods"] for e in entries)
    for code, genera in idx.countries.items():
        assert len(genera) == sum(code in e["countries"] for e in entries)


def test_new_taxa_newest_first_by_the_description_event():
    taxa = [new_species("A a", "Cretaceous", []), new_species("B b", "Cretaceous", []),
            new_species("C c", "Cretaceous", []), genus("Old")]  # fmt: skip
    events = [  # newest first, as SiteData.all_events gives them
        {"taxon_key": "b-b", "event_type": "description", "event_date": dt.date(2026, 10, 2)},
        {"taxon_key": "a-a", "event_type": "new_study", "event_date": dt.date(2026, 10, 1)},
        {"taxon_key": "a-a", "event_type": "description", "event_date": dt.date(2026, 3, 1)},
    ]
    assert explore.new_order(taxa, events) == {"b-b": 0, "a-a": 1, "c-c": 2}


def test_card_thumbnails_are_small_and_untracked():
    assert explore.thumb(COMMONS) == (
        "https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6f/Bicharracosaurus_dionidei.png/"
        "330px-Bicharracosaurus_dionidei.png"
    )
    assert explore.thumb(COMMONS, 960).endswith("/960px-Bicharracosaurus_dionidei.png")
    phylopic = "https://images.phylopic.org/images/abc/raster/1536x306.png"
    assert explore.thumb(phylopic) == phylopic and explore.thumb(None) is None


# -------------------------------------------------------------------- carousel


def photo_genus(name, author="Someone", license_="CC BY-SA 4.0", source="commons", **extra):
    return genus(name, image_url=COMMONS, image_source=source, image_author=author,
                 image_license=license_, **extra)  # fmt: skip


def test_the_carousel_takes_credited_photos_with_curiosities_in_both_languages():
    taxa = [photo_genus("Alpha"), photo_genus("Beta"), photo_genus("Gamma", source="phylopic"),
            photo_genus("Delta", author=None), photo_genus("Epsilon")]  # fmt: skip
    long = "A" * (explore.MAX_SENTENCE + 1)
    texts = {
        ("alpha", "es"): text("Una frase.", "Alpha era enorme."),
        ("alpha", "en"): text(long, "Alpha was huge."),
        ("beta", "es"): text("Solo en español."),  # no English: left out
        ("gamma", "es"): text("x"), ("gamma", "en"): text("x"),  # silhouette: left out
        ("delta", "es"): text("x"), ("delta", "en"): text("x"),  # no author: left out
        ("epsilon", "es"): text(long), ("epsilon", "en"): text("Fine."),  # too long in ES
    }  # fmt: skip
    slides = explore.pick_curiosities(taxa, texts, dt.date(2026, 11, 4))
    assert [s["taxon"]["taxon_name"] for s in slides] == ["Alpha"]
    # The sentence that names the genus wins; too long ones never show.
    assert slides[0]["text"] == {"es": "Alpha era enorme.", "en": "Alpha was huge."}


def test_the_curiosity_of_the_day_changes_with_the_date_and_wraps_around():
    taxa = [photo_genus(n) for n in ("Alpha", "Beta", "Gamma")]
    texts = {(t["taxon_key"], lang): text("x") for t in taxa for lang in ("es", "en")}
    day = dt.date(2026, 11, 4)
    first = [s["taxon"]["taxon_name"] for s in explore.pick_curiosities(taxa, texts, day)]
    again = [s["taxon"]["taxon_name"] for s in explore.pick_curiosities(taxa, texts, day)]
    nxt = [
        s["taxon"]["taxon_name"]
        for s in explore.pick_curiosities(taxa, texts, day + dt.timedelta(1))
    ]
    assert first == again and len(first) == 3  # deterministic, never more than the pool
    assert nxt[0] != first[0] and nxt == first[1:] + first[:1]


# ----------------------------------------------------------------- explorer data


def test_explore_json_is_compact_and_complete():
    taxa = [genus("Allosaurus", oldest=155, youngest=145.5, codes=["US"], image_url=COMMONS),
            new_species("Hintighernia x", "Early Cretaceous", ["United Kingdom"])]  # fmt: skip
    entries = explore.explore_entries(
        taxa,
        groups=["non_avian_dinosaurs", "pterosaurs"],
        curiosities={"allosaurus"},
        ranks={"hintighernia-x": 0},
    )
    data = explore.build_explore(
        entries,
        "es",
        lambda key: f"/es/taxones/{key}.html",
        groups=["non_avian_dinosaurs", "pterosaurs"],
        centroids={"us": (40.0, -100.0)},
    )
    assert data["url"] == ["/es/taxones/", ".html"]
    assert [p[0] for p in data["periods"]][6:8] == ["jurassic", "cretaceous"]
    assert data["countries"] == [["us", "Estados Unidos", 40.0, -100.0]]  # no centroid: off the map
    allo, hint = data["taxa"]
    assert allo[0] == "Allosaurus" and allo[4] == 0 and allo[5] == 1 << 6 and allo[6] == [0]
    assert allo[3] == explore.CURIOSITIES | explore.PHOTO and allo[7] is None
    assert data["terms"][allo[2]].startswith("3|") and "330px-" in data["terms"][allo[2]]
    assert hint[3] == explore.NEW and hint[5] == 1 << 7 and hint[6] == [] and hint[7] == 0
    assert len(hint) == 8  # the page key follows from the name: not stored


def test_numbers_are_written_as_each_language_does():
    from paleo.site.build import fmt_count

    assert fmt_count(4890, "es") == "4890" and fmt_count(10252, "es") == "10\u202f252"
    assert fmt_count(4890, "en") == "4,890"


# ------------------------------------------------------------------- home page


def home_builder():
    from paleo.site.build import SiteBuilder
    from paleo.site.data import SiteData

    allo = photo_genus("Allosaurus", image_license_url="https://creativecommons.org/x")
    allo.update(first_appearance_max_ma=155, last_appearance_min_ma=145.5, country_codes=["US"])
    hint = new_species("Hintighernia x", "Early Cretaceous", ["United States"])
    texts = {("allosaurus", "es"): text("Allosaurus tenía crestas."),
             ("allosaurus", "en"): text("Allosaurus had crests.")}  # fmt: skip
    event = {"taxon_key": "hintighernia-x", "event_type": "description", "origin": "tracked",
             "date_precision": "day", "event_date": dt.date(2026, 10, 30), "doi": "10.1/x",
             "title": "A new pterosaur", "title_es": "Un pterosaurio nuevo",
             "journal": "J"}  # fmt: skip
    data = SiteData([allo, hint], {"hintighernia-x": [event]}, texts, {}, {}, dt.date(2026, 11, 4),
                    country_centroids={"us": (40.0, -100.0)})  # fmt: skip
    return SiteBuilder(data)


def test_the_home_page_has_the_same_structure_in_both_languages():
    from paleo.site.build import Page

    b = home_builder()
    home = b.home_context(b.data.all_events())
    pages = {
        lang: b.render(Page(lang, "home", None, "index.html.j2", {"latest_week": None, **home}))
        for lang in ("es", "en")
    }

    def shape(html):
        return {k: len(re.findall(k, html)) for k in
                ('class="feature__slide', 'class="news__item"', 'class="gtile',
                 'class="ribbon__seg', "data-code=", "data-region=", 'class="card"')}  # fmt: skip

    assert shape(pages["es"]) == shape(pages["en"])
    es = pages["es"]
    assert shape(es)['class="feature__slide'] == 1 and shape(es)['class="card"'] == 1
    assert 'href="https://doi.org/10.1/x"' in es and "Un pterosaurio nuevo" in es
    assert "Imagen: Someone" in es and 'href="https://creativecommons.org/x"' in es
    # The slide's sentence in its language, the name in italics but not a link (the
    # whole slide is one).
    assert "<em>Allosaurus</em> tenía crestas." in es and "taxon-link" not in es
    # Without JavaScript the periods and groups are links to existing index pages.
    assert 'href="/es/enciclopedia/epoca/jurassic.html"' in es
    assert 'href="/es/enciclopedia/grupo/non_avian_dinosaurs.html"' in es
    assert 'href="/es/enciclopedia/epoca/ordovician.html"' not in es  # no genus there: no page
