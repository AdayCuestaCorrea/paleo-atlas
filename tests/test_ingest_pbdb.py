import datetime as dt
import json

import httpx

from paleo.http import make_client
from paleo.ingest import pbdb

DAY = dt.date(2026, 11, 2)


def write_interim(root, new_taxa, research):
    folder = root / "wikipedia" / "2026_in_archosaur_paleontology" / "100"
    folder.mkdir(parents=True)
    for name, rows in (("new_taxa", new_taxa), ("research", research)):
        (folder / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def record(name, rank="genus", phylum="Chordata"):
    return {"taxon_name": name, "taxon_rank": rank, "phylum": phylum}


class FakePbdb:
    def __init__(self, known):
        self.known = known
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        names = request.url.params["name"].split(",")
        records = [record(n) for n in names if n in self.known]
        return httpx.Response(200, json={"elapsed_time": 0.01, "records": records})


def test_names_of_interest_collects_candidates(tmp_path):
    write_interim(
        tmp_path,
        new_taxa=[
            {"name": "Crocodylus lucivenator", "name_link": None, "note_links": ["crocodile"]}
        ],
        research=[
            {
                "links": ["Tyrannosaurus", "Andrea Cau", "Hell Creek Formation"],
                "italic_names": ["Troodon formosus"],
            }
        ],
    )
    names = pbdb.names_of_interest(tmp_path)
    assert {
        "Crocodylus lucivenator",
        "Crocodylus",
        "Tyrannosaurus",
        "Troodon formosus",
        "Troodon",
    } <= set(names)
    assert "crocodile" not in names  # lowercase: not a scientific name
    assert "Hell Creek Formation" not in names  # four words


def test_found_and_missing_names_are_both_stored(tmp_path):
    fake = FakePbdb(known={"Spinosaurus"})
    with make_client(httpx.MockTransport(fake)) as client:
        result = pbdb.ingest_names(
            client, ["Spinosaurus", "Antusuchus"], raw_root=tmp_path, today=DAY
        )
    assert (result.found, result.not_found, result.new_versions) == (1, 1, 2)
    store = pbdb.store(tmp_path)
    assert store.latest("Antusuchus")["payload"] == {
        "name": "Antusuchus",
        "found": False,
        "records": [],
    }
    assert store.latest("Spinosaurus")["payload"]["records"][0]["taxon_name"] == "Spinosaurus"
    assert "elapsed_time" not in json.dumps(store.latest("Spinosaurus"))


def test_names_are_requested_in_batches(tmp_path):
    fake = FakePbdb(known=set())
    names = [f"Genus{chr(97 + i % 26)}{i}" for i in range(250)]
    with make_client(httpx.MockTransport(fake)) as client:
        pbdb.ingest_names(client, names, raw_root=tmp_path, today=DAY)
    assert [len(r.url.params["name"].split(",")) for r in fake.requests] == [100, 100, 50]
    assert fake.requests[0].url.params["vocab"] == "pbdb"


def test_recently_checked_names_are_skipped(tmp_path):
    fake = FakePbdb(known={"Spinosaurus"})
    with make_client(httpx.MockTransport(fake)) as client:
        pbdb.ingest_names(client, ["Spinosaurus"], raw_root=tmp_path, today=DAY)
        second = pbdb.ingest_names(
            client, ["Spinosaurus"], raw_root=tmp_path, today=DAY + dt.timedelta(days=3)
        )
        third = pbdb.ingest_names(
            client, ["Spinosaurus"], raw_root=tmp_path, today=DAY + dt.timedelta(days=7)
        )
    assert second.skipped_fresh == 1
    assert third.skipped_fresh == 0
    assert len(fake.requests) == 2


def test_homonyms_keep_every_record(tmp_path):
    def handler(request):
        records = [record("Ozimek", phylum="Chordata"), record("Ozimek", phylum="Arthropoda")]
        return httpx.Response(200, json={"records": records})

    with make_client(httpx.MockTransport(handler)) as client:
        by_name = pbdb.fetch_batch(client, ["Ozimek"])
    assert len(by_name["Ozimek"]) == 2
