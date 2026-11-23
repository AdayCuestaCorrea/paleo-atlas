"""Reviewer experiments on the 15 evaluated pages (Phase 7, step 5).
uv run python exp.py NAME --model M --effort none --batch 3 --prompt FILE [--pages a,b]
Writes results/NAME.json with recall per language and cause and the false-flag rate."""

import argparse
import collections
import csv
import json
import sys
import time
from pathlib import Path

from pydantic import BaseModel

import paleo.narrative.review as R
from paleo.llm import LLM, PROVIDERS, Provider

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "eval" / "fichas" / "reviewer_study"

ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--model", default="paleo-qwen3.5-9b")
ap.add_argument("--effort", default="none")
ap.add_argument("--batch", type=int, default=3)
ap.add_argument("--prompt", default=str(REPO / "src/paleo/narrative/prompts/review_text.md"))
ap.add_argument("--pages", default="")
ap.add_argument("--max-tokens", type=int, default=1500)
ap.add_argument("--cot", action="store_true")
a = ap.parse_args()

text = Path(a.prompt).read_text("utf-8")
system = text.split("\n", 1)[1].strip()
R.prompt = lambda name: (system, "exp")  # type: ignore[assignment]
R.BATCH = a.batch
orig = R.review_page


class CoTItem(BaseModel):
    index: int
    en_claims_vs_quotes: str  # each claim of the English sentence, and whether a quote states it
    en_ok: bool
    es_vs_en: str  # what the Spanish says differently from the English, if anything
    es_ok: bool = True


class CoTPage(BaseModel):
    sentences: list[CoTItem]


Schema = CoTPage if a.cot else R.PageReview


def review_page(llm, taxon, pairs):
    # same as R.review_page but with our max_tokens
    flags = []
    numbered = list(enumerate(pairs, start=1))
    for start in range(0, len(numbered), R.BATCH):
        batch = numbered[start : start + R.BATCH]
        result = llm.complete_json(
            system, R._user_message(taxon, batch), Schema, max_tokens=a.max_tokens
        )
        wanted = {n for n, _ in batch}
        for r in result.sentences:
            if r.index not in wanted:
                continue
            p = pairs[r.index - 1]
            if not r.en_ok:
                flags.append(
                    {
                        "index": r.index - 1,
                        "lang": "en",
                        "sentence": p["en"],
                        "reason": getattr(r, "en_reason", "")
                        or getattr(r, "en_claims_vs_quotes", ""),
                    }
                )
            if not r.es_ok and p["es"]:
                flags.append(
                    {
                        "index": r.index - 1,
                        "lang": "es",
                        "sentence": p["es"],
                        "reason": getattr(r, "es_reason", "") or getattr(r, "es_vs_en", ""),
                    }
                )
    return flags


provider = Provider(
    "ollama",
    PROVIDERS["ollama"].base_url,
    extra_body={} if a.effort == "default" else {"reasoning_effort": a.effort},
)
llm = LLM(provider, a.model, timeout=1200)
derived = REPO / "data" / "derived"
rows = [
    r
    for r in csv.DictReader((REPO / "eval/fichas/findings.csv").open(encoding="utf-8"))
    if r["element"] == "text"
]
causes = collections.defaultdict(set)
expected, known = set(), set()
for r in rows:
    for lang in ("en", "es"):
        for s in filter(None, r[f"{lang}_sentences"].split(" || ")):
            k = (r["taxon_key"], lang, s)
            known.add(k)
            if r["severity"] in ("high", "medium"):
                expected.add(k)
                causes[k].add(r["cause"])
pages = sorted({r["taxon_key"] for r in rows})
if a.pages:
    pages = [p for p in pages if p in a.pages.split(",")]
present, flagged, clean, all_flags = set(), set(), 0, []
t0 = time.monotonic()
for key in pages:
    pairs = R.page_pairs(derived, key)
    if not pairs:
        continue
    taxon = json.loads((derived / "texts" / f"{key}.en.json").read_text("utf-8"))["taxon"]
    try:
        flags = review_page(llm, taxon, pairs)
    except Exception as exc:
        print(key, "failed", exc, file=sys.stderr)
        continue
    for p in pairs:
        for lang in ("en", "es"):
            if p[lang]:
                k = (key, lang, p[lang])
                clean += k not in known
                if k in expected:
                    present.add(k)
    for f in flags:
        k = (key, f["lang"], f["sentence"])
        flagged.add(k)
        all_flags.append({"page": key, **f, "known": k in known})
secs = time.monotonic() - t0
found = present & flagged
false = {f for f in flagged if f not in known}
by_lang = {
    lg: f"{len([x for x in found if x[1] == lg])}/{len([x for x in present if x[1] == lg])}"
    for lg in ("en", "es")
}
by_cause = collections.Counter()
tot_cause = collections.Counter()
for k in present:
    for c in causes[k]:
        tot_cause[c] += 1
        by_cause[c] += k in found
res = {
    "name": a.name,
    "model": a.model,
    "effort": a.effort,
    "batch": a.batch,
    "prompt": a.prompt,
    "pages": len(pages),
    "seconds": round(secs),
    "expected": len(present),
    "found": len(found),
    "recall": round(len(found) / max(1, len(present)), 3),
    "clean": clean,
    "false_flags": len(false),
    "false_rate": round(len(false) / max(1, clean), 3),
    "by_lang": by_lang,
    "by_cause": {c: f"{by_cause[c]}/{n}" for c, n in tot_cause.most_common()},
    "llm": str(llm.stats),
    "flags": all_flags,
}
OUT.mkdir(exist_ok=True)
(OUT / f"{a.name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
print(json.dumps({k: v for k, v in res.items() if k != "flags"}, ensure_ascii=False))
