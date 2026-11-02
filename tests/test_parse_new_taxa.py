from paleo.parse.wikipedia import NewTaxonRow, ParsedPage


def by_name(page: ParsedPage, name: str) -> NewTaxonRow:
    return next(r for r in page.new_taxa if r.name == name)


def test_every_kept_row_is_parsed(archosaur_page):
    assert len(archosaur_page.new_taxa) == 12
    assert all(r.revid == 1383165113 for r in archosaur_page.new_taxa)


def test_standard_row_fields(archosaur_page):
    row = by_name(archosaur_page, "Antusuchus")
    assert row.name_link == "Antusuchus"
    assert row.novelty == "Gen. et sp. nov"
    assert row.status == "Valid"
    assert row.authors == "Fernandez-Dumont et al."
    assert row.age == "Early Cretaceous (Albian)"
    assert row.age_links == ["Early Cretaceous", "Albian"]
    assert row.type_locality == "Candeleros Formation"
    assert row.countries == ["Argentina"]
    assert row.regions == []
    assert "Peirosauridae" in row.note_links
    assert row.section_path == ["Pseudosuchians", "New pseudosuchian taxa"]
    assert row.parse_warnings == []


def test_reference_is_extracted_from_cite_template(archosaur_page):
    (ref,) = by_name(archosaur_page, "Antusuchus").references
    assert ref.doi == "10.1080/08912963.2026.2683112"
    assert ref.template == "cite journal"
    assert ref.year == 2026
    assert ref.venue.startswith("Historical Biology")
    assert ref.authors[0] == "Fernández-Dumont"


def test_binomial_name_and_image(archosaur_page):
    assert by_name(archosaur_page, "Crocodylus lucivenator").novelty == "Sp. nov"
    assert by_name(archosaur_page, "Carinthiasuchus").images == ["Carinthiasuchus skeletal.png"]


def test_cells_on_the_same_line_as_the_pipe(archosaur_page):
    row = by_name(archosaur_page, "Eosphorosuchus")
    assert row.novelty == "Gen. et sp. nov"
    assert row.authors == "Margulis-Ohnuma et al."
    assert row.type_locality == "Chinle Formation"


def test_subdivisions_in_parentheses_are_regions(archosaur_page):
    assert by_name(archosaur_page, "Eosphorosuchus").regions == ["New Mexico"]
    row = by_name(archosaur_page, "Gilmoretyrannus")
    assert row.countries == ["United States"]
    assert row.regions == ["Montana", "Wyoming"]


def test_several_countries_without_regions(archosaur_page):
    row = by_name(archosaur_page, "Eopinacosaurus")
    assert row.countries == ["China", "Mongolia"]
    assert row.regions == []


def test_reused_named_reference_resolves_to_its_content(archosaur_page):
    first = by_name(archosaur_page, "Gilmoretyrannus").references[0]
    reused = by_name(archosaur_page, "Larsonvenator").references[0]
    assert first.ref_name == reused.ref_name == "S&P2026"
    assert reused.doi is not None
    assert reused.doi == first.doi


def test_missing_status_and_plain_text_country(archosaur_page):
    row = by_name(archosaur_page, "Asio pythiotus")
    assert row.status is None
    assert row.countries == ["Crimea"]


def test_triple_brace_inside_a_citation_title_does_not_break_the_table(archosaur_page):
    row = by_name(archosaur_page, "Xenicus longipes perditus")
    assert row.novelty == "Ssp. nov"
    assert row.countries == ["New Zealand"]
    assert row.references[0].doi == "10.1016/j.ympev.2026.108741"


def test_new_spinosaurus_species_is_found(archosaur_page):
    row = by_name(archosaur_page, "Spinosaurus mirabilis")
    assert row.section_path == ["Non-avian dinosaurs", "New dinosaur taxa"]
    assert row.references[0].venue == "Science"


def test_fish_page_location_column_is_the_country(fish_page):
    """Some paleoichthyology tables have "Type locality" and "Location": the latter
    is the country, not a second type locality."""
    rows = {r.name: r for r in fish_page.new_taxa}
    assert len(fish_page.new_taxa) == 135
    assert rows["Asioaspis"].countries == ["China"]
    assert rows["Asioaspis"].type_locality == "Xishancun Formation"
    assert not [w for r in fish_page.new_taxa for w in r.parse_warnings if "column" in w]


def test_reptile_page_rows_keep_their_nested_sections(reptile_page):
    sections = {tuple(r.section_path) for r in reptile_page.new_taxa}
    assert ("Lepidosauromorphs", "Squamates") in sections
    assert ("Ichthyosauromorphs",) in sections
    assert len(reptile_page.new_taxa) == 42
