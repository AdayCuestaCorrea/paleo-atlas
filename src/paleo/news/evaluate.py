"""Metrics of the news pipeline against the labels made by hand (eval/news/).

* Category: the classical baseline (TF-IDF of character n-grams + logistic regression,
  cross-validated, so it is never scored on what it was trained on) and each LLM
  configuration, with precision, recall and F1 per class and language, macro F1 and
  the confusion matrix.
* Taxa: the genera linked to each article against the genera of the labels.
* Grouping: for each similarity method, the threshold is chosen on some folds of the
  labelled pairs and scored on the others (cross-validated), so the reported figure
  is not tuned on itself.

The LLM's proposal is never a label: only rows a person confirmed are in labels.csv.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from paleo.news.classify import CATEGORIES

FOLDS = 5
SEED = 7


def load_labels(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return {
            r["key"]: {**r, "taxa": [t.strip() for t in r["taxa"].split(",") if t.strip()]}
            for r in csv.DictReader(f)
        }


def load_pairs(path: Path) -> list[tuple[str, str, bool]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [(r["key_a"], r["key_b"], r["same_story"] == "yes") for r in csv.DictReader(f)]


def scores(gold: Sequence[str], pred: Sequence[str | None]) -> dict[str, Any]:
    """Per-class precision/recall/F1/support, macro F1, accuracy and confusion matrix
    (rows: gold, columns: predicted; a missing prediction counts as wrong)."""
    per = {}
    for c in CATEGORIES:
        tp = sum(g == c and p == c for g, p in zip(gold, pred, strict=True))
        fp = sum(g != c and p == c for g, p in zip(gold, pred, strict=True))
        fn = sum(g == c and p != c for g, p in zip(gold, pred, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per[c] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    present = [c for c in CATEGORIES if per[c]["support"]]
    confusion = {g: dict(Counter(p for gg, p in zip(gold, pred, strict=True) if gg == g))
                 for g in CATEGORIES}  # fmt: skip
    return {
        "n": len(gold),
        "accuracy": sum(g == p for g, p in zip(gold, pred, strict=True)) / len(gold) if gold else 0,
        "macro_f1": sum(per[c]["f1"] for c in present) / len(present) if present else 0.0,
        "per_class": per,
        "confusion": confusion,
    }


def baseline_predictions(texts: Sequence[str], gold: Sequence[str]) -> list[str]:
    """Cross-validated predictions of TF-IDF (character 2-5-grams) + logistic regression."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline

    model = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
        LogisticRegression(max_iter=2_000, class_weight="balanced"),
    )
    smallest = min(Counter(gold).values())
    folds = StratifiedKFold(n_splits=max(2, min(FOLDS, smallest)), shuffle=True,
                            random_state=SEED)  # fmt: skip
    return list(cross_val_predict(model, list(texts), list(gold), cv=folds))


def genus_set(names: Sequence[str]) -> set[str]:
    return {n.split()[0].lower() for n in names if n.split()}


def taxa_scores(gold: dict[str, list[str]], pred: dict[str, list[str]]) -> dict[str, float]:
    """Micro precision/recall/F1 of the genera linked per article."""
    tp = fp = fn = 0
    for key, names in gold.items():
        g, p = genus_set(names), genus_set(pred.get(key, []))
        tp, fp, fn = tp + len(g & p), fp + len(p - g), fn + len(g - p)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "gold_names": tp + fn}


def _f1(sims: np.ndarray, same: np.ndarray, threshold: float) -> tuple[float, float, float]:
    pred = sims >= threshold
    tp, fp, fn = int((pred & same).sum()), int((pred & ~same).sum()), int((~pred & same).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall, (2 * precision * recall / (precision + recall) if tp else 0.0)


def grouping_scores(sims: Sequence[float], same: Sequence[bool]) -> dict[str, float]:
    """Cross-validated pair precision/recall/F1: the threshold of each fold is the one
    with the best F1 on the other folds. Also the threshold chosen on all pairs."""
    s, y = np.asarray(sims, dtype=float), np.asarray(same, dtype=bool)
    values = np.unique(np.round(s, 3))
    candidates = (values[:-1] + values[1:]) / 2 if len(values) > 1 else values  # midpoints

    def best(idx: np.ndarray) -> float:
        """The middle of the thresholds with the best F1 (not an edge, which would sit
        right on a training pair)."""
        f1s = np.array([_f1(s[idx], y[idx], t)[2] for t in candidates])
        top = candidates[f1s == f1s.max()]
        return float(np.median(top))

    order = np.random.default_rng(SEED).permutation(len(s))
    pred = np.zeros(len(s), dtype=bool)
    for fold in np.array_split(order, min(FOLDS, len(s))):
        train = np.setdiff1d(order, fold)
        pred[fold] = s[fold] >= best(train)
    tp, fp, fn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "pairs": len(s), "same": int(y.sum()), "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if tp else 0.0,
        "threshold": float(best(order)),
    }  # fmt: skip


def judged_scores(
    answers: dict[tuple[str, str], bool], pairs: Sequence[tuple[str, str, bool]]
) -> dict[str, Any]:
    """Pair precision/recall/F1 of yes/no answers (an unanswered pair counts as no)."""
    tp = sum(answers.get((a, b)) is True and same for a, b, same in pairs)
    fp = sum(answers.get((a, b)) is True and not same for a, b, same in pairs)
    fn = sum(answers.get((a, b)) is not True and same for a, b, same in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "pairs": len(pairs), "same": tp + fn, "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if tp else 0.0, "threshold": None,
    }  # fmt: skip


def _pct(x: float) -> str:
    return f"{100 * x:.0f} %"


def report_markdown(summary: dict[str, Any]) -> str:
    """The report of one evaluation, for eval/reports/<date>-news.md."""
    s = summary
    lines = [
        "# News pipeline — evaluation",
        "",
        f"{s['evaluated_at']} · {s['labelled']} articles labelled by hand "
        f"({s['by_lang']['en']} EN, {s['by_lang']['es']} ES) · {s['pairs']} labelled pairs",
        "",
        "Labels: `eval/news/labels.csv` and `pairs.csv`, made with `scripts/label_news.py`",
        "(the LLM's proposal was shown, but only a person's answer is a label). The baseline",
        f"is scored with {FOLDS}-fold cross-validation, so never on what it was trained on.",
        "",
        "## Category",
        "",
        "| Configuration | Macro F1 | Accuracy | "
        + " | ".join(f"F1 {c}" for c in CATEGORIES)
        + " | Cost |",
        "|---|---:|---:|" + "---:|" * len(CATEGORIES) + "---|",
    ]
    for name, r in s["category"].items():
        per = r["all"]["per_class"]
        lines.append(
            f"| {name} | {r['all']['macro_f1']:.2f} | {_pct(r['all']['accuracy'])} | "
            + " | ".join(f"{per[c]['f1']:.2f}" for c in CATEGORIES)
            + f" | {r.get('cost', '—')} |"
        )
    lines += ["", "By language (macro F1):", "", "| Configuration | EN | ES |", "|---|---:|---:|"]
    for name, r in s["category"].items():
        lines.append(f"| {name} | {r['en']['macro_f1']:.2f} | {r['es']['macro_f1']:.2f} |")
    lines += ["", "Support per class: " + ", ".join(
        f"{c} {n}" for c, n in s["support"].items()) + "."]  # fmt: skip
    c = s.get("caveats")
    if c:
        lines += [
            "",
            "**How far to trust these figures.** The labeller saw the production LLM's "
            f"proposal: {c['category_as_proposed']} of {s['labelled']} labels kept its "
            "category, so its scores are an upper bound (anchoring), not an independent "
            "measure; the baseline is not affected. A blind sample (labels made without "
            "the proposal) is the honest check.",
        ]
    if not s["support"].get("revision"):
        lines += ["", "No article of the sample is a revision: that class is not measured."]
    lines += ["", "## Taxa", ""]
    if c and c["taxa_edited"] == 0:
        lines += [f"Not measured: none of the {c['with_taxa']} taxa proposed by the LLM was "
                  "edited, so comparing with the labels would only measure the proposal "
                  "against itself."]  # fmt: skip
        s = {**s, "taxa": {}}
    else:
        lines += ["| Method | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
    for name, t in s["taxa"].items():
        lines.append(f"| {name} | {t['precision']:.2f} | {t['recall']:.2f} | {t['f1']:.2f} |")
    lines += ["", "## Same story (grouping)", "",
              "The pairs were labelled without any proposal: these figures are independent.",
              "",
              "| Method | Pairs (same) | Precision | Recall | F1 | Threshold |",
              "|---|---:|---:|---:|---:|---:|"]  # fmt: skip
    for name, g in s["grouping"].items():
        cut = "—" if g["threshold"] is None else f"{g['threshold']:.3f}"
        lines.append(f"| {name} | {g['pairs']} ({g['same']}) | {g['precision']:.2f} | "
                     f"{g['recall']:.2f} | {g['f1']:.2f} | {cut} |")  # fmt: skip
    return "\n".join(lines) + "\n"
