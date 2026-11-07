"""Taxon page (§11.1): its computed pieces and the rendered page in both languages."""

import datetime as dt
import re
from collections import defaultdict

from paleo.site import taxon_page as tp
from paleo.site.check import check_site

DAY = dt.date(2026, 11, 7)
COMMONS = (
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/9/94/T_rex.jpg/960px-T_rex.jpg"
    "?utm_source=commons.wikimedia.org"
)


def test_srcset_offers_three_sizes_of_commons_pictures_only():
    s = tp.srcset(COMMONS)
    assert s.count("px-T_rex.jpg") == 3 and "utm_source" not in s
    assert s.endswith("/1920px-T_rex.jpg 1920w") and "/960px-T_rex.jpg 960w" in s
    assert tp.srcset("https://images.phylopic.org/images/x/raster/1536x306.png") is None
    assert tp.srcset(None) is None


def test_time_strip_marks_the_range_and_its_periods():
    ax = tp.time_axis(83.6, 66.0, ["cretaceous"])
    assert [b["key"] for b in ax["bands"] if b["active"]] == ["cretaceous"]
    cret = next(b for b in ax["bands"] if b["key"] == "cretaceous")
    assert (
        cret["x"] <= ax["mark"]["x"]
        and ax["mark"]["x"] + ax["mark"]["width"] <= cret["x"] + cret["width"] + 0.2
    )
    short = tp.time_axis(10.0, 9.9, ["neogene"])["mark"]  # a short range stays visible
    assert short["width"] == 6.0
    assert tp.time_axis(None, None, [])["mark"] is None


def test_new_means_tracked_and_at_most_90_days_old():
    def ev(days, origin="tracked"):
        return {"event_date": DAY - dt.timedelta(days=days), "origin": origin}

    assert tp.is_new(ev(0), DAY) and tp.is_new(ev(90), DAY)
    assert not tp.is_new(ev(91), DAY)
    assert not tp.is_new(ev(5, origin="backfill"), DAY)  # the history backwards never is
    assert not tp.is_new({"event_date": None}, DAY)


def test_history_bars_by_decade_then_the_tracked_year():
    history = {"recent": [{}, {}, {}], "decades": [(2010, [{}] * 6), (1990, [{}])]}
    bars = tp.history_by_decade(history, DAY)
    assert [(b["label"], b["n"], b["now"]) for b in bars] == [
        ("1990s", 1, False), ("2010s", 6, False), ("2026", 3, True)
    ]  # fmt: skip
    assert bars[1]["height"] == 100 and 6 <= bars[0]["height"] < 100


def test_the_language_tag_says_only_what_we_know():
    en = {"title": "A study", "language": "en"}
    assert tp.study_lang_tag(en, "es") == "lang:en" and tp.study_lang_tag(en, "en") is None
    assert tp.study_lang_tag({"title": "Ein Werk", "language": "DE"}, "en") == "lang:de"
    assert tp.study_lang_tag({"title": "Un estudio", "language": "es"}, "es") is None
    # Unknown language: on Spanish pages, whether the title shown is ours or as published.
    assert tp.study_lang_tag({"title": "A", "title_es": "Un"}, "es") == "translated"
    assert tp.study_lang_tag({"title": "A"}, "es") == "original"
    assert tp.study_lang_tag({"title": "A"}, "en") is None
    assert tp.study_lang_tag({"title": None}, "es") is None


def test_map_frames_the_finds_at_two_to_one():
    x, y, w, h = map(
        float, tp.map_viewbox([{"lon": -105, "lat": 45}, {"lon": -100, "lat": 50}]).split()
    )
    assert w == 2 * h and x <= -105 and x + w >= -100 and y <= -50 and y + h >= -45
    assert tp.map_viewbox([]) == "-180 -90 360 180"
    world = [{"lon": -170, "lat": 60}, {"lon": 170, "lat": -50}]
    assert tp.map_viewbox(world) == "-180 -90 360 180"


# ---------------------------------------------------------------- rendered page


def taxon(**fields):
    base = {"taxon_key": "tyrannosaurus", "taxon_name": "Tyrannosaurus", "page_type": "genus",
            "taxon_rank": "genus", "taxon_group": "non_avian_dinosaurs",
            "taxonomic_block": "archosaurs", "family_name": "Tyrannosauridae",
            "order_name": "Saurischia", "class_name": "Reptilia",
            "first_appearance_max_ma": 83.6, "last_appearance_min_ma": 66.0,
            "country_codes": ["US", "CA"], "occurrence_count": 85,
            "image_url": COMMONS, "image_source": "commons", "image_author": "Someone",
            "image_license": "CC BY-SA 3.0", "image_license_url": "https://creativecommons.org/x",
            "image_page_url": "https://commons.wikimedia.org/wiki/File:T_rex.jpg",
            "pbdb_points": [{"lon": -105, "lat": 45, "n": 3}]}  # fmt: skip
    t = defaultdict(lambda: None)
    t.update(base | fields)
    return t


YEAR_PAGE = "2026 in archosaur paleontology"


def render_taxon(lang, t, events=()):
    from paleo.site.build import Page, SiteBuilder
    from paleo.site.data import SiteData, history
    from paleo.site.fallback import basic_sources, fallback_text

    events = list(events)
    rows = [{"level_clade_name": "Tyrannosaurini", "level_genera": 2, "member_key": "tyrannosaurus",
             "member_name": "Tyrannosaurus", "is_self": True, "first_appearance_max_ma": 83.6,
             "last_appearance_min_ma": 66.0},
            {"level_clade_name": "Tyrannosaurini", "level_genera": 2, "member_key": "tarbosaurus",
             "member_name": "Tarbosaurus", "is_self": False, "first_appearance_max_ma": 89.8,
             "last_appearance_min_ma": 66.0}]  # fmt: skip
    data = SiteData([t], {t["taxon_key"]: events}, {}, {}, {}, DAY,
                    neighborhood={t["taxon_key"]: {"group": rows}})  # fmt: skip
    b = SiteBuilder(data)
    ctx = {"taxon": t, "events": events, "history": history(events), "kin": data.kinship(t),
           "silhouettes": {}, "gallery": [], "text": None, "fallback": fallback_text(t, lang),
           "basic_sources": basic_sources(t, events, YEAR_PAGE, lang)}  # fmt: skip
    return b.render(Page(lang, "taxon", t["taxon_key"], "taxon.html.j2", ctx))


EVENT = defaultdict(lambda: None, {
         "taxon_key": "tyrannosaurus", "event_type": "new_study", "origin": "tracked",
         "date_precision": "day", "event_date": DAY - dt.timedelta(days=30), "doi": "10.1/x",
         "title": "The body temperature of Tyrannosaurus rex", "language": "en",
         "title_es": "La temperatura corporal de Tyrannosaurus rex", "journal": "Science Advances",
         "attribution": "Someone et al."})  # fmt: skip


def test_the_taxon_page_has_the_same_structure_in_both_languages():
    pages = {lang: render_taxon(lang, taxon(), [EVENT]) for lang in ("es", "en")}

    def shape(html):
        keys = ('class="tx-sec"', 'class="tx-glance"', "<div><small>", 'class="kt__row',
                'class="tx-toc"', "data-viewer", 'class="tag-new"', 'target="_blank"')  # fmt: skip
        return {k: len(re.findall(k, html)) for k in keys}

    assert shape(pages["es"]) == shape(pages["en"])
    es = pages["es"]
    # The study opens in a new tab, says it is in English and shows our translation.
    assert re.search(r'<a href="https://doi.org/10.1/x" rel="noopener" target="_blank">', es)
    assert ">en inglés</span>" in es and "La temperatura corporal" in es
    assert "Artículo en inglés" not in es
    assert 'class="tag-new"' in es  # 30 days old
    # Header: the whole picture in three sizes, its credit with the license, the viewer.
    assert 'srcset="' in es and "1920px-T_rex.jpg 1920w" in es
    assert "Someone" in es and 'href="https://creativecommons.org/x"' in es
    assert (
        'data-full="https://thumb.wikimedia.org/wikipedia/commons/thumb/9/94/T_rex.jpg/1920px-T_rex.jpg"'
        in es
    )
    # Relatives with their range written out, the page itself marked.
    dash = "\u2013"
    assert f"89,8{dash}66 Ma" in es and f"83,6{dash}66 Ma · este animal" in es
    assert f"89.8{dash}66 Ma" in pages["en"]


def test_a_page_without_text_or_picture_still_has_its_summary_and_no_tags():
    t = taxon(image_url=None, image_source=None, image_page_url=None, occurrence_count=None)
    es = render_taxon("es", t, [])
    assert 'class="tx-glance"' in es and "Cuándo vivió" in es and "Fósiles registrados" not in es
    assert "data-viewer" not in es and 'class="tag-new"' not in es


def test_the_check_wants_a_license_for_every_figure(tmp_path):
    def page(path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'<!doctype html><html><head><link rel="alternate" href="/es/index.html">'
                        f"</head><body>{body}</body></html>")  # fmt: skip

    page(
        tmp_path / "es" / "index.html",
        '<figure><img src="https://example.org/a.jpg"><figcaption>Foto: X</figcaption></figure>',
    )
    assert any(
        "license" in p.lower() or "licen" in p.lower() for p in check_site(tmp_path).problems
    )
    page(
        tmp_path / "es" / "index.html",
        '<figure><img src="https://example.org/a.jpg">'
        "<figcaption>Foto: X · CC BY 4.0</figcaption></figure>",
    )
    assert check_site(tmp_path).passed
