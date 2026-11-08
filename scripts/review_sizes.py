"""Review a sample of the extracted body sizes by hand (size comparator, ALCANCE §11.3).

A small local page (http://127.0.0.1:8773) shows, one taxon at a time, the length that the
comparator would draw (the taxon's main estimate), the verified sentence it comes from and
the literal quote of the source; the answer (S correct, N wrong, ? cannot tell) is saved
at once to ``eval/sizes/review.csv``. The sample is drawn once (seeded, the same share of
rule and LLM readings as in the data, at least a third from the LLM) and kept in
``eval/sizes/sample.json``. Run ``paleo sizes extract`` first.

    uv run python scripts/review_sizes.py --sample 20
"""

# ruff: noqa: E501  (the review page is inline HTML and Spanish text)
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from paleo import sizes
from paleo.config import get_paths, project_root

EVAL = project_root() / "eval" / "sizes"
FIELDS = ["taxon_key", "fact_id", "method", "min_m", "max_m", "verdict", "note", "reviewed_at"]

PAGE = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Revisar tamaños</title>
<style>
:root{--bg:#f7f3ea;--fg:#2a2420;--muted:#776b60;--card:#fffdf8;--line:#e3dccf;--acc:#b5652b}
@media (prefers-color-scheme:dark){:root{--bg:#171310;--fg:#ece5d8;--muted:#a59885;--card:#211b17;--line:#3a312a;--acc:#e08b4f}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}.bar{height:6px;background:var(--line);border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
.card{background:var(--card);border-radius:14px;padding:18px 20px;margin:14px 0;box-shadow:0 1px 3px #0002}
.meta{color:var(--muted);font-size:.85rem}.t{font-size:1.3rem;font-weight:650;margin:.2rem 0 .6rem}.d{font-size:1.1rem}
.src{color:var(--muted);font-size:.88rem;border-left:3px solid var(--line);padding-left:10px;margin-top:14px;max-height:14rem;overflow:auto}
.yn{display:flex;gap:10px;margin-top:12px}.yn button{flex:1;padding:12px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--fg);font:inherit;cursor:pointer}
.yn button.mine{background:var(--acc);color:#fff}input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg);font:inherit;margin-top:10px}
.help{color:var(--muted);font-size:.8rem}a{color:var(--acc)}
</style>
<main><p class="help" id="count"></p><div class="bar"><i id="prog"></i></div><div id="view"></div>
<p class="help"><b>S</b> correcta · <b>N</b> incorrecta (no es la longitud del cuerpo entero de un adulto, o la cifra está mal leída) · <b>?</b> no lo sé · <b>C</b> escribe un comentario (Intro para salir) · <b>←</b>/<b>→</b> moverse</p></main>
<script>
let D,i=0;const $=s=>document.querySelector(s),esc=s=>(s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const key=x=>x.taxon_key;
async function load(){D=await (await fetch("/data")).json();i=Math.max(0,D.items.findIndex(x=>!D.review[key(x)]));if(i<0)i=0;draw()}
function draw(){const x=D.items[i],r=D.review[key(x)]||{},n=D.items.filter(y=>D.review[key(y)]).length;
$("#prog").style.width=(100*n/D.items.length)+"%";$("#count").textContent=n+" de "+D.items.length;
$("#view").innerHTML=`<div class="card"><p class="meta">${esc(x.method=="llm"?"leída por el LLM":"leída por la regla")} · fuente: <a href="${esc(x.source_url)}" target="_blank" rel="noopener">${esc(x.source_title)}</a> (${esc(x.source_license||"")})</p>
<p class="t"><i>${esc(x.taxon)}</i></p><p class="d">Longitud del cuerpo de un adulto: <b>${esc(x.value)}</b></p>
<p class="meta">Frase verificada (${esc(x.fact_id)}): ${esc(x.statement)}</p>
<div class="src"><b>Cita literal de la fuente:</b><br>${esc(x.quote)}</div>
<div class="yn">${[["yes","S · correcta"],["no","N · incorrecta"],["unsure","? · no lo sé"]].map(v=>`<button data-v="${v[0]}" class="${r.verdict==v[0]?"mine":""}">${v[1]}</button>`).join("")}</div>
<input id="note" placeholder="Comentario (opcional)" value="${esc(r.note||"")}"></div>`;
document.querySelectorAll(".yn button").forEach(b=>b.onclick=()=>save(b.dataset.v))}
async function save(v){const x=D.items[i];const note=$("#note").value;D.review[key(x)]={verdict:v,note};
await fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({taxon_key:x.taxon_key,verdict:v,note})});i=Math.min(i+1,D.items.length-1);draw()}
document.addEventListener("keydown",e=>{if(e.target.id=="note"){if(e.key=="Enter"){e.preventDefault();e.target.blur()}return}
if(e.key=="s"||e.key=="S")save("yes");else if(e.key=="n"||e.key=="N")save("no");else if(e.key=="?")save("unsure");
else if(e.key=="c"||e.key=="C"){e.preventDefault();$("#note").focus()}
else if(e.key=="ArrowRight"){i=Math.min(i+1,D.items.length-1);draw()}else if(e.key=="ArrowLeft"){i=Math.max(i-1,0);draw()}});
load();
</script></html>"""


def value(e: dict) -> str:
    def m(v: float) -> str:
        return (f"{round(v * 100):g} cm" if v < 1 else f"{round(v, 1):g} m").replace(".", ",")

    q = {"up_to": "hasta ", "at_least": "al menos ", "about": ""}.get(e["qualifier"], "")
    if e["min_m"] == e["max_m"]:
        return q + m(e["max_m"])
    return f"{m(e['min_m']).split(' ')[0]}\u2013{m(e['max_m'])}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument("--port", type=int, default=8773)
    args = parser.parse_args()

    rows = json.loads(sizes.sizes_path(get_paths().data / "derived").read_text(encoding="utf-8"))
    main_est = {}
    for r in rows:
        e = r["estimates"][0]  # the main one comes first
        main_est[r["taxon_key"]] = {
            "taxon_key": r["taxon_key"],
            "taxon": r["taxon"],
            **e,
            "value": value(e),
        }
    sample_path = EVAL / "sample.json"
    if not sample_path.exists():
        rng = random.Random(7)
        by_method = {
            m: sorted(k for k, e in main_est.items() if e["method"] == m) for m in ("rule", "llm")
        }
        n_llm = max(args.sample // 3, round(args.sample * len(by_method["llm"]) / len(main_est)))
        keys = rng.sample(by_method["llm"], min(n_llm, len(by_method["llm"])))
        keys += rng.sample(by_method["rule"], args.sample - len(keys))
        rng.shuffle(keys)
        EVAL.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(json.dumps(keys, indent=1) + "\n", encoding="utf-8")
    keys = json.loads(sample_path.read_text(encoding="utf-8"))
    items = [main_est[k] for k in keys if k in main_est]
    review_csv = EVAL / "review.csv"
    review = {}
    if review_csv.exists():
        with review_csv.open(encoding="utf-8") as f:
            review = {r["taxon_key"]: r for r in csv.DictReader(f)}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, kind: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/data":
                body = json.dumps({"items": items, "review": review}, ensure_ascii=False)
                self._send(body.encode(), "application/json")
            else:
                self._send(PAGE.encode(), "text/html; charset=utf-8")

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            e = main_est[body["taxon_key"]]
            review[e["taxon_key"]] = {
                "taxon_key": e["taxon_key"], "fact_id": e["fact_id"], "method": e["method"],
                "min_m": e["min_m"], "max_m": e["max_m"], "verdict": body["verdict"],
                "note": body.get("note", ""),
                "reviewed_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            }  # fmt: skip
            EVAL.mkdir(parents=True, exist_ok=True)
            with review_csv.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
                w.writeheader()
                for key in sorted(review):
                    w.writerow(review[key])
            self._send(b"{}", "application/json")

        def log_message(self, *_args) -> None:
            pass

    print(f"{len(items)} sizes to review · http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
