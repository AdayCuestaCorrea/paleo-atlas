"""The size comparator's core (site/static/compare.js) run with node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

D = chr(0x2013)  # en dash

JS = Path(__file__).resolve().parents[1] / "site" / "static" / "compare.js"
RUNNER = """
const C = require(process.argv[2]);
const trex = {lo: 11.1, hi: 13, ax: "length", a: 0.32};
const man = {lo: 1.761, hi: 1.761, ax: "height", box: [0.56, 1.761]};
const giraffe = {lo: 4.3, hi: 5.7, ax: "height", a: 1.74};
const boxes = [C.box(trex, "max"), C.box(man, "max"), C.box(giraffe, "min")];
const pos = C.layout(boxes);
const s = C.scale(boxes, pos, 800, 400, {l: 46, r: 16, t: 34, b: 30});
// Two overlapping items: A on top but with ink only on its left half.
const mask = (cols) => ({w: cols.length, h: 1, a: Uint8Array.from(cols)});
const half = [...Array(5).fill(255), ...Array(5).fill(0)];
const A = {z: 2, rect: {l: 0, b: 0, w: 100, h: 50}, mask: mask(half)};
const B = {z: 1, rect: {l: 0, b: 0, w: 100, h: 50}, mask: mask(Array(10).fill(255))};
const tiny = {z: 3, rect: {l: 300, b: 0, w: 3, h: 10}, mask: mask([0, 0])};
console.log(JSON.stringify({
  boxes, pos, s,
  fits: pos.every((p, i) => (46 + (p.x + boxes[i].w) * s) <= 800 - 16 + 1e-6),
  step: [C.step(5), C.step(50), C.step(400)],
  clamp: C.clamp({x: -3, y: 99}, {w: 2, h: 1}, 10, 5),
  drag: [C.isDrag(3, 4), C.isDrag(6, 6)],
  pickLeft: C.pick([A, B], 20, 25) === A, pickRight: C.pick([A, B], 90, 25) === B,
  pickNone: C.pick([A, B], 500, 25), pickTiny: C.pick([A, B, tiny], 296, 5) === tiny,
  hash: C.hash("comparar", ["tyrannosaurus", "man"]),
  parsed: [C.parseHash("#comparar=tyrannosaurus,man"), C.parseHash("#compare=a,b,c,d,e,f,g"),
           C.parseHash("#nothing")],
  ranges: [C.range(0.42, 0.83, "es"), C.range(11.1, 13, "es"), C.range(2.07, 2.07, "en")],
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_scale_layout_and_picking_by_the_drawing(tmp_path):
    run = tmp_path / "run.js"
    run.write_text(RUNNER, encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(run), str(JS)], capture_output=True,
                                    text=True, check=True).stdout)  # fmt: skip
    trex, man, giraffe = out["boxes"]
    assert trex == {"w": 13, "h": pytest.approx(4.16)}
    assert man == {"w": 0.56, "h": 1.761}
    assert giraffe["h"] == 4.3 and giraffe["w"] == pytest.approx(4.3 / 1.74)
    assert out["pos"][0]["x"] < out["pos"][1]["x"] < out["pos"][2]["x"] and out["fits"]
    assert out["step"] == [10, 1, 0.2]
    assert out["clamp"] == {"x": 0, "y": 4}
    assert out["drag"] == [False, True]  # under 8 px it is a click
    # The top item only grabs where it has ink; elsewhere the one below is grabbed.
    assert out["pickLeft"] and out["pickRight"] and out["pickNone"] is None
    assert out["pickTiny"]  # a tiny item is grabbed by its box plus a margin
    assert out["hash"] == "#comparar=tyrannosaurus,man"
    assert out["parsed"] == [["tyrannosaurus", "man"], ["a", "b", "c", "d", "e", "f"], []]
    assert out["ranges"] == [f"42{D}83 cm", f"11,1{D}13 m", "2.07 m"]
