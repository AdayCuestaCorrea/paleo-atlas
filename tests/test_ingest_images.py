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


def phylopic_handler(known):
    def handler(request):
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
