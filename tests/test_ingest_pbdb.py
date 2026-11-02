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
    assert "Andrea" not in names and "Hell" not in names  # no genus split of non-taxa


def test_linked_names_that_are_never_genera_are_not_asked():
    for name in ("Albian", "Brazil", "Arabian ostrich", "Late Cretaceous", "Nomen dubium"):
        assert not pbdb.looks_like_linked_taxon(name), name
    for name in ("Tyrannosaurus rex", "Asiatyrannus xui", "Camptosaurus dispar", "Jian"):
        assert pbdb.looks_like_linked_taxon(name), name


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


# --- Encyclopedia catalog (Phase 3) ----------------------------------------------------


def write_seed(path):
    path.write_text(
        "block,taxon_group,pbdb_base_name,priority,enabled\n"
        "archosaurs,birds,Aves,1,true\n"
        "archosaurs,non_avian_dinosaurs,Dinosauria,2,true\n"
        "fossil_fishes,placoderms,Placodermi,1,false\n"
    )
    return path


def test_scope_seed_gives_the_enabled_clades(tmp_path):
    seed = write_seed(tmp_path / "scope.csv")
    assert [c.pbdb_base_name for c in pbdb.scope_clades(seed)] == ["Aves", "Dinosauria"]
    every = pbdb.scope_clades(seed, enabled_only=False)
    assert [(c.block, c.priority, c.enabled) for c in every][-1] == ("fossil_fishes", 1, False)


def test_the_real_scope_seed_covers_the_three_blocks_of_the_scope():
    clades = pbdb.scope_clades()
    assert {c.block for c in clades} == {"archosaurs", "marine_reptiles", "fossil_fishes"}
    # every block has a root, used for occurrences and to verify articles in Wikidata
    roots = {c.block for c in clades if c.block_root and c.wikidata_item}
    assert roots == {"archosaurs", "marine_reptiles", "fossil_fishes"}


def test_featured_fishes_are_asked_for_by_name(tmp_path):
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    (seeds / "featured_fishes.csv").write_text("genus,reason\nLeedsichthys,big\nTiktaalik,legs\n")
    clade = pbdb.ScopeClade("fossil_fishes", "other_fishes", "featured_fishes", 1, True,
                            True, "Q25241", "seed:featured_fishes")  # fmt: skip
    assert clade.base_names(seeds) == "Leedsichthys,Tiktaalik"
    plain = pbdb.ScopeClade("archosaurs", "birds", "Aves", 1, True)
    assert plain.base_names(seeds) == "Aves"


def test_catalog_asks_for_accepted_extinct_genera_once_a_month(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        base = request.url.params["base_name"]
        rows = [{"taxon_name": f"{base}us"}, {"taxon_name": f"{base}us rex"}]
        return httpx.Response(200, json={"elapsed_time": 0.5, "records": rows})

    clades = pbdb.scope_clades(write_seed(tmp_path / "scope.csv"))
    with make_client(transport=httpx.MockTransport(handler)) as client:
        first = pbdb.ingest_catalog(client, clades, raw_root=tmp_path, today=DAY)
        again = pbdb.ingest_catalog(
            client, clades, raw_root=tmp_path, today=DAY + dt.timedelta(days=29)
        )
        later = pbdb.ingest_catalog(
            client, clades, raw_root=tmp_path, today=DAY + dt.timedelta(days=31)
        )
    assert (first.records, first.new_versions) == (4, 2)
    assert again.skipped_fresh == 2 and later.skipped_fresh == 0
    assert later.new_versions == 0  # same answer (elapsed_time is volatile): no new version
    params = requests[0].url.params
    assert params["taxon_status"] == "accepted"  # "valid" would list junior synonyms
    assert (params["extant"], params["rank"]) == ("no", "genus,species")
    stored = pbdb.catalog_store(tmp_path).latest("Aves")
    assert stored["payload"]["records"][1]["taxon_name"] == "Avesus rex"


def test_occurrences_are_downloaded_once_per_block_root(tmp_path):
    requests = []

    def handler(request):
        requests.append(request)
        rows = [{"oid": "occ:1", "tna": "Spinosaurus aegyptiacus", "cc2": "EG"}]
        return httpx.Response(200, json={"elapsed_time": 0.1, "records": rows})

    seed = tmp_path / "scope.csv"
    seed.write_text(
        "block,taxon_group,pbdb_base_name,priority,enabled,block_root,wikidata_item\n"
        "archosaurs,birds,Aves,1,true,false,\n"
        "archosaurs,other_archosaurs,Archosauria,9,true,true,Q130910\n"
    )
    clades = pbdb.scope_clades(seed)
    assert [c.wikidata_item for c in clades] == [None, "Q130910"]
    with make_client(transport=httpx.MockTransport(handler)) as client:
        r = pbdb.ingest_occurrences(client, clades, raw_root=tmp_path, today=DAY)
    assert (r.blocks, r.records) == (1, 1)
    assert [q.url.params["base_name"] for q in requests] == ["Archosauria"]
    assert requests[0].url.params["idreso"] == "genus"
