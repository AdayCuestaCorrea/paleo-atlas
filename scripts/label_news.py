"""Label news articles by hand, for the classifier's metrics (Phase 5).

A small local page (http://127.0.0.1:8769) shows one article at a time with the
LLM's proposal already marked; every answer is saved at once to
``eval/news/labels.csv`` (category and taxa) and ``eval/news/pairs.csv`` (same story
or not). The LLM's proposal never counts as a label until a person confirms it.

    uv run python scripts/label_news.py --sample 300

The sample is drawn once (seeded) and saved to ``eval/news/sample.json``, so a
session can be resumed and the set stays the same.

    uv run python scripts/label_news.py --blind 50

Blind mode: 50 of the articles already labelled (seeded, some of every class the
person gave), shown WITHOUT the LLM's proposal, saved to ``eval/news/blind_labels.csv``.
It measures the LLM without anchoring and the person against themselves. In both
modes the key D marks an answer as doubtful.
"""

# ruff: noqa: E501, RUF001  (the labelling page is inline HTML and Spanish text)
from __future__ import annotations

import argparse
import csv
import datetime as dt
import itertools
import json
import random
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from paleo.config import get_paths, project_root
from paleo.news.classify import labels_path, load_labels, stored_articles

EVAL = project_root() / "eval" / "news"
LABEL_FIELDS = ["key", "category", "unsure", "taxa", "lang", "outlet", "title", "url",
                "labelled_at"]  # fmt: skip
PAIR_FIELDS = ["key_a", "key_b", "same_story", "labelled_at"]
CATEGORIES = ["new_species", "new_fossil", "new_study", "revision", "noise"]
WORDS = re.compile(r"\w{4,}", re.U)


def read_csv(path: Path, key) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {key(r): r for r in csv.DictReader(f)}


def write_csv(path: Path, fields: list[str], rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])


def draw_sample(articles: dict, llm: dict, size: int, seed: int = 7) -> list[str]:
    """Every article the LLM did not call noise, plus a seeded random share of the rest,
    shuffled so the order gives no hint."""
    rng = random.Random(seed)
    paleo = sorted(k for k in articles if llm.get(k, {}).get("category") not in (None, "noise"))
    rest = sorted(k for k in articles if k not in paleo)
    keys = paleo + rng.sample(rest, max(0, min(len(rest), size - len(paleo))))
    rng.shuffle(keys)
    return keys


def draw_blind(first: dict, size: int, seed: int = 11) -> list[str]:
    """``size`` already labelled articles: an equal share of each class the person gave
    (all of a class if it has fewer), the rest noise; shuffled."""
    rng = random.Random(seed)
    by_class: dict[str, list[str]] = {}
    for key, row in sorted(first.items()):
        by_class.setdefault(row["category"], []).append(key)
    others = [c for c in by_class if c != "noise"]
    share = size // (len(others) + 1) if others else 0
    keys = []
    for c in others:
        keys += rng.sample(by_class[c], min(share, len(by_class[c])))
    noise = by_class.get("noise", [])
    keys += rng.sample(noise, min(len(noise), size - len(keys)))
    rng.shuffle(keys)
    return keys


def candidate_pairs(articles: dict, llm: dict, keys: list[str], days: int = 5) -> list[list[str]]:
    """Pairs that might be the same story: both not noise for the LLM, published within
    ``days`` of each other, and either in different languages, sharing a taxon or
    sharing at least two words of four letters or more."""

    def when(k):
        p = articles[k].get("published")
        return dt.datetime.fromisoformat(p.replace("Z", "+00:00")) if p else None

    paleo = [k for k in keys if llm.get(k, {}).get("category") not in (None, "noise") and when(k)]
    out = []
    for a, b in itertools.combinations(sorted(paleo), 2):
        if abs((when(a) - when(b)).days) > days:
            continue
        ta, tb = articles[a], articles[b]
        words = {w.lower() for w in WORDS.findall(ta["title"])} & {
            w.lower() for w in WORDS.findall(tb["title"])
        }
        taxa = set(llm[a].get("taxa") or []) & set(llm[b].get("taxa") or [])
        if ta["lang"] != tb["lang"] or taxa or len(words) >= 2:
            out.append([a, b])
    return out


PAGE = """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Etiquetar noticias</title>
<style>
:root{--bg:#f7f3ea;--fg:#2a2420;--muted:#776b60;--card:#fffdf8;--line:#e3dccf;--acc:#b5652b;--ok:#4f7a4a}
@media (prefers-color-scheme:dark){:root{--bg:#171310;--fg:#ece5d8;--muted:#a59885;--card:#211b17;--line:#3a312a;--acc:#e08b4f;--ok:#9fc79a}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}
.bar{height:6px;background:var(--line);border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc)}
.card{background:var(--card);border-radius:14px;padding:18px 20px;margin:14px 0;box-shadow:0 1px 3px #0002}
.meta{color:var(--muted);font-size:.85rem}.t{font-size:1.25rem;font-weight:650;margin:.3rem 0}
.s{color:var(--muted)}
.cats{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:12px}
.cats button{padding:10px 4px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--fg);font:inherit;font-size:.85rem;cursor:pointer}
.cats button.llm{border:2px dashed var(--acc)}.cats button.mine{background:var(--acc);color:#fff;border-color:var(--acc)}
.cats b{display:block;font-size:1.1rem}
input{width:100%;box-sizing:border-box;padding:8px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg);font:inherit}
.help{color:var(--muted);font-size:.8rem}.tabs a{margin-right:1rem;color:var(--acc)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.pair .card{margin:0}
.yn{display:flex;gap:10px;margin-top:12px}.yn button{flex:1;padding:12px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--fg);font:inherit;cursor:pointer}
.yn button.mine{background:var(--acc);color:#fff}
@media (max-width:600px){.cats{grid-template-columns:repeat(2,1fr)}.pair{grid-template-columns:1fr}}
</style>
<main><p class="tabs"><a href="#" id="tab1">Titulares</a><a href="#" id="tab2">Pares</a> <span class="help" id="count"></span></p>
<div class="bar"><i id="prog"></i></div><div id="view"></div>
<p class="help" id="help"></p></main>
<script>
const CATS=[["new_species","Especie nueva"],["new_fossil","Hallazgo"],["new_study","Estudio"],["revision","Revisión"],["noise","Ruido"]];
let D,mode="items",i=0,unsure=false;
const $=s=>document.querySelector(s),esc=s=>(s||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
async function load(){D=await (await fetch("/data")).json();i=first();draw()}
function list(){return mode=="items"?D.sample:D.pairs}
function done(k){return mode=="items"?!!D.labels[k]:!!D.pair_labels[k.join("|")]}
function first(){const L=list();const n=L.findIndex(k=>!done(k));return n<0?L.length-1:n}
function art(k){const a=D.articles[k];return `<p class="meta">${esc(a.outlet)} · ${a.lang.toUpperCase()} · ${esc((a.published||"").slice(0,10))} · <a href="${esc(a.url)}" target="_blank" rel="noopener">abrir</a></p><p class="t">${esc(a.title)}</p><p class="s">${esc(a.summary||"")}</p>`}
function draw(){
  const L=list(),n=L.filter(done).length;$("#prog").style.width=(100*n/L.length)+"%";$("#count").textContent=`${n} de ${L.length}`;
  if(mode=="items"){
    const k=L[i],a=D.articles[k],llm=D.llm[k]||{},mine=D.labels[k];unsure=!!(mine&&mine.unsure);
    const taxa=mine?mine.taxa:(llm.taxa||[]).join(", ");
    $("#view").innerHTML=`<div class="card">${art(k)}<div class="cats">${CATS.map((c,j)=>`<button data-c="${c[0]}" class="${llm.category==c[0]?"llm":""} ${mine&&mine.category==c[0]?"mine":""}"><b>${j+1}</b>${c[1]}</button>`).join("")}</div>
    <p class="help" id="doubt" style="margin-top:12px">${unsure?"<b>Marcada como dudosa</b> (D para quitarlo)":""}</p><p class="help" style="margin-top:12px">Taxones (nombres científicos que nombra, separados por comas)</p><input id="taxa" value="${esc(taxa)}"></div>`;
    $("#help").innerHTML=(D.blind?"<b>A ciegas</b>: sin la propuesta del LLM · ":"")+"<b>1–5</b> elige la categoría y pasa a la siguiente · "+(D.blind?"":"<b>Intro</b> acepta la propuesta (borde discontinuo) · ")+"<b>D</b> marca dudosa (antes de elegir) · <b>T</b> edita los taxones (Intro para salir) · <b>←</b>/<b>→</b> moverse";
    document.querySelectorAll(".cats button").forEach(b=>b.onclick=()=>save(b.dataset.c));
  }else{
    const p=L[i],mine=D.pair_labels[p.join("|")];
    $("#view").innerHTML=`<div class="pair"><div class="card">${art(p[0])}</div><div class="card">${art(p[1])}</div></div>
    <div class="yn"><button data-v="yes" class="${mine&&mine.same_story=="yes"?"mine":""}"><b>S</b> · la misma noticia</button><button data-v="no" class="${mine&&mine.same_story=="no"?"mine":""}"><b>N</b> · noticias distintas</button></div>`;
    $("#help").innerHTML="<b>S</b> misma noticia (el mismo hallazgo o estudio, aunque sea en otro medio o idioma) · <b>N</b> distintas · <b>←</b>/<b>→</b> moverse";
    document.querySelectorAll(".yn button").forEach(b=>b.onclick=()=>savePair(b.dataset.v));
  }
}
async function post(body){await fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})}
async function save(cat){const k=list()[i];const taxa=$("#taxa").value;D.labels[k]={category:cat,taxa,unsure};await post({kind:"item",key:k,category:cat,taxa,unsure});next()}
async function savePair(v){const p=list()[i];D.pair_labels[p.join("|")]={same_story:v};await post({kind:"pair",key_a:p[0],key_b:p[1],same_story:v});next()}
function next(){i=Math.min(i+1,list().length-1);draw()}
document.addEventListener("keydown",e=>{
  if(e.target.id=="taxa"){if(e.key=="Enter"){e.preventDefault();e.target.blur()}return}
  if(e.key=="ArrowRight"){i=Math.min(i+1,list().length-1);draw()}
  else if(e.key=="ArrowLeft"){i=Math.max(i-1,0);draw()}
  else if(mode=="items"){
    if(e.key>="1"&&e.key<="5")save(CATS[+e.key-1][0]);
    else if(e.key=="Enter"){const c=(D.labels[list()[i]]||D.llm[list()[i]]||{}).category;if(c){unsure=unsure||!!(D.labels[list()[i]]||{}).unsure;save(c)}}
    else if(e.key=="t"||e.key=="T"){e.preventDefault();$("#taxa").focus()}
    else if(e.key=="d"||e.key=="D"){unsure=!unsure;$("#doubt").innerHTML=unsure?"<b>Marcada como dudosa</b> (D para quitarlo)":""}
  }else{if(e.key=="s"||e.key=="S")savePair("yes");else if(e.key=="n"||e.key=="N")savePair("no")}
});
$("#tab1").onclick=e=>{e.preventDefault();mode="items";i=first();draw()};
$("#tab2").onclick=e=>{e.preventDefault();mode="pairs";i=first();draw()};
load().then(()=>{if(D.blind)$("#tab2").hidden=true});
</script></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=300)
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--blind", type=int, default=0, help="Blind sample of this size.")
    args = parser.parse_args()

    paths = get_paths()
    articles = stored_articles(paths.raw)
    llm = load_labels(labels_path(paths.data / "derived"))
    sample_path = EVAL / ("blind_sample.json" if args.blind else "sample.json")
    if args.blind and not sample_path.exists():
        first = read_csv(EVAL / "labels.csv", lambda r: r["key"])
        sample_path.write_text(json.dumps({"items": draw_blind(first, args.blind), "pairs": []},
                                          indent=1) + "\n", encoding="utf-8")  # fmt: skip
    if sample_path.exists():
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
    else:
        keys = draw_sample(articles, llm, args.sample)
        sample = {"items": keys, "pairs": candidate_pairs(articles, llm, keys)}
        EVAL.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(json.dumps(sample, indent=1) + "\n", encoding="utf-8")
    labels_csv = EVAL / ("blind_labels.csv" if args.blind else "labels.csv")
    pairs_csv = EVAL / "pairs.csv"
    labels = read_csv(labels_csv, lambda r: r["key"])
    pairs = read_csv(pairs_csv, lambda r: f"{r['key_a']}|{r['key_b']}")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, kind: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/data":
                keys = set(sample["items"]) | {k for p in sample["pairs"] for k in p}
                data = {
                    "sample": sample["items"], "pairs": sample["pairs"],
                    "articles": {k: articles[k] for k in keys},
                    "llm": {} if args.blind else {k: llm[k] for k in keys if k in llm},
                    "blind": bool(args.blind),
                    "labels": labels, "pair_labels": pairs,
                }  # fmt: skip
                self._send(json.dumps(data, ensure_ascii=False).encode(), "application/json")
            else:
                self._send(PAGE.encode(), "text/html; charset=utf-8")

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            stamp = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
            if body["kind"] == "item":
                a = articles[body["key"]]
                taxa = ", ".join(t.strip() for t in body["taxa"].split(",") if t.strip())
                labels[body["key"]] = {
                    "key": body["key"], "category": body["category"],
                    "unsure": "yes" if body.get("unsure") else "", "taxa": taxa,
                    "lang": a["lang"], "outlet": a["outlet"], "title": a["title"],
                    "url": a["url"], "labelled_at": stamp,
                }  # fmt: skip
                write_csv(labels_csv, LABEL_FIELDS, labels)
            else:
                pairs[f"{body['key_a']}|{body['key_b']}"] = {
                    "key_a": body["key_a"], "key_b": body["key_b"],
                    "same_story": body["same_story"], "labelled_at": stamp,
                }  # fmt: skip
                write_csv(pairs_csv, PAIR_FIELDS, pairs)
            self._send(b"{}", "application/json")

        def log_message(self, *_args) -> None:
            pass

    print(f"{len(sample['items'])} articles and {len(sample['pairs'])} pairs to label")
    print(f"http://127.0.0.1:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
