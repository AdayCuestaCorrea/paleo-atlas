"""The data-branch merge helper (scripts/merge_data.py): predictable conflicts of the
RawStore snapshots are resolved without losing a check date or a run."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "merge_data", Path(__file__).parents[1] / "scripts" / "merge_data.py"
)
merge_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_data)


def test_check_dates_keep_every_key_with_the_latest_date():
    ours = {"Acanthodes": "2026-11-03", "Accipitridae": "2026-11-01"}
    theirs = {"Acanthodes": "2026-11-02", "Zygorhiza": "2026-11-02"}
    assert merge_data.merge_checked(ours, theirs) == {
        "Acanthodes": "2026-11-03",
        "Accipitridae": "2026-11-01",
        "Zygorhiza": "2026-11-02",
    }


def test_snapshots_that_differ_only_in_volatile_fields_are_the_same():
    a = {"key": "X", "fetched_at": "2026-11-03T10:00", "payload": {"elapsed_time": 0.1, "n": 1}}
    b = {"key": "X", "fetched_at": "2026-11-03T15:50", "payload": {"elapsed_time": 0.3, "n": 1}}
    assert merge_data.same_snapshot(a, b)
    assert not merge_data.same_snapshot(a, {**b, "payload": {"n": 2}})


def test_runs_of_both_sides_are_kept_once_in_order():
    ours = [{"started_at": "2026-11-03T06:23:00Z", "trigger": "schedule"}]
    theirs = [{"started_at": "2026-11-03T01:00:00Z", "trigger": "manual"}, ours[0]]
    merged = merge_data.merge_runs(ours, theirs)
    assert [r["trigger"] for r in merged] == ["manual", "schedule"]


def test_news_labels_and_pairs_are_joined_by_key():
    ours = [
        {"key": "a", "category": "research", "classified_at": "2026-11-07T16:00"},
        {"key": "b", "category": "noise", "classified_at": "2026-11-07T16:00"},
    ]
    theirs = [{"key": "b", "category": "culture", "classified_at": "2026-11-08T14:00"},
              {"key": "c", "category": "noise", "classified_at": "2026-11-08T14:00"}]  # fmt: skip
    merged = merge_data.merge_labels(ours, theirs)
    assert [(r["key"], r["category"]) for r in merged] == [
        ("a", "research"), ("b", "culture"), ("c", "noise")
    ]  # fmt: skip
    pairs = merge_data.merge_pairs(
        [{"key_a": "a", "key_b": "b", "same": True}],
        [{"key_a": "a", "key_b": "b", "same": False}, {"key_a": "c", "key_b": "d", "same": True}],
    )
    assert [(p["key_a"], p["key_b"], p["same"]) for p in pairs] == [
        ("a", "b", True), ("c", "d", True)
    ]  # fmt: skip


def test_news_groups_are_rebuilt_from_the_merged_pairs():
    row = {"method": "groq/openai/gpt-oss-120b", "threshold": None}
    ours = [{"key": k, "group": k, **row} for k in ("a", "b")]
    theirs = [{"key": k, "group": "c", **row} for k in ("c", "d")]
    pairs = [{"key_a": "a", "key_b": "b", "same": False},
             {"key_a": "b", "key_b": "c", "same": True},
             {"key_a": "c", "key_b": "d", "same": True}]  # fmt: skip
    groups = {r["key"]: r["group"] for r in merge_data.merge_groups(ours, theirs, pairs)}
    assert groups == {"a": "a", "b": "b", "c": "b", "d": "b"}
