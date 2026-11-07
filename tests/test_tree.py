"""Kinship tree (Phase 3, H7): PBDB clades, the neighbourhood drawing and its page."""

import datetime as dt

import httpx

from paleo.http import make_client
from paleo.ingest import pbdb
from paleo.site import taxon_page
from paleo.site.data import SiteData

DAY = dt.date(2026, 11, 3)


class FakeClades:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request.url.params)
        if request.url.params.get("rel") == "all_parents":
            rows = [{"oid": "txn:1", "rnk": "unranked clade", "nam": "Life", "par": "txn:1"},
                    {"oid": "txn:9", "rnk": "genus", "nam": "Otodus", "par": "txn:2"}]  # fmt: skip
        else:
            rows = [{"oid": "txn:2", "rnk": "family", "nam": "Otodontidae", "par": "txn:1"}]
        return httpx.Response(200, json={"elapsed_time": 0.1, "records": rows})


def test_clades_are_fetched_monthly_per_block_root(tmp_path):
    fake = FakeClades()
    roots = [
        c for c in pbdb.scope_clades() if c.pbdb_base_name in ("Chondrichthyes", "featured_fishes")
    ]
    with make_client(transport=httpx.MockTransport(fake)) as client:
        r = pbdb.ingest_clades(client, roots, raw_root=tmp_path, today=DAY)
        assert (r.blocks, r.new_versions) == (2, 2)
        # A block defined by a list of genera only asks for their ancestors.
        assert [p.get("rel") for p in fake.requests] == [None, "all_parents", "all_parents"]
        assert pbdb.ingest_clades(client, roots, raw_root=tmp_path, today=DAY).skipped_fresh == 2
    stored = pbdb.clades_store(tmp_path).latest("Chondrichthyes")["payload"]
    assert [c["nam"] for c in stored["ancestors"]] == ["Life"]  # genera are left out


def row(key, name, path, *, first=100.0, last=90.0, self_=False, depth=2):
    return {"level_clade_name": "Spinosauridae", "level_genera": 4, "member_key": key,
            "member_name": name, "is_self": self_, "common_depth": depth,
            "first_appearance_max_ma": first, "last_appearance_min_ma": last,
            "path": [{"clade_no": f"txn:{n}", "name": n} for n in path]}  # fmt: skip


ROWS = [
    row(
        "spinosaurus",
        "Spinosaurus",
        ["Spinosaurinae", "Spinosaurini"],
        first=125.8,
        last=72.2,
        self_=True,
        depth=0,
    ),
    row("oxalaia", "Oxalaia", ["Spinosaurinae"], first=100.5, last=93.9, depth=2),
    row("baryonyx", "Baryonyx", ["Baryonychinae"], first=139.1, last=110.1, depth=3),
    row("suchomimus", "Suchomimus", ["Baryonychinae"], first=None, last=None, depth=3),
]


def test_relatives_are_rows_on_a_time_axis_with_every_range_written():
    chart = taxon_page.kin_rows(ROWS)
    assert chart["clade"] == "Spinosauridae" and chart["total"] == 4
    # Same order as the neighbourhood (closest first), the page itself marked.
    assert [r["name"] for r in chart["rows"]] == [
        "Spinosaurus",
        "Oxalaia",
        "Baryonyx",
        "Suchomimus",
    ]
    me = chart["rows"][0]
    assert me["self"] and (me["from"], me["to"]) == (125.8, 72.2)
    # Older to the left: Baryonyx (139.1 Ma) starts before Spinosaurus (125.8 Ma).
    assert (
        chart["rows"][2]["left"] < me["left"] and 0 <= me["left"] < me["left"] + me["width"] <= 100
    )
    assert chart["rows"][3]["to"] is None and "left" not in chart["rows"][3]  # no ages: no bar
    ticks = [t["ma"] for t in chart["ticks"]]
    assert 3 <= len(ticks) <= 7 and ticks == sorted(ticks)
    assert all(0 <= t["pos"] <= 100 for t in chart["ticks"])
    assert [b["key"] for b in chart["bands"]] == ["cretaceous"]  # 70-139 Ma (with margin)
    assert taxon_page.kin_rows([]) is None


def test_species_pages_show_the_tree_of_their_genus():
    data = SiteData([], {}, {}, {}, {}, neighborhood={"spinosaurus": {"group": ROWS}})
    assert data.kinship({"taxon_key": "spinosaurus-mirabilis", "genus_key": "spinosaurus"})
    assert data.kinship({"taxon_key": "otodus", "genus_key": None}) == {}
