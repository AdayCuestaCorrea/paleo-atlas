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


def test_repeated_claims_are_left_out_in_both_languages(tmp_path):
    from paleo.narrative.review import drop_repetitions, review_notes

    en = [f"Sentence number {i} says something different about this animal." for i in range(6)]
    es = [f"La frase número {i} dice algo distinto de este animal." for i in range(6)]
    for lang, sentences in (("en", en), ("es", es)):
        doc = {"taxon": "X", "taxon_key": "x", "lang": lang, "status": "verified",
               "generator": "t", "prompt_version": "v", "facts_hash": "h", "problems": [],
               "sections": [{"section": "description", "sentences": [
                   {"text": t, "fact_ids": [f"F00{i}"]}
                   for i, t in enumerate(sentences)]}]}  # fmt: skip
        (tmp_path / "texts").mkdir(exist_ok=True)
        (tmp_path / "texts" / f"x.{lang}.json").write_text(json.dumps(doc), "utf-8")
    problems = [{"sentences": [1, 4], "kind": "repetition", "reason": "same claim"},
                {"sentences": [2], "kind": "about_something_else", "reason": "a relative"},
                {"sentences": [0, 3], "kind": "contradiction", "reason": "two sizes"}]  # fmt: skip
    assert drop_repetitions(tmp_path, "x", problems) == 1
    for lang, sentences in (("en", en), ("es", es)):
        doc = json.loads((tmp_path / "texts" / f"x.{lang}.json").read_text("utf-8"))
        now = [s["text"] for sec in doc["sections"] for s in sec["sentences"]]
        assert now == [t for i, t in enumerate(sentences) if i != 4]
    pairs = [{"en": t} for t in en]
    notes = review_notes(pairs, problems)  # only the contradiction goes to the writer
    assert len(notes) == 1 and notes[0].startswith("- contradiction:") and en[3] in notes[0]


def test_flagged_sentences_are_renumbered_after_the_repetitions_left_out():
    from paleo.narrative.review import flagged_now

    record = {"repetitions_dropped": 1, "problems": [
        {"sentences": [1, 4], "kind": "repetition", "reason": "same claim"},
        {"sentences": [3, 6], "kind": "contradiction", "reason": "two sizes"},
        {"sentences": [4], "kind": "missing_context", "reason": "the dropped one"},
        {"sentences": [2], "kind": "about_something_else", "reason": "a relative"}]}  # fmt: skip
    assert flagged_now(record, 6) == [{"sentences": [3, 5], "kind": "contradiction",
                                       "reason": "two sizes"}]  # fmt: skip
    assert flagged_now({**record, "repetitions_dropped": 0}, 7)[0]["sentences"] == [3, 6]


_SAME = "The animal had a long tail and a small head on a long neck."


class FixLLM:
    """Returns sentence 1 as it was and sentence 2 written again (fix prompt), and
    adapts what it gets to Spanish."""

    label = "fake/writer"

    def __init__(self, fixed="The animal was a slow walker on four legs, as its bones show."):
        self.fixed, self.calls = fixed, []

    def complete_json(self, system, user, output, max_tokens=0):
        from paleo.narrative.review import FixedSentence, FixedSentences
        from paleo.narrative.write import AdaptedSentence, AdaptedText

        self.calls.append(user)
        if output is FixedSentences:
            return FixedSentences(sentences=[FixedSentence(index=1, text=_SAME, fact_ids=["F001"]),
                                         FixedSentence(index=2, text=self.fixed,
                                                           fact_ids=["F002"])])  # fmt: skip
        n = sum(line[:1].isdigit() for line in user.splitlines())
        return AdaptedText(sentences=[AdaptedSentence(
            index=i, text="El animal caminaba despacio a cuatro patas, como muestran sus huesos.")
            for i in range(1, n + 1)])  # fmt: skip


def _fix_page(root):
    en = [
        "The animal had a long tail and a small head on a long neck.",
        "These hollow spaces held air sacs.",
        "It lived near rivers and lakes in a warm, wet climate.",
        "Its teeth were thin and shaped like pegs for stripping leaves.",
    ]
    es = [
        "El animal tenía una cola larga y una cabeza pequeña sobre un cuello largo.",
        "Estos espacios huecos contenían sacos aéreos.",
        "Vivía cerca de ríos y lagos en un clima cálido y húmedo.",
        "Sus dientes eran finos y con forma de clavija para arrancar hojas.",
    ]
    for lang, sentences in (("en", en), ("es", es)):
        doc = {"taxon": "Xus", "taxon_key": "xus", "lang": lang, "status": "verified",
               "generator": "t", "prompt_version": "v", "facts_hash": "h", "problems": [],
               "review": "unchanged",
               "sections": [{"section": "description", "sentences": [
                   {"text": t, "fact_ids": [f"F00{i}"]}
                   for i, t in enumerate(sentences, 1)]}]}  # fmt: skip
        (root / "texts").mkdir(exist_ok=True)
        (root / "texts" / f"xus.{lang}.json").write_text(json.dumps(doc), "utf-8")
    facts = [{"fact_id": f"F00{i}", "category": "description", "statement": s, "quote": ""}
             for i, s in enumerate([en[0], "It walked slowly on four legs, its bones show.",
                                    en[2], en[3]], 1)]  # fmt: skip
    (root / "facts").mkdir()
    (root / "facts" / "xus.json").write_text(json.dumps({"facts": facts}), "utf-8")
    return en, es


def _texts(root, lang):
    doc = json.loads((root / "texts" / f"xus.{lang}.json").read_text("utf-8"))
    return doc, [s["text"] for sec in doc["sections"] for s in sec["sentences"]]


def test_only_the_flagged_sentence_is_written_again_in_both_languages(tmp_path):
    from paleo.narrative.review import fix_sentences

    en, es = _fix_page(tmp_path)
    problems = [{"sentences": [0, 1], "kind": "missing_context", "reason": "no hollow spaces"}]
    llm = FixLLM()
    out = fix_sentences(llm, "xus", [], problems, derived_root=tmp_path,
                        scientific_names=set(), ages={})  # fmt: skip
    assert out == "replaced"
    doc, now_en = _texts(tmp_path, "en")
    assert now_en == [en[0], llm.fixed, en[2], en[3]]
    assert doc["prompt_version"] == "v" and doc["facts_hash"] == "h"
    assert doc["sections"][0]["sentences"][1]["fact_ids"] == ["F002"]
    es_doc, now_es = _texts(tmp_path, "es")
    assert now_es[0] == es[0] and now_es[2:] == es[2:] and now_es[1] != es[1]
    assert es_doc["review"] == "unchanged"
    assert "TO FIX: sentences 1, 2" in llm.calls[0]
    assert sum("ENGLISH SENTENCES" in c for c in llm.calls) == 1  # only the new one adapted
    assert llm.calls[1].count("\n1. ") == 1 and "\n2. " not in llm.calls[1]


def test_a_new_sentence_that_keeps_failing_is_left_out_after_the_retries(tmp_path):
    from paleo.narrative.review import fix_sentences

    en, es = _fix_page(tmp_path)
    problems = [{"sentences": [1], "kind": "missing_context", "reason": "no hollow spaces before"}]
    llm = FixLLM(fixed="In 1999 Smith found that these air sacs weighed 45 kg.")  # unsourced
    out = fix_sentences(llm, "xus", [], problems, derived_root=tmp_path,
                        scientific_names=set(), ages={})  # fmt: skip
    # retried with the checks' feedback, then left out (this page can afford one)
    assert out == "replaced"
    fixes = [c for c in llm.calls if "TO FIX" in c]
    assert len(fixes) == 3 and "failed these automatic checks" in fixes[1]
    assert _texts(tmp_path, "en")[1] == [en[0], en[2], en[3]]
    assert _texts(tmp_path, "es")[1] == [es[0], es[2], es[3]]


def test_a_fix_that_changes_nothing_leaves_the_files_alone(tmp_path):
    from paleo.narrative.review import fix_sentences

    _fix_page(tmp_path)
    before = (tmp_path / "texts" / "xus.en.json").read_text("utf-8")
    problems = [{"sentences": [0], "kind": "contradiction", "reason": "two sizes"}]
    out = fix_sentences(FixLLM(), "xus", [], problems, derived_root=tmp_path,
                        scientific_names=set(), ages={})  # fmt: skip
    assert out == "unchanged"
    assert (tmp_path / "texts" / "xus.en.json").read_text("utf-8") == before
