import datetime as dt
import tomllib
from pathlib import Path

from paleo.site import terms
from paleo.site.build import fmt_date, iso_week, md_inline, week_label
from paleo.site.check import check_site
from paleo.site.fallback import fallback_text

I18N = Path(__file__).resolve().parents[1] / "src" / "paleo" / "site" / "i18n"


def test_both_languages_have_the_same_interface_strings():
    es = tomllib.loads((I18N / "es.toml").read_text("utf-8"))
    en = tomllib.loads((I18N / "en.toml").read_text("utf-8"))
    assert set(es) == set(en)


def test_ages_follow_spanish_conventions():
    assert terms.age("Late Cretaceous (Campanian)", "es") == "Cretácico Superior (Campaniense)"
    assert terms.age("Middle-Late Jurassic", "es") == "Jurásico Medio-Superior"
    assert (
        terms.age("Late Triassic (Norian or Rhaetian)", "es")
        == "Triásico Superior (Noriense o Rhaetiense)"
    )
    assert terms.age("Late Cretaceous", "en") == "Late Cretaceous"


def test_places_and_localities():
    assert terms.place("United States", "es") == "Estados Unidos"
    assert terms.place("Argentina", "es") == "Argentina"
    assert terms.locality("Dinosaur Park Formation", "es") == "Formación Dinosaur Park"
    assert terms.locality("Hammerschmiede clay pit", "es") == "Hammerschmiede clay pit"


def test_unknown_terms_are_reported_not_invented():
    terms.UNTRANSLATED.clear()
    assert terms.place("Atlantis", "es") == "Atlantis"
    assert "Atlantis" in terms.UNTRANSLATED


def taxon(**overrides):
    base = {
        "page_type": "new", "novelty": "new_genus_and_species", "taxon_group": "pterosaurs",
        "age_text": "Early Cretaceous (Valanginian)",
        "type_locality": "Tunbridge Wells Sand Formation",
        "countries": ["United Kingdom"], "regions": [], "name_authors": "Thomas & McDavid",
        "naming_year": 2026,
    }  # fmt: skip
    return base | overrides


def test_fallback_text_in_both_languages():
    assert fallback_text(taxon(), "es") == (
        "Nuevo género y especie de pterosaurio del Cretácico Inferior (Valanginiense) "
        "de la Formación Tunbridge Wells Sand, en Reino Unido, "
        "descrito por Thomas & McDavid en 2026."
    )
    assert fallback_text(taxon(), "en") == (
        "New genus and species of pterosaur from the Early Cretaceous (Valanginian) "
        "of the Tunbridge Wells Sand Formation, United Kingdom, "
        "described by Thomas & McDavid in 2026."
    )


def test_fallback_text_agrees_in_gender_and_skips_missing_fields():
    text = fallback_text(taxon(novelty="new_species", type_locality=None, naming_year=None), "es")
    assert text == (
        "Nueva especie de pterosaurio del Cretácico Inferior (Valanginiense), "
        "en Reino Unido, descrita por Thomas & McDavid."
    )
    assert fallback_text(taxon(page_type="known"), "es") is None


def test_italics_are_rendered_and_html_is_escaped():
    assert str(md_inline("*Spinosaurus* <b>x</b>")) == "<em>Spinosaurus</em> &lt;b&gt;x&lt;/b&gt;"


def test_dates_show_only_the_known_precision():
    day = dt.date(2026, 2, 19)
    assert fmt_date(day, "es") == "19 feb 2026"
    assert fmt_date(day, "es", "month") == "feb 2026"
    assert fmt_date(day, "en", "year") == "2026"
    assert iso_week(day) == "2026-W08"
    assert week_label("2026-W08", "es") == "Semana 8 · 16 feb 2026 \u2013 22 feb 2026"


def page(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<!doctype html><html><head>{body}</head><body></body></html>")


def test_checker_finds_broken_links_and_missing_alternates(tmp_path):
    page(
        tmp_path / "es" / "index.html",
        '<link rel="alternate" href="/en/index.html"><a href="/es/x.html">x</a>',
    )
    page(tmp_path / "en" / "index.html", '<a href="/en/index.html">ok</a>')
    report = check_site(tmp_path)
    assert not report.passed
    assert any("broken link /es/x.html" in p for p in report.problems)
    assert any("en/index.html: no hreflang" in p for p in report.problems)


def test_checker_respects_the_base_path(tmp_path):
    page(tmp_path / "es" / "index.html", '<link rel="alternate" href="/paleo-atlas/es/index.html">')
    assert check_site(tmp_path, base="/paleo-atlas").passed
    assert not check_site(tmp_path, base="").passed


def builder():
    import datetime as dt

    from paleo.site.build import SiteBuilder
    from paleo.site.data import SiteData

    names = ["Tyrannosaurus rex", "Spinosaurus mirabilis"]
    taxa = [{"taxon_name": n, "taxon_key": n.lower().replace(" ", "-")} for n in names]
    return SiteBuilder(SiteData(taxa, {}, {}, {}, {}, dt.date(2026, 11, 1)), base="/pa")


def test_scientific_names_are_italic_and_linked():
    b = builder()
    out = str(b.prose(
        "Unlike Tyrannosaurus rex and Carcharodontosaurus, Spinosaurus mirabilis lived in "
        "Patagonia & Niger; Spinosaurus was described by Sereno.", "en", "Spinosaurus mirabilis",
    ))  # fmt: skip
    assert (
        '<a class="taxon-link" href="/pa/en/taxa/tyrannosaurus-rex.html"><em>Tyrannosaurus rex'
        in out
    )
    assert "search=Carcharodontosaurus&amp;go=Go" not in out  # href is not double-escaped
    assert "Special:Search?search=Carcharodontosaurus&go=Go" in out
    assert "<em>Spinosaurus mirabilis</em> lived" in out  # its own page: no link
    assert "<em>Spinosaurus</em></a> was" in out  # "was" is not an epithet
    assert "Patagonia &amp; Niger" in out and "Sereno." in out


def test_species_epithets_need_a_latin_ending():
    out = str(
        builder().prose("Spinosaurus aegyptiacus y Baryonyx vivieron en el Cretácico.", "es", None)
    )
    assert "search=Spinosaurus%20aegyptiacus" in out
    assert "<em>Baryonyx</em></a> vivieron" in out


def test_spanish_and_english_forms_of_scientific_names():
    assert terms.clade_aliases("Abelisauridae") == ["abelisauridos", "abelisaurids"]
    assert terms.clade_aliases("Spinosauridae")[0] == "espinosauridos"
    assert terms.genus_aliases("Spinosaurus") == ["espinosaurio", "spinosaur"]
    assert terms.genus_aliases("Tyrannosaurus")[0] == "tiranosaurio"
    assert terms.hispanize("Pachycephalo") == "paquicefalo"
    assert terms.hispanize("Archaeopteryx") == "arqueopterix"


def test_time_units_cover_stages_dated_only_in_millions_of_years():
    units = [es for _, es in terms.time_units(72.2, 66.0)]  # Maastrichtian
    assert units == ["Cretácico", "Cretácico Superior"]
    assert ("Jurassic", "Jurásico") in terms.time_units(150.0, 140.0)  # crosses a boundary
    assert terms.time_units(None, None) == []


def test_search_entry_has_both_languages_and_facets():
    from paleo.site.search import entry

    taxon = {
        "taxon_name": "Carnotaurus", "taxon_key": "carnotaurus", "page_type": "known",
        "family_name": "Abelisauridae", "taxon_group": "non_avian_dinosaurs",
        "early_interval": "Maastrichtian", "late_interval": "Maastrichtian",
        "first_appearance_max_ma": 72.2, "last_appearance_min_ma": 66.0,
        "countries": ["Argentina"],
    }  # fmt: skip
    e = entry(taxon, "es", "/es/taxones/carnotaurus.html")
    assert "abelisauridos" in e["f"]["clade"]
    assert {"Cretácico Superior", "Late Cretaceous", "Maastrichtiense"} <= set(e["f"]["time"])
    assert e["facets"] == {
        "clade": "Abelisauridae", "group": "Dinosaurios no avianos",
        "time": ["Cretácico"], "place": "Argentina",
    }  # fmt: skip
