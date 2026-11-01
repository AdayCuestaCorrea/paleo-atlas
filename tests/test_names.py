from paleo.names import mentions_other_taxon


def test_other_genera_and_other_species_are_detected():
    assert mentions_other_taxon("Baryonyx walkeri restoration.jpg", "Spinosaurus mirabilis")
    assert mentions_other_taxon("Spinosaurus aegyptiacus by Artist.png", "Spinosaurus mirabilis")
    assert not mentions_other_taxon("Spinosaurus mirabilis skull.jpg", "Spinosaurus mirabilis")
    assert not mentions_other_taxon("Spinosaurid MNBH EGA1.jpg", "Spinosaurus mirabilis")
    assert not mentions_other_taxon("Cryptarcus locality.jpg", "Cryptarcus")
    assert not mentions_other_taxon("Patagonia outcrop.jpg", "Cryptarcus")


def test_anatomy_and_plain_words_are_not_epithets():
    assert not mentions_other_taxon("Testosaurus excavation site.jpg", "Testosaurus rex")
    assert not mentions_other_taxon("Testosaurus vertebra.jpg", "Testosaurus rex")
    assert mentions_other_taxon("Testosaurus elegans.png", "Testosaurus rex")
