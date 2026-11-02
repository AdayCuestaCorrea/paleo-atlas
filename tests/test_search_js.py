"""The browser search (site/static/search.js) run with node over a tiny index."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from paleo.site.search import build_index

JS = Path(__file__).resolve().parents[1] / "site" / "static" / "search.js"
TAXA = [
    {"taxon_name": "Carnotaurus", "taxon_key": "carnotaurus", "family_name": "Abelisauridae",
     "taxon_group": "non_avian_dinosaurs", "first_appearance_max_ma": 72.2,
     "last_appearance_min_ma": 66.0, "countries": ["Argentina"]},
    {"taxon_name": "Spinosaurus mirabilis", "taxon_key": "spinosaurus-mirabilis",
     "family_name": "Spinosauridae", "taxon_group": "non_avian_dinosaurs",
     "age_text": "Late Cretaceous (Cenomanian)", "countries": ["Niger"],
     "name_authors": "Sereno et al.", "page_type": "new"},
    {"taxon_name": "Tyrannosaurus rex", "taxon_key": "tyrannosaurus-rex",
     "family_name": "Tyrannosauridae", "taxon_group": "non_avian_dinosaurs",
     "first_appearance_max_ma": 68.0, "last_appearance_min_ma": 66.0},
    {"taxon_name": "Sinosaurus", "taxon_key": "sinosaurus", "taxon_group": "non_avian_dinosaurs",
     "first_appearance_max_ma": 199.0, "last_appearance_min_ma": 190.0},
]  # fmt: skip
RUNNER = """
const s = require(process.argv[2]);
s.prepare(require(process.argv[3]));
const out = {};
for (const q of process.argv.slice(4)) out[q] = s.search(q).map(r => r.t.n);
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_search_matches_spanish_forms_typos_and_ages(tmp_path):
    index = tmp_path / "index.json"
    index.write_text(json.dumps(build_index(TAXA, "es", lambda key: f"/es/taxones/{key}.html")))
    runner = tmp_path / "run.js"
    runner.write_text(RUNNER)
    queries = ["Abelisáuridos", "espinosaurio", "tyranosaurus", "Cretácico", "jurasico",
               "T. rex", "sereno", "zzzz"]  # fmt: skip
    result = subprocess.run(
        ["node", str(runner), str(JS), str(index), *queries],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    found = json.loads(result.stdout)
    assert found["Abelisáuridos"] == ["Carnotaurus"]
    assert found["espinosaurio"] == ["Spinosaurus mirabilis"]  # not Sinosaurus
    assert found["tyranosaurus"] == ["Tyrannosaurus rex"]
    assert set(found["Cretácico"]) == {"Carnotaurus", "Spinosaurus mirabilis", "Tyrannosaurus rex"}
    assert found["jurasico"] == ["Sinosaurus"]
    assert found["T. rex"] == ["Tyrannosaurus rex"]
    assert found["sereno"] == ["Spinosaurus mirabilis"]
    assert found["zzzz"] == []


EXPAND = """
const s = require(process.argv[2]);
s.prepare(require(process.argv[3]));
console.log(JSON.stringify(s.taxa().map(t => ({n: t.n, u: t.u, img: t.img, sil: t.sil,
  new: t.new, meta: t.meta, f: t.f, facets: t.facets}))));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_compact_index_expands_to_the_full_entries(tmp_path):
    from paleo.site.search import entry

    url = lambda key: f"/es/taxones/{key}.html"  # noqa: E731
    index = tmp_path / "index.json"
    index.write_text(json.dumps(build_index(TAXA, "es", url)))
    runner = tmp_path / "expand.js"
    runner.write_text(EXPAND)
    result = subprocess.run(["node", str(runner), str(JS), str(index)],
                            capture_output=True, text=True, check=True)  # fmt: skip
    expanded = json.loads(result.stdout)
    for got, taxon in zip(expanded, TAXA, strict=True):
        want = entry(taxon, "es", url(taxon["taxon_key"]))
        want["facets"] = {k: v for k, v in want["facets"].items() if v}
        want["meta"] = want["meta"] or ""
        assert got == want
