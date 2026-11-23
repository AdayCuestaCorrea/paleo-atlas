"""The model as reviewer (Phase 7, step 5), with a fake model."""

import csv
import json
from types import SimpleNamespace

from paleo.narrative.review import (
    PageReview,
    SentenceReview,
    evaluate,
    is_reviewed,
    page_pairs,
    review_page,
    save_flags,
)

EN = ["Parasaurolophus reached maturity in about one year.",
      "Parasaurolophus lived in North America during the Campanian."]  # fmt: skip
ES = ["Parasaurolophus alcanzaba la madurez en aproximadamente un año.",
      "Parasaurolophus vivió en Norteamérica durante el Campaniense."]  # fmt: skip


class FakeLLM:
    """Flags the English sentences that mention maturity."""

    label = "fake/reviewer"

    def __init__(self):
        self.calls = []

    def complete_json(self, system, user, output, max_tokens=0):
        self.calls.append(user)
        items = []
        for line in user.splitlines():
            if line.startswith("[") and "] EN: " in line:
                n = int(line[1 : line.index("]")])
                bad = "maturity" in line
                reason = "misreads the quote" if bad else ""
                items.append(SentenceReview(index=n, en_ok=not bad, en_reason=reason))
        return PageReview(sentences=items)


def _page(root):
    for lang, sentences in (("en", EN), ("es", ES)):
        doc = {"taxon": "Parasaurolophus", "taxon_key": "parasaurolophus", "lang": lang,
               "status": "verified", "generator": "t", "prompt_version": "v",
               "facts_hash": "h", "problems": [],
               "sections": [{"section": "description", "sentences": [
                   {"text": t, "fact_ids": [f"F00{i}"]}
                   for i, t in enumerate(sentences, 1)]}]}  # fmt: skip
        (root / "texts").mkdir(exist_ok=True)
        (root / "texts" / f"parasaurolophus.{lang}.json").write_text(json.dumps(doc), "utf-8")
    facts = {"facts": [{"fact_id": "F001", "statement": "A juvenile was about one year old.",
                        "quote": "about one year old"}]}  # fmt: skip
    (root / "facts").mkdir()
    (root / "facts" / "parasaurolophus.json").write_text(json.dumps(facts), "utf-8")


def test_flags_are_recorded_and_a_page_is_not_reviewed_twice(tmp_path):
    _page(tmp_path)
    pairs = page_pairs(tmp_path, "parasaurolophus")
    assert pairs[0]["es"] == ES[0] and pairs[0]["facts"][0]["quote"] == "about one year old"
    llm = FakeLLM()
    flags = review_page(llm, "Parasaurolophus", pairs)
    assert [(f["index"], f["lang"]) for f in flags] == [(0, "en")]
    assert 'quote: "about one year old"' in llm.calls[0]
    assert not is_reviewed(tmp_path, "parasaurolophus", pairs)
    save_flags(tmp_path, "parasaurolophus", "Parasaurolophus", llm, pairs, flags)
    assert is_reviewed(tmp_path, "parasaurolophus", pairs)


def test_the_measurement_counts_found_and_false_flags(tmp_path):
    _page(tmp_path)
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    with (eval_dir / "findings.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "taxon_key", "severity", "element",
                                          "en_sentences", "es_sentences"])  # fmt: skip
        w.writeheader()
        w.writerow({"id": "p-01", "taxon_key": "parasaurolophus", "severity": "high",
                    "element": "text", "en_sentences": EN[0], "es_sentences": ES[0]})  # fmt: skip
    result = evaluate(FakeLLM(), tmp_path, eval_dir)
    # the English sentence is found; its Spanish one is not (the fake only reads English)
    assert (result["expected"], result["found"], result["false_flags"]) == (2, 1, 0)
    assert result["recall"] == 0.5 and result["passes"]
    assert SimpleNamespace(**result).clean_sentences == 2
