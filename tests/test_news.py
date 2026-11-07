"""News classification (Phase 5): batches, what is asked again, what the model left out."""

import datetime as dt
import json

from paleo.ingest import news as news_ingest
from paleo.news import classify

DAY = dt.date(2026, 11, 7)
NOW = dt.datetime(2026, 11, 7, 12, tzinfo=dt.UTC)


class FakeLLM:
    """Answers every item but the ones whose headline contains "skip"."""

    label = "fake/model"

    def __init__(self):
        self.calls = []

    def complete_json(self, system, user, output, max_tokens):
        self.calls.append(user)
        items = []
        for line in user.splitlines()[1:]:
            index, text = line.split(". ", 1)
            if "skip" in text:
                continue
            category = "new_species" if "new species" in text else "noise"
            taxa = ["Spinosaurus mirabilis", " "] if "Spinosaurus" in text else []
            items.append({"index": int(index), "category": category, "taxa": taxa})
        return output.model_validate({"items": items})


def store_articles(tmp_path, titles):
    items = news_ingest.store(tmp_path)
    for n, title in enumerate(titles):
        url = f"https://example.org/{n}"
        payload = {"url": url, "outlet": "X", "lang": "en", "title": title,
                   "published": f"2026-11-0{n % 7 + 1}T10:00:00Z"}  # fmt: skip
        items.save_if_changed(news_ingest.item_key(url), payload, DAY)
    items.flush()


def test_articles_are_classified_in_batches_and_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(classify, "BATCH", 2)
    store_articles(tmp_path, ["A new species of Spinosaurus", "Mars rover", "Please skip me"])
    llm, derived = FakeLLM(), tmp_path / "derived"
    r = classify.classify_news(llm, raw_root=tmp_path, derived_root=derived, now=NOW)
    assert (r.total, r.classified, r.missing, len(llm.calls)) == (3, 2, 1, 2)
    rows = json.loads(classify.labels_path(derived).read_text())
    spino = next(row for row in rows if row["category"] == "new_species")
    assert spino["taxa"] == ["Spinosaurus mirabilis"]  # blank names dropped
    assert spino["prompt_version"].startswith("news-") and spino["generator"] == "fake/model"

    again = classify.classify_news(llm, raw_root=tmp_path, derived_root=derived, now=NOW)
    assert (again.up_to_date, again.classified, again.missing) == (2, 0, 1)  # only the left-out


def test_a_changed_headline_is_asked_again(tmp_path):
    store_articles(tmp_path, ["Mars rover"])
    llm, derived = FakeLLM(), tmp_path / "derived"
    classify.classify_news(llm, raw_root=tmp_path, derived_root=derived, now=NOW)
    store_articles(tmp_path, ["Mars rover finds a new species"])
    r = classify.classify_news(llm, raw_root=tmp_path, derived_root=derived, now=NOW)
    assert r.classified == 1


def test_the_model_sees_the_summary_only_when_stored():
    plain = {"title": "T. rex grew slowly", "lang": "en"}
    assert classify.model_input(plain) == "T. rex grew slowly"
    rich = {**plain, "summary": "It took 40 years."}
    assert classify.model_input(rich) == "T. rex grew slowly — It took 40 years."
    assert classify.input_hash(plain) != classify.input_hash(rich)


def test_groups_join_pairs_within_the_window_transitively():
    import numpy as np

    from paleo.news import dedup

    arts = {
        "a": {"published": "2026-11-06T10:00:00Z"},
        "b": {"published": "2026-11-06T12:00:00Z"},
        "c": {"published": "2026-11-08T09:00:00Z"},
        "d": {"published": "2026-10-01T09:00:00Z"},  # same text, a month earlier
    }
    keys = ["a", "b", "c", "d"]
    sim = np.array([
        [1.0, 0.9, 0.1, 0.9],
        [0.9, 1.0, 0.8, 0.9],
        [0.1, 0.8, 1.0, 0.9],
        [0.9, 0.9, 0.9, 1.0],
    ])  # fmt: skip
    pairs = dedup.links(keys, arts, sim, threshold=0.75)
    assert [(a, b) for a, b, _ in pairs] == [("a", "b"), ("b", "c")]
    assert dedup.groups(keys, pairs) == {"a": "a", "b": "a", "c": "a", "d": "d"}


def test_tfidf_finds_the_same_story_in_other_words():
    from paleo.news import dedup

    sim = dedup.tfidf_similarity([
        "Scientists just found dinosaur blood that survived 115 million years",
        "Traces of dinosaur blood found in world-first discovery",
        "A satellite detects volcanic activity on Mars",
    ])  # fmt: skip
    assert sim[0, 1] > sim[0, 2] and sim[0, 1] > 0.2


def test_class_scores_by_hand():
    from paleo.news.evaluate import scores

    gold = ["new_species", "new_species", "noise", "noise", "new_study"]
    pred = ["new_species", "noise", "noise", "noise", None]
    s = scores(gold, pred)
    sp, no = s["per_class"]["new_species"], s["per_class"]["noise"]
    assert (sp["precision"], sp["recall"], sp["support"]) == (1.0, 0.5, 2)
    assert (no["precision"], no["recall"]) == (2 / 3, 1.0)
    assert s["per_class"]["new_study"]["recall"] == 0.0  # no answer counts as wrong
    assert s["accuracy"] == 3 / 5
    present_f1 = [2 / 3, 0.8, 0.0]  # new_species, noise, new_study (others absent)
    assert abs(s["macro_f1"] - sum(present_f1) / 3) < 1e-9
    assert s["confusion"]["new_species"] == {"new_species": 1, "noise": 1}


def test_taxa_scores_compare_genera():
    from paleo.news.evaluate import taxa_scores

    gold = {"a": ["Tyrannosaurus rex"], "b": [], "c": ["Spinosaurus", "Jian"]}
    pred = {"a": ["Tyrannosaurus"], "b": ["Velociraptor"], "c": ["Spinosaurus"]}
    t = taxa_scores(gold, pred)
    assert (t["precision"], t["recall"], t["gold_names"]) == (2 / 3, 2 / 3, 3)


def test_grouping_threshold_is_chosen_on_other_folds():
    from paleo.news.evaluate import grouping_scores

    sims = [0.9, 0.8, 0.7, 0.3, 0.2, 0.1, 0.85, 0.15, 0.75, 0.25]
    same = [True, True, True, False, False, False, True, False, True, False]
    g = grouping_scores(sims, same)
    assert (g["precision"], g["recall"], g["f1"]) == (1.0, 1.0, 1.0)
    assert 0.3 < g["threshold"] <= 0.7
