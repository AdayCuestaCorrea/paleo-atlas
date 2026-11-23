"""Page-level reviewer experiment: the whole English page at once, for problems no
single sentence shows (contradictions, repeated claims, missing context).
uv run python scripts/reviewer_study/page_review.py NAME --model gpt-oss:20b
    --effort low [--union e5_oss20_low_b3] [--knowledge]"""

import argparse
import csv
import json
import time
from pathlib import Path

from pydantic import BaseModel

import paleo.narrative.review as R
from paleo.llm import LLM, PROVIDERS, Provider

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "eval" / "fichas" / "reviewer_study"
ap = argparse.ArgumentParser()
ap.add_argument("name")
ap.add_argument("--model", default="gpt-oss:20b")
ap.add_argument("--effort", default="low")
ap.add_argument("--union", default="")
ap.add_argument("--knowledge", action="store_true")
ap.add_argument("--union-en-only", action="store_true")
ap.add_argument("--tokens", type=int, default=6000)
a = ap.parse_args()

SYSTEM = (
    """You are the fact-checker of Paleo Atlas, a popular-science encyclopedia of
fossil animals written by a language model from cited sources. You receive the
numbered English sentences of ONE page. Find only the problems that a careful
reader sees by reading the page as a whole:
- two sentences that contradict each other (different sizes, masses, ages,
  places or classifications for the same thing, without saying they are
  different estimates);
- a sentence that depends on something the page never said ("these hollow
  spaces", "the latter", "this specimen" with nothing before it);
- the same claim said twice;
- a sentence about a formation, a relative or a group presented as if it were
  about the animal itself.
"""
    + (
        """- a claim that you know to be wrong or long outdated in paleontology (only
  when you are sure: a well-known, settled fact).
"""
        if a.knowledge
        else ""
    )
    + """
Do NOT report style, missing information or anything you are not sure about.
Most pages have none or one or two problems. Answer with the list of problems,
each with the sentence numbers involved, the kind and a short reason."""
)


class Problem(BaseModel):
    sentences: list[int]
    kind: str
    reason: str


class PageProblems(BaseModel):
    problems: list[Problem]


llm = LLM(
    Provider("ollama", PROVIDERS["ollama"].base_url, extra_body={"reasoning_effort": a.effort}),
    a.model,
    timeout=1200,
)
derived = REPO / "data" / "derived"
rows = [
    r
    for r in csv.DictReader((REPO / "eval/fichas/findings.csv").open(encoding="utf-8"))
    if r["element"] == "text"
]
expected, known = set(), set()
for r in rows:
    for lang in ("en", "es"):
        for s in filter(None, r[f"{lang}_sentences"].split(" || ")):
            known.add((r["taxon_key"], lang, s))
            if r["severity"] in ("high", "medium"):
                expected.add((r["taxon_key"], lang, s))
pages = sorted({r["taxon_key"] for r in rows})
present, flagged, clean, out = set(), set(), 0, []
t0 = time.monotonic()
for key in pages:
    pairs = R.page_pairs(derived, key)
    taxon = json.loads((derived / "texts" / f"{key}.en.json").read_text("utf-8"))["taxon"]
    user = f"Page: {taxon}\n\n" + "\n".join(f"[{i}] {p['en']}" for i, p in enumerate(pairs, 1))
    res = llm.complete_json(SYSTEM, user, PageProblems, max_tokens=a.tokens)
    for p in pairs:
        for lang in ("en", "es"):
            if p[lang]:
                k = (key, lang, p[lang])
                clean += k not in known
                if k in expected:
                    present.add(k)
    for prob in res.problems:
        for n in prob.sentences:
            if 1 <= n <= len(pairs):
                p = pairs[n - 1]
                # a page-level problem flags the English sentence and its Spanish one
                for lang in ("en", "es"):
                    if p[lang]:
                        flagged.add((key, lang, p[lang]))
                out.append(
                    {
                        "page": key,
                        "n": n,
                        "kind": prob.kind,
                        "reason": prob.reason,
                        "sentence": p["en"],
                        "known": (key, "en", p["en"]) in known,
                    }
                )


def score(fl):
    found = present & fl
    false = {f for f in fl if f not in known}
    return {
        "found": len(found),
        "expected": len(present),
        "recall": round(len(found) / len(present), 3),
        "false_flags": len(false),
        "false_rate": round(len(false) / clean, 3),
    }


result = {
    "name": a.name,
    "model": a.model,
    "seconds": round(time.monotonic() - t0),
    "page_only": score(flagged),
    "llm": str(llm.stats),
    "flags": out,
}
if a.union:
    other = json.loads((OUT / f"{a.union}.json").read_text("utf-8"))
    sent = {
        (f["page"], f.get("lang", "en"), f["sentence"])
        for f in other["flags"]
        if not a.union_en_only or f.get("lang", "en") == "en"
    }
    result["union_with_" + a.union] = score(flagged | sent)
OUT.mkdir(exist_ok=True)
(OUT / f"{a.name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "flags"}, ensure_ascii=False))
