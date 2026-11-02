"""Which rows of the yearly pages are in the taxonomic scope (paleo.scope, §4)."""

import json

from paleo import scope
from paleo.interim import latest_rows

REPTILES = "2026 in reptile paleontology"
FISHES = "2026 in paleoichthyology"
ARCHOSAURS = "2026 in archosaur paleontology"


def test_blocks_come_from_the_page_title():
    assert scope.block_of(ARCHOSAURS) == "archosaurs"
    assert scope.block_of(REPTILES) == "marine_reptiles"
    assert scope.block_of(FISHES) == "fossil_fishes"


def test_archosaur_page_keeps_every_section():
    assert scope.new_taxon_group(ARCHOSAURS, ["Birds"], "Janavis", "") == "birds"
    assert scope.new_taxon_group(ARCHOSAURS, ["Something else"], "X", "") == "other"


def test_only_the_mosasaurs_among_the_squamates():
    squamates = ["Lepidosauromorphs", "Squamates"]  # nested headings
    assert scope.new_taxon_group(REPTILES, squamates, "Garamaudo", "A mosasaur of the "
                                 "subfamily Tethysaurinae.") == "mosasaurs"  # fmt: skip
    assert scope.new_taxon_group(REPTILES, squamates, "Acutodon", "A lizard.") is None
    assert scope.new_taxon_group(REPTILES, ["Turtles"], "Testudo", "A turtle.") is None
    assert scope.new_taxon_group(REPTILES, ["Ichthyosauromorphs"], "X", "") == "ichthyosaurs"


def test_bony_fishes_only_when_featured():
    ray_finned = ["Ray-finned fishes", "Otolith taxa"]
    assert scope.new_taxon_group(FISHES, ray_finned, "Saurichthys major", "") == "other_fishes"
    assert scope.new_taxon_group(FISHES, ray_finned, "Clupea", "") is None
    assert scope.new_taxon_group(FISHES, ["Placoderms"], "X", "") == "placoderms"
    # a study is in when it names a featured genus
    research = ["Lobe-finned fishes", "Lobe-finned fish research"]
    assert scope.research_group(FISHES, research, "A study of Tiktaalik's fins.") == "other_fishes"
    assert scope.research_group(FISHES, research, "A study of lungfish teeth.") is None


def test_rows_outside_the_scope_are_left_out_of_every_step(tmp_path):
    folder = tmp_path / "wikipedia" / "2026_in_reptile_paleontology" / "1"
    folder.mkdir(parents=True)
    rows = [{"name": "Tylosaurus rex", "taxon_group": "mosasaurs"},
            {"name": "Testudo", "taxon_group": None},
            {"name": "Old row without the field"}]  # fmt: skip
    (folder / "new_taxa.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    names = [r["name"] for r in latest_rows(tmp_path, "new_taxa")]
    assert names == ["Tylosaurus rex", "Old row without the field"]
    assert len(list(latest_rows(tmp_path, "new_taxa", in_scope_only=False))) == 3
