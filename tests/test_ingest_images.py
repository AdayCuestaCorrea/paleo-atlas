import httpx
import pytest

from paleo.http import make_client
from paleo.ingest import images

BUILD = 560


def commons_handler(request):
    return httpx.Response(
        200,
        json={
            "query": {
                "normalized": [
                    {
                        "from": "File:Carinthiasuchus_skeletal.png",
                        "to": "File:Carinthiasuchus skeletal.png",
                    }
                ],
                "pages": [
                    {
                        "title": "File:Carinthiasuchus skeletal.png",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/a.png",
                                "thumburl": "https://upload.wikimedia.org/a-800.png",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:A.png",
                                "mime": "image/png",
                                "width": 2000,
                                "height": 900,
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY 4.0"},
                                    "LicenseUrl": {
                                        "value": "https://creativecommons.org/licenses/by/4.0"
                                    },
                                    "Artist": {"value": '<a href="//x">Jane Doe</a>'},
                                },
                            }
                        ],
                    },
                    {"title": "File:Missing.png", "missing": True},
                ],
            }
        },
    )


def test_commons_metadata_is_mapped_back_to_requested_names():
    with make_client(httpx.MockTransport(commons_handler)) as client:
        out = images.fetch_commons(client, ["Carinthiasuchus_skeletal.png", "Missing.png"])
    image = out["Carinthiasuchus_skeletal.png"]
    assert image["found"]
    assert image["license_short_name"] == "CC BY 4.0"
    assert image["thumb_url"].endswith("-800.png")
    assert "Jane Doe" in image["artist_html"]
    assert out["Missing.png"] == {"file": "Missing.png", "found": False}


def node(name, license_url="https://creativecommons.org/publicdomain/zero/1.0/"):
    return {
        "uuid": "node-1",
        "names": [
            [{"class": "scientific", "text": name}, {"class": "citation", "text": "Author 1900"}]
        ],
        "_embedded": {
            "primaryImage": {
                "uuid": "img-1",
                "attribution": "Tasman Dixon",
                "_links": {
                    "license": {"href": license_url},
                    "contributor": {"title": "Tasman Dixon"},
                    "vectorFile": {"href": "https://images.phylopic.org/img-1/vector.svg"},
                    "rasterFiles": [
                        {"href": "https://images.phylopic.org/img-1/raster/1024x512.png"}
                    ],
                },
            }
        },
    }


def image(uuid, license_url, node_title="Giganotosaurus carolinii"):
    return {
        "uuid": uuid,
        "attribution": "Someone",
        "_links": {
            "license": {"href": license_url},
            "specificNode": {"title": node_title},
            "vectorFile": {"href": f"https://images.phylopic.org/{uuid}/vector.svg"},
            "rasterFiles": [{"href": f"https://images.phylopic.org/{uuid}/raster/1024x330.png"}],
        },
    }


def phylopic_handler(known, clade_images=None, autocomplete=None):
    def handler(request):
        if request.url.path == "/autocomplete":
            matches = (autocomplete or {}).get(request.url.params["query"], [])
            return httpx.Response(200, json={"build": BUILD, "matches": matches})
        if request.url.path == "/images":
            items = (clade_images or {}).get(request.url.params["filter_clade"], [])
            return httpx.Response(200, json={"_embedded": {"items": items}})
        if request.url.path == "/" and "build" not in request.url.params:
            return httpx.Response(
                307, headers={"Location": f"https://api.phylopic.org/?build={BUILD}"}
            )
        if request.url.path == "/":
            return httpx.Response(200, json={"build": BUILD})
        assert request.headers["Accept"] == images.PHYLOPIC_ACCEPT
        name = request.url.params["filter_name"]
        if name not in known:
            return httpx.Response(404, json={"errors": []})
        return httpx.Response(200, json={"_embedded": {"items": [known[name]]}})

    return handler


def test_build_number_comes_from_the_root_redirect():
    with make_client(httpx.MockTransport(phylopic_handler({}))) as client:
        assert images.phylopic_build(client) == BUILD


def test_silhouette_with_license_and_attribution():
    known = {"spinosaurus": node("Spinosaurus")}
    with make_client(httpx.MockTransport(phylopic_handler(known))) as client:
        out = images.fetch_phylopic(client, "Spinosaurus", BUILD)
    assert out["found"]
    assert out["image"]["license_url"].endswith("/publicdomain/zero/1.0/")
    assert out["image"]["attribution"] == "Tasman Dixon"
    assert out["image"]["raster_url"].endswith(".png")


@pytest.mark.parametrize("name", ["Antusuchus", "Tyrannosauridae"])
def test_404_means_no_node(name):
    with make_client(httpx.MockTransport(phylopic_handler({}))) as client:
        assert images.fetch_phylopic(client, name, BUILD) == {
            "name": name,
            "found": False,
            "build": BUILD,
        }


def test_a_node_with_a_different_name_is_not_used():
    known = {"spinosaurus": node("Spinosauridae")}  # fuzzy match returned by the API
    with make_client(httpx.MockTransport(phylopic_handler(known))) as client:
        assert not images.fetch_phylopic(client, "Spinosaurus", BUILD)["found"]


def test_non_commercial_licenses_are_stored_but_filtered_downstream():
    # The license filter lives in dbt (tested there); ingestion must keep the URL.
    known = {
        "tyrannosaurus rex": node(
            "Tyrannosaurus rex", "https://creativecommons.org/licenses/by-nc-sa/3.0/"
        )
    }
    with make_client(httpx.MockTransport(phylopic_handler(known))) as client:
        out = images.fetch_phylopic(client, "Tyrannosaurus rex", BUILD)
    assert "by-nc-sa" in out["image"]["license_url"]


ARTICLE = """{{Speciesbox
| image = Testosaurus rex skull.jpg
| image_caption = Skull
}}
'''Testosaurus rex''' is a theropod.
[[File:Testosaurus_rex_tooth.jpg|thumb|A tooth]]
[[Archivo:Testosaurus rex life.png|thumb]]
{{clade |1={{clade |1=[[File:Baryonyx walkeri restoration.jpg|60px]] }} }}
[[File:Testosaurus elegans.png|thumb|Another species of the genus]]
<gallery>
File:Testosaurus excavation site.jpg|The quarry
Suchomimus by Artist.png|A relative
</gallery>
"""


def test_article_files_keep_the_taxon_and_drop_relatives():
    assert images.article_files(ARTICLE, "Testosaurus rex") == [
        "Testosaurus rex skull.jpg",
        "Testosaurus rex tooth.jpg",
        "Testosaurus rex life.png",
        "Testosaurus excavation site.jpg",
    ]


def test_category_files_include_subcategories_named_after_the_taxon():
    def handler(request):
        title = request.url.params["cmtitle"]
        members = {
            "Category:Testosaurus rex": [
                {"title": "File:A.jpg"},
                {"title": "Category:Testosaurus rex skulls"},
                {"title": "Category:Dinosaur toys"},  # not named after it: skipped
            ],
            "Category:Testosaurus rex skulls": [{"title": "File:B skull.png"}],
        }[title]
        return httpx.Response(200, json={"query": {"categorymembers": members}})

    with make_client(httpx.MockTransport(handler)) as client:
        assert images.fetch_category_files(client, "Testosaurus rex") == ["A.jpg", "B skull.png"]


def test_known_species_fall_back_to_the_genus_category():
    def handler(request):
        members = {
            "Category:Testosaurus rex": [],
            "Category:Testosaurus": [{"title": "File:Testosaurus skeleton.jpg"},
                                     {"title": "File:Testosaurus elegans.png"}],
        }[request.url.params["cmtitle"]]  # fmt: skip
        return httpx.Response(200, json={"query": {"categorymembers": members}})

    with make_client(httpx.MockTransport(handler)) as client:
        assert images.fetch_category_files(client, "Testosaurus rex") == []  # a new species
        assert images.fetch_category_files(client, "Testosaurus rex", genus_fallback=True) == [
            "Testosaurus skeleton.jpg"  # not the other species
        ]


def test_only_pictures_are_asked_for():
    assert images.is_picture("Skull.JPG") and images.is_picture("map.svg")
    assert not images.is_picture("10_24072_pcjournal_804.pdf")
    assert not images.is_picture("walk.webm")


def test_a_file_commons_rejects_does_not_cost_the_rest_of_its_batch():
    asked = []

    def handler(request):
        titles = request.url.params["titles"].split("|")
        asked.append(titles)
        if "File:Odd.png" in titles:  # Commons rejects any request that includes it
            return httpx.Response(200, json={"error": {"code": "urlparamnormal", "info": "x"}})
        pages = [{"title": t, "missing": True} for t in titles]
        return httpx.Response(200, json={"query": {"pages": pages}})

    with make_client(httpx.MockTransport(handler)) as client:
        out = images._fetch_commons_resilient(client, ["A.png", "Odd.png", "B.png"])
    assert set(out) == {"A.png", "B.png"}  # the odd one is skipped, the others kept
    assert asked[0] == ["File:A.png", "File:Odd.png", "File:B.png"]
    assert sorted(asked[1:]) == [["File:A.png"], ["File:B.png"], ["File:Odd.png"]]


def test_a_genus_that_is_a_second_name_of_its_species_node_is_found():
    # PhyloPic merges a monotypic genus into its species' node
    giga = node("Giganotosaurus carolinii")
    giga["names"].append([{"class": "scientific", "text": "Giganotosaurus"}])
    with make_client(httpx.MockTransport(phylopic_handler({"giganotosaurus": giga}))) as client:
        out = images.fetch_phylopic(client, "Giganotosaurus", BUILD)
    assert out["found"] and out["node_uuid"] == "node-1"


def test_other_images_of_the_node_are_kept_after_the_primary():
    nc = "https://creativecommons.org/licenses/by-nc-sa/3.0/"
    cc0 = "https://creativecommons.org/publicdomain/zero/1.0/"
    known = {"giganotosaurus carolinii": node("Giganotosaurus carolinii", nc)}
    others = {"node-1": [image("img-1", nc), image("img-2", cc0), image("img-3", cc0)]}
    with make_client(httpx.MockTransport(phylopic_handler(known, others))) as client:
        out = images.fetch_phylopic(client, "Giganotosaurus carolinii", BUILD)
    assert out["image"]["uuid"] == "img-1"  # the primary, still the page picture
    assert [i["uuid"] for i in out["images"]] == ["img-1", "img-2", "img-3"]  # no duplicate
    assert out["images"][1]["license_url"] == cc0
    assert out["images"][1]["node"] == "Giganotosaurus carolinii"


def test_a_homonym_among_the_second_names_is_not_used():
    chitons = node("Polyplacophora")
    chitons["names"].append([{"class": "scientific", "text": "Loricata"}])
    with make_client(httpx.MockTransport(phylopic_handler({"loricata": chitons}))) as client:
        assert not images.fetch_phylopic(client, "Loricata", BUILD)["found"]


def species_node(name, uuid, license_url="https://creativecommons.org/publicdomain/zero/1.0/"):
    out = node(name, license_url)
    out["uuid"] = uuid
    out["_embedded"]["primaryImage"]["uuid"] = f"img-{uuid}"
    return out


def test_a_genus_kept_only_as_its_species_node_is_found_by_autocomplete():
    # "Acrocanthosaurus atokensis" has no second name: the exact lookup of the genus
    # misses it, the autocomplete finds it.
    known = {"acrocanthosaurus atokensis": species_node("Acrocanthosaurus atokensis", "n-a")}
    others = {"n-a": [image("img-2", "https://creativecommons.org/publicdomain/zero/1.0/",
                            "Acrocanthosaurus atokensis")]}  # fmt: skip
    hints = {"acrocanthosaurus": ["acrocanthosaurus atokensis"]}
    with make_client(httpx.MockTransport(phylopic_handler(known, others, hints))) as client:
        out = images.fetch_phylopic(client, "Acrocanthosaurus", BUILD)
    assert out["found"] and out["node_uuid"] == "n-a"
    assert out["species_nodes"] == ["acrocanthosaurus atokensis"]
    assert [i["uuid"] for i in out["images"]] == ["img-n-a", "img-2"]


def test_the_autocomplete_only_takes_species_of_that_genus():
    known = {"tarbosaurusoides x": species_node("Tarbosaurusoides x", "n-x")}
    hints = {"tarbosaurus": ["tarbosaurusoides x", "tarbosaurus"]}
    with make_client(httpx.MockTransport(phylopic_handler(known, None, hints))) as client:
        assert not images.fetch_phylopic(client, "Tarbosaurus", BUILD)["found"]


def test_several_species_nodes_are_merged_primaries_first():
    known = {
        "testosaurus rex": species_node("Testosaurus rex", "n-r"),
        "testosaurus minor": species_node("Testosaurus minor", "n-m"),
    }
    cc0 = "https://creativecommons.org/publicdomain/zero/1.0/"
    others = {"n-r": [image("img-r2", cc0, "Testosaurus rex")]}
    hints = {"testosaurus": ["testosaurus rex", "testosaurus minor"]}
    with make_client(httpx.MockTransport(phylopic_handler(known, others, hints))) as client:
        out = images.fetch_phylopic(client, "Testosaurus", BUILD)
    assert [i["uuid"] for i in out["images"]] == ["img-n-r", "img-n-m", "img-r2"]
    assert out["image"]["uuid"] == "img-n-r"


def test_a_species_name_does_not_ask_the_autocomplete():
    hints = {"testosaurus rex": ["testosaurus rex foo"]}
    with make_client(httpx.MockTransport(phylopic_handler({}, None, hints))) as client:
        assert not images.fetch_phylopic(client, "Testosaurus rex", BUILD)["found"]


def test_a_species_filed_under_another_genus_is_taken_as_a_labelled_synonym():
    # PhyloPic files Gorgosaurus libratus as "Albertosaurus libratus"; "Gorgosaurus
    # lancensis" is an old name of Nanotyrannus. Both are kept, labelled with the binomial
    # looked up; dbt only draws the one PBDB counts as a valid species of the genus.
    albertosaurus = species_node("Albertosaurus libratus", "n-al")
    albertosaurus["names"].append([{"class": "scientific", "text": "Gorgosaurus libratus"}])
    albertosaurus["_embedded"]["primaryImage"]["_links"]["specificNode"] = {
        "title": "Albertosaurus libratus"
    }
    nano = species_node("Nanotyrannus lancensis", "n-na")
    nano["names"].append([{"class": "scientific", "text": "Gorgosaurus lancensis"}])

    def handler(request):
        if request.url.path == "/autocomplete":
            return httpx.Response(200, json={"matches": [
                "gorgosaurus", "gorgosaurus lancensis", "gorgosaurus libratus"]})  # fmt: skip
        if request.url.path == "/images":
            return httpx.Response(200, json={"_embedded": {"items": []}})
        wanted = request.url.params["filter_name"]
        items = {"gorgosaurus lancensis": [nano], "gorgosaurus libratus": [albertosaurus]}
        if wanted not in items:
            return httpx.Response(404, json={"errors": []})
        return httpx.Response(200, json={"_embedded": {"items": items[wanted]}})

    with make_client(httpx.MockTransport(handler)) as client:
        out = images.fetch_phylopic(client, "Gorgosaurus", BUILD)
    assert out["species_nodes"] == ["gorgosaurus lancensis", "gorgosaurus libratus"]
    assert [(i["node"], i.get("synonym_of")) for i in out["images"]] == [
        ("Gorgosaurus lancensis", "nanotyrannus lancensis"),
        ("Gorgosaurus libratus", "Albertosaurus libratus"),
    ]
    assert out["image"] is None  # a synonym node gives no page picture
