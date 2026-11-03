"""Kinship tree (Phase 3, H7): PBDB clades, the neighbourhood drawing and its page."""

import datetime as dt
import re

import httpx

from paleo.http import make_client
from paleo.ingest import pbdb
from paleo.site import tree
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


def test_single_child_clades_are_collapsed_and_leaves_never_overlap():
    root = tree.build(ROWS)
    names = {c.name for c in root.children}
    assert names == {"Spinosaurinae", "Baryonychinae"}  # Spinosaurini had one genus
    n = tree.layout(root)
    ys = [leaf.y for leaf in root.leaves()]
    assert n == 4 and len(set(ys)) == 4 and ys == sorted(ys)
    for node in root.children:
        assert node.children[0].y <= node.y <= node.children[-1].y


def test_svg_links_every_genus_highlights_the_page_and_escapes_names():
    svg = str(tree.svg([*ROWS, row("x", "<b>X</b>", [])], lang="es",
                       url=lambda kind, key: f"/es/taxones/{key}.html", label="Grupo"))  # fmt: skip
    assert svg.count('<a href="/es/taxones/') == 5
    assert svg.count("is-self") == 1 and "&lt;b&gt;X" in svg and "<b>X" not in svg
    assert ">Cretácico<" in svg  # period names in the page's language
    xs = [float(x) for x in re.findall(r'class="tree__bar" x="([\d.]+)"', svg)]
    assert len(xs) == 4  # Suchomimus has no dates: no bar, still a link
    assert all(
        tree.CLADO_W + tree.LABEL_W <= x <= tree.CLADO_W + tree.LABEL_W + tree.TIME_W for x in xs
    )


def test_species_pages_show_the_tree_of_their_genus():
    data = SiteData([], {}, {}, {}, {}, neighborhood={"spinosaurus": {"group": ROWS}})
    assert data.kinship({"taxon_key": "spinosaurus-mirabilis", "genus_key": "spinosaurus"})
    assert data.kinship({"taxon_key": "otodus", "genus_key": None}) == {}
