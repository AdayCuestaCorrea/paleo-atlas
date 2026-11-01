from paleo.parse.wikipedia import parse_page


def test_research_bullets_are_parsed(archosaur_page):
    assert len(archosaur_page.research) == 29
    topics = {r.section_path[-1] for r in archosaur_page.research}
    assert {"Theropod research", "Avian research", "Pterosaur research"} <= topics
    assert all(r.section_path[-1] != "References" for r in archosaur_page.research)


def test_research_item_keeps_italic_links_as_candidate_taxa(archosaur_page):
    item = next(r for r in archosaur_page.research if "Saurosuchus" in r.italic_links)
    assert item.section_path == ["Pseudosuchians", "General pseudosuchian research"]
    assert {"Sillosuchus", "Aetobarbakinoides"} <= set(item.italic_links)
    assert set(item.italic_links) <= set(item.links)
    assert item.references[0].doi == "10.1111/pala.70056"


def test_plain_text_has_no_markup(archosaur_page):
    for item in archosaur_page.research:
        assert "[[" not in item.text
        assert "<ref" not in item.text
        assert "{{" not in item.text


def test_bullet_without_doi_is_kept_with_a_warning(archosaur_page):
    no_doi = [r for r in archosaur_page.research if "no DOI" in r.parse_warnings]
    assert len(no_doi) == 2
    assert all(r.references for r in no_doi)


def test_research_ids_are_unique_and_stable(archosaur_page, archosaur_text):
    ids = [r.research_id for r in archosaur_page.research]
    assert len(ids) == len(set(ids))
    again = parse_page("2026 in archosaur paleontology", 1383165113, archosaur_text)
    assert ids == [r.research_id for r in again.research]


def test_same_study_under_two_headings_is_merged():
    wikitext = """== Group ==
=== Theropod research ===
* Study A.<ref>{{Cite journal |title=A |doi=10.1/abc |year=2026}}</ref> [[Tyrannosaurus]]
=== General research ===
* Study A again.<ref>{{Cite journal |title=A |doi=10.1/ABC |year=2026}}</ref> [[Allosaurus]]
"""
    page = parse_page("2026 in archosaur paleontology", 1, wikitext)
    (item,) = page.research
    assert item.links == ["Tyrannosaurus", "Allosaurus"]
    assert any("also listed under" in w for w in item.parse_warnings)
