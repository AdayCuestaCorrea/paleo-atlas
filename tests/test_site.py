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
        '<a class="taxon-link" href="/pa/en/taxa/tyrannosaurus-rex.html" '
        'title="Open the Tyrannosaurus rex page"><em>Tyrannosaurus rex' in out
    )
    assert 'title="Search Wikipedia for Carcharodontosaurus"' in out  # says where it goes
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


def test_known_taxa_get_a_fallback_sentence_from_pbdb():
    known = {
        "page_type": "known", "taxon_rank": "species", "taxon_group": "non_avian_dinosaurs",
        "family_name": "Tyrannosauridae", "early_interval": "Late Campanian",
        "late_interval": "Late Maastrichtian", "first_appearance_max_ma": 83.6,
        "last_appearance_min_ma": 66.0,
    }  # fmt: skip
    es = fallback_text(known, "es")
    assert es.startswith("Especie de dinosaurio no aviano de la familia Tyrannosauridae")
    assert "(hace 83,6 a 66 millones de años)." in es
    en = fallback_text(known, "en")
    assert en.startswith("Species of non-avian dinosaur in the family Tyrannosauridae")
    assert fallback_text({**known, "taxon_rank": "family"}, "es") is None


def test_pages_without_text_still_list_their_sources():
    from paleo.site.fallback import basic_sources

    sources = basic_sources(
        {"taxon_name": "Allosaurus", "pbdb_has_taxon": True, "pbdb_taxon_no": "txn:52962"},
        [{"doi": "10.1/x", "title": "A study"}, {"doi": "10.1/x", "title": "A study"}],
        "2026 in archosaur paleontology",
    )
    assert [s["url"] for s in sources] == [
        "https://en.wikipedia.org/wiki/2026_in_archosaur_paleontology",
        "https://paleobiodb.org/classic/basicTaxonInfo?taxon_no=52962",
        "https://doi.org/10.1/x",
    ]


def test_encyclopedia_genera_cite_the_yearly_page_only_when_studied():
    from paleo.site.fallback import basic_sources

    genus = {"page_type": "genus", "taxon_name": "Brontosaurus", "pbdb_has_taxon": True,
             "pbdb_taxon_no": "txn:52986", "taxon_rank": "genus",
             "taxon_group": "non_avian_dinosaurs"}  # fmt: skip
    urls = [s["url"] for s in basic_sources(genus, [], "2026 in archosaur paleontology")]
    assert urls == ["https://paleobiodb.org/classic/basicTaxonInfo?taxon_no=52986"]
    studied = basic_sources(genus, [{"doi": "10.1/y"}], "2026 in archosaur paleontology")
    assert studied[0]["url"].endswith("2026_in_archosaur_paleontology")
    assert fallback_text(genus, "es").startswith("Género de dinosaurio no aviano")


def test_substages_and_cenozoic_periods_in_spanish():
    from paleo.site import terms

    assert terms.interval("Late Campanian", "es") == "Campaniense superior"
    assert terms.interval("early Albian", "es") == "Albiense inferior"
    assert terms.interval("Paleogene", "es") == "Paleógeno"
    assert terms.country_name("uk", "es") == "Reino Unido"
    assert terms.country_name("O2", "en") == "North Atlantic"


def test_indices_list_each_genus_by_group_family_epoch_and_country():
    from paleo.site.indices import build_indices

    def genus(name, group, family, oldest, youngest, countries):
        return {"taxon_key": name.lower(), "taxon_name": name, "page_type": "genus",
                "taxon_rank": "genus", "taxon_group": group, "family_name": family,
                "first_appearance_max_ma": oldest, "last_appearance_min_ma": youngest,
                "country_codes": countries}  # fmt: skip

    taxa = [
        genus("Tyrannosaurus", "non_avian_dinosaurs", "Tyrannosauridae", 68, 66, ["US", "CA"]),
        genus("Allosaurus", "non_avian_dinosaurs", None, 155, 145.5, ["US", "PT"]),
        genus("Archaeopteryx", "birds", None, 151, 149, ["DE"]),
        {"taxon_key": "t-rex", "taxon_name": "T rex", "page_type": "known",
         "taxon_rank": "species", "taxon_group": "non_avian_dinosaurs"},  # not a genus
    ]  # fmt: skip
    idx = build_indices(taxa, ["birds", "non_avian_dinosaurs"])
    assert list(idx.groups) == ["birds", "non_avian_dinosaurs"]
    # families alphabetically, no family last
    assert list(idx.groups["non_avian_dinosaurs"]) == ["Tyrannosauridae", ""]
    assert idx.genera == 3 and idx.group_count("non_avian_dinosaurs") == 2
    assert [e for e, _ in idx.periods["jurassic"]] == ["late-jurassic"]
    assert idx.period_count("cretaceous") == 1
    assert [t["taxon_name"] for t in idx.countries["us"]] == ["Allosaurus", "Tyrannosaurus"]
    assert next(iter(idx.countries)) == "us"  # most genera first


def test_the_check_finds_taxon_pages_nobody_links_to(tmp_path):
    from paleo.site.check import check_site

    for lang, folder in (("es", "taxones"), ("en", "taxa")):
        page = tmp_path / lang / folder / "lonely.html"
        page.parent.mkdir(parents=True)
        other = "en/taxa" if lang == "es" else "es/taxones"
        page.write_text(f'<html><head><link rel="alternate" href="/{other}/lonely.html">'
                        f'</head><body><a hreflang="x" href="/{other}/lonely.html">x</a>'
                        "</body></html>")  # fmt: skip
    problems = check_site(tmp_path).problems
    assert "es/taxones/lonely.html: no page links to it" in problems
    assert "en/taxa/lonely.html: no page links to it" in problems
    assert check_site(tmp_path / "missing").problems[-1].endswith("(was the site built?)")


def test_the_fossil_record_falls_back_to_the_epochs_of_its_ages():
    from paleo.site import terms

    with_names = {"early_interval": "Late Campanian", "late_interval": "Maastrichtian"}
    assert terms.span(with_names, "es") == ("Campaniense superior", "Maastrichtiense")
    only_ages = {"first_appearance_max_ma": 168.2, "last_appearance_min_ma": 157.9}
    assert terms.span(only_ages, "es") == ("Jurásico Medio", "Jurásico Superior")
    assert terms.span(only_ages, "en") == ("Middle Jurassic", "Late Jurassic")
    assert terms.span({}, "es") == (None, None)
    fish = {"page_type": "genus", "taxon_rank": "genus", "taxon_group": "other_fishes",
            "family_name": "Pachycormidae", **only_ages}  # fmt: skip
    assert fallback_text(fish, "es") == (
        "Género de pez de la familia Pachycormidae, que vivió del Jurásico Medio al Jurásico "
        "Superior (hace 168,2 a 157,9 millones de años)."
    )  # fmt: skip


def test_no_double_dot_after_et_al():
    text = fallback_text(taxon(name_authors="Zietlow et al.", naming_year=None), "es")
    assert text.endswith("Zietlow et al.") and not text.endswith("..")


def test_long_lists_show_the_first_items_and_fold_the_rest():
    b = builder()
    folded = b.env.get_template("macros.html.j2").module.folded
    from markupsafe import Markup

    items = [Markup(f"<a href='#{i}'>C{i}</a>") for i in range(20)]  # as the page builds them
    out = str(folded(items, "and 8 more"))
    head, _, rest = out.partition("<details")
    assert head.count("<a ") == 12 and rest.count("<a ") == 8 and "and 8 more" in rest
    assert "<details" not in str(folded(items[:12], "unused"))  # 12 or fewer: no fold


def test_a_moved_page_redirects_and_is_not_an_orphan_or_a_taxon(tmp_path):
    alt = '<link rel="alternate" href="/es/index.html">'
    page(tmp_path / "es" / "index.html", alt + '<a href="/es/taxones/tyrannosaurus.html">T</a>')
    page(tmp_path / "es" / "taxones" / "tyrannosaurus.html", alt)
    # T. rex, folded into its genus: only a redirect is left at its old URL.
    page(
        tmp_path / "es" / "taxones" / "tyrannosaurus-rex.html",
        alt + '<meta http-equiv="refresh" content="0; url=/es/taxones/tyrannosaurus.html">'
        '<a href="/es/taxones/tyrannosaurus.html">T</a>',
    )
    (tmp_path / "es" / "buscar.json").write_text('{"taxa": [["Tyrannosaurus"]]}')
    report = check_site(tmp_path)
    assert report.passed, report.problems  # not an orphan, not counted as a taxon page
