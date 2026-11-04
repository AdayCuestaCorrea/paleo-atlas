"""The home page explorer (site/static/home.js) run with node over a tiny explore.json."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from paleo.site import explore

JS = Path(__file__).resolve().parents[1] / "site" / "static" / "home.js"
GROUPS = ["non_avian_dinosaurs", "pterosaurs"]
TAXA = [
    {"taxon_key": "allosaurus", "taxon_name": "Allosaurus", "page_type": "genus",
     "taxon_group": "non_avian_dinosaurs", "first_appearance_max_ma": 155,
     "last_appearance_min_ma": 145.5, "country_codes": ["US", "PT"]},
    {"taxon_key": "tyrannosaurus", "taxon_name": "Tyrannosaurus", "page_type": "genus",
     "taxon_group": "non_avian_dinosaurs", "first_appearance_max_ma": 68,
     "last_appearance_min_ma": 66, "country_codes": ["US"],
     "image_url": "https://upload.wikimedia.org/x.jpg", "image_source": "commons"},
    {"taxon_key": "hintighernia-x", "taxon_name": "Hintighernia x", "page_type": "new",
     "taxon_group": "pterosaurs", "age_text": "Early Cretaceous", "countries": ["Portugal"]},
    {"taxon_key": "zeta-y", "taxon_name": "Zeta y", "page_type": "new",
     "taxon_group": "pterosaurs", "age_text": "Late Jurassic", "countries": ["Portugal"]},
]  # fmt: skip
RUNNER = """
const h = require(process.argv[2]);
const ix = require(process.argv[3]);
const taxa = h.decode(ix);
const sizes = {time: ix.periods.length, group: ix.groups.length, place: ix.countries.length};
const keys = {time: ix.periods.map(p => p[0]), group: ix.groups.map(g => g[0]),
              place: ix.countries.map(c => c[0])};
const run = (st) => {
  const t = h.tally(taxa, st, sizes);
  return {found: h.order(t.found, st.scope).map(x => x.n),
          time: t.time, group: t.group, place: t.place};
};
const st = {scope: "all", time: keys.time.indexOf("jurassic"), group: null, place: null};
console.log(JSON.stringify({
  decoded: taxa.map(t => [t.n, t.u, t.img, t.flags]),
  all: run({scope: "all", time: null, group: null, place: null}),
  newOnly: run({scope: "new", time: null, group: null, place: null}),
  jurassic: run(st),
  hash: h.toHash(st, keys),
  back: h.fromHash("#" + h.toHash(st, keys), keys),
  bad: h.fromHash("#time=nowhere&place=pt&foo", keys),
  clampLeft: h.clampView([-500, -500, 30]),
  tooFar: h.clampView([0, 0, 5000]),
  europe: h.boxView(h.REGIONS.europe),
  zoomIn: h.zoomView(h.FULL, 0.5, 0.5, 0.5),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_explorer_filters_counts_orders_and_keeps_the_map_inside_the_world(tmp_path):
    entries = explore.explore_entries(
        TAXA, groups=GROUPS, curiosities={"allosaurus"},
        ranks={"zeta-y": 0, "hintighernia-x": 1},
    )  # fmt: skip
    data = explore.build_explore(
        entries, "en", lambda key: f"/en/taxa/{key}.html", groups=GROUPS,
        centroids={"us": (40.0, -100.0), "pt": (39.5, -8.0)},
    )  # fmt: skip
    (tmp_path / "ix.json").write_text(json.dumps(data))
    (tmp_path / "run.js").write_text(RUNNER)
    out = json.loads(subprocess.run(
        ["node", str(tmp_path / "run.js"), str(JS), str(tmp_path / "ix.json")],
        capture_output=True, text=True, check=True).stdout)  # fmt: skip

    assert out["decoded"][1] == ["Tyrannosaurus", "/en/taxa/tyrannosaurus.html",
                                 "https://upload.wikimedia.org/x.jpg", explore.PHOTO]  # fmt: skip
    assert out["decoded"][2][1] == "/en/taxa/hintighernia-x.html"
    # Whole atlas: curiosities first, then photos, then the rest.
    assert out["all"]["found"] == ["Allosaurus", "Tyrannosaurus", "Hintighernia x", "Zeta y"]
    assert out["newOnly"]["found"] == ["Zeta y", "Hintighernia x"]  # newest first
    assert out["newOnly"]["group"] == [0, 2]
    # With the Jurassic chosen, the period counts ignore it (cross counts) but the
    # groups and countries only count Jurassic pages.
    jur = out["jurassic"]
    assert jur["found"] == ["Allosaurus", "Zeta y"]
    assert jur["time"][7] == 2  # Cretaceous: Tyrannosaurus, Hintighernia
    assert jur["group"] == [1, 1]
    assert jur["place"] == [2, 1]  # pt: Allosaurus, Zeta; us: Allosaurus
    assert out["hash"] == "all&time=jurassic"
    assert out["back"] == {"scope": "all", "time": 6, "group": None, "place": None}
    assert out["bad"] == {"scope": "new", "time": None, "group": None, "place": 0}
    assert out["clampLeft"] == [-180, -90, 30, 15]
    assert out["tooFar"] == [-180, -90, 360, 180]
    x, y, w, h = out["europe"]
    assert w == 2 * h and x <= -25 and x + w >= 45 and y <= -71 and y + h >= -33
    assert out["zoomIn"] == [-90, -45, 180, 90]
