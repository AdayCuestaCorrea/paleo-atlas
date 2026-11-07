"""Review a sample of glossary definitions by hand (§12.2, Phase 5).

A small local page (http://127.0.0.1:8770) shows one published definition at a time,
with the lead of the Wikipedia article it was written from and a link to it; the
answer (S correct, N wrong, ? cannot tell) is saved at once to
``eval/glossary/review.csv``. The sample is drawn once (seeded, half in each
language) and kept in ``eval/glossary/sample.json``.

    uv run python scripts/review_glossary.py --sample 20
"""

# ruff: noqa: E501  (the review page is inline HTML and Spanish text)
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

from paleo.config import get_paths, project_root
from paleo.ingest.glossary import lead_store

EVAL = project_root() / "eval" / "glossary"
FIELDS = ["term_id", "lang", "term", "definition", "verdict", "note", "reviewed_at"]

PAGE = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Revisar glosario</title>
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
<p class="help"><b>S</b> correcta · <b>N</b> incorrecta (dice algo falso o no es lo que significa el término) · <b>?</b> no lo sé · <b>C</b> escribe un comentario (Intro para salir) · <b>←</b>/<b>→</b> moverse</p></main>
<script>
let D,i=0;const $=s=>document.querySelector(s),esc=s=>(s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const key=x=>x.term_id+"."+x.lang;
async function load(){D=await (await fetch("/data")).json();i=Math.max(0,D.items.findIndex(x=>!D.review[key(x)]));if(i<0)i=0;draw()}
function draw(){const x=D.items[i],r=D.review[key(x)]||{},n=D.items.filter(y=>D.review[key(y)]).length;
$("#prog").style.width=(100*n/D.items.length)+"%";$("#count").textContent=n+" de "+D.items.length;
$("#view").innerHTML=`<div class="card"><p class="meta">${x.lang=="es"?"Español":"English"} · fuente: <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source_title)}</a> (revisión ${x.revid})</p>
<p class="t">${esc(x.term)}</p><p class="d">${esc(x.definition)}</p>
<div class="src"><b>Fuente</b> (inicio del artículo):<br>${esc(x.lead)}</div>
<div class="yn">${[["yes","S · correcta"],["no","N · incorrecta"],["unsure","? · no lo sé"]].map(v=>`<button data-v="${v[0]}" class="${r.verdict==v[0]?"mine":""}">${v[1]}</button>`).join("")}</div>
<input id="note" placeholder="Comentario (opcional)" value="${esc(r.note||"")}"></div>`;
document.querySelectorAll(".yn button").forEach(b=>b.onclick=()=>save(b.dataset.v))}
async function save(v){const x=D.items[i];const note=$("#note").value;D.review[key(x)]={verdict:v,note};
await fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({term_id:x.term_id,lang:x.lang,verdict:v,note})});i=Math.min(i+1,D.items.length-1);draw()}
document.addEventListener("keydown",e=>{if(e.target.id=="note"){if(e.key=="Enter"){e.preventDefault();e.target.blur()}return}
if(e.key=="s"||e.key=="S")save("yes");else if(e.key=="n"||e.key=="N")save("no");else if(e.key=="?")save("unsure");
else if(e.key=="c"||e.key=="C"){e.preventDefault();$("#note").focus()}
else if(e.key=="ArrowRight"){i=Math.min(i+1,D.items.length-1);draw()}else if(e.key=="ArrowLeft"){i=Math.max(i-1,0);draw()}});
load();
</script></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()

    paths = get_paths()
    published = {}
    for path in sorted((paths.data / "derived" / "glossary").glob("*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        if d["status"] == "verified":
            published[f"{d['term_id']}.{d['lang']}"] = d
    sample_path = EVAL / "sample.json"
    if not sample_path.exists():
        rng = random.Random(7)
        keys = []
        for lang in ("es", "en"):
            pool = sorted(k for k, d in published.items() if d["lang"] == lang)
            keys += rng.sample(pool, min(len(pool), args.sample // 2))
        rng.shuffle(keys)
        EVAL.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(json.dumps(keys, indent=1) + "\n", encoding="utf-8")
    keys = json.loads(sample_path.read_text(encoding="utf-8"))
    items = []
    for k in keys:
        d = published[k]
        src = d["source"]
        lead = lead_store(src["lang"]).latest(d["term_id"])["payload"]["lead"]
        items.append({
            "term_id": d["term_id"], "lang": d["lang"], "term": d["term"],
            "definition": d["definition"], "source_title": src["title"], "revid": src["revid"],
            "url": f"https://{src['lang']}.wikipedia.org/w/index.php?title="
                   f"{quote(src['title'])}&oldid={src['revid']}",
            "lead": lead[:1500],
        })  # fmt: skip
    review_csv = EVAL / "review.csv"
    review = {}
    if review_csv.exists():
        with review_csv.open(encoding="utf-8") as f:
            review = {f"{r['term_id']}.{r['lang']}": r for r in csv.DictReader(f)}

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
            k = f"{body['term_id']}.{body['lang']}"
            review[k] = {
                "term_id": body["term_id"], "lang": body["lang"], "term": published[k]["term"],
                "definition": published[k]["definition"], "verdict": body["verdict"],
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

    print(f"{len(items)} definitions to review · http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
