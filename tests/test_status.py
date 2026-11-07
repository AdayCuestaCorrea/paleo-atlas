"""The data status page (status.py and its template)."""

import datetime as dt
import re

import pytest

from paleo.site import status


def run(start, minutes=1, trigger="schedule", state="ok", changed=True, **extra):
    started = dt.datetime.fromisoformat(start).replace(tzinfo=dt.UTC)
    finished = started + dt.timedelta(minutes=minutes)
    return {"started_at": started.isoformat(), "finished_at": finished.isoformat(),
            "trigger": trigger, "status": state, "changed": changed, **extra}  # fmt: skip


STEPS = [
    {"name": "Set up job", "seconds": 5},
    {"name": "Check out the data branch", "seconds": 3},
    {"name": "Ingest and parse", "seconds": 20},
    {"name": "Facts and texts for pending species (Groq)", "seconds": 4},
    {"name": "dbt build", "seconds": 15},
    {"name": "Build the website", "seconds": 6, "partial": True},
]


def test_steps_are_grouped_once_and_the_rest_is_not_broken_down():
    view = status.runs_view([run("2026-11-05T14:00:00", steps=STEPS)])
    (r,) = view
    groups = {g["key"]: g["seconds"] for g in r["groups"]}
    assert groups == {"prep": 8, "ingest": 20, "groq": 4, "dbt": 15, "site": 6}
    assert [g["partial"] for g in r["groups"] if g["key"] == "site"] == [True]
    assert r["seconds"] == 60 and r["unsplit"] == 60 - 53
    # a run without steps is all "not broken down"
    (bare,) = status.runs_view([run("2026-11-05T14:00:00")])
    assert bare["groups"] == [] and bare["unsplit"] == bare["seconds"] == 60


def test_the_days_source_changes_go_only_on_its_latest_run():
    day = {"sources_changed": {"pbdb/taxa": 2}, "wikipedia_new_revisions": ["2026_in_x"]}
    view = status.runs_view([
        run("2026-11-07T11:00:00", **day),
        run("2026-11-07T13:00:00", **day, changes_since_previous={"events": 4, "studies": 0}),
        run("2026-11-06T14:00:00", trigger="manual", **day),
    ])  # fmt: skip
    assert [r["started_at"].hour for r in view] == [13, 11, 14]  # newest first
    assert view[0]["sources"] == {"pbdb/taxa": 2} and view[0]["wikipedia"] == 1
    assert view[1]["sources"] == {} and view[1]["wikipedia"] == 0
    assert view[2]["sources"] == {"pbdb/taxa": 2}  # another day
    assert view[0]["diffs"] == [("events", 4)]  # zero changes are left out


def test_runs_still_running_are_left_out():
    running = {**run("2026-11-07T14:00:00"), "status": "running", "finished_at": None}
    assert status.runs_view([running, run("2026-11-06T14:00:00")])[0]["started_at"].day == 6


def test_dbt_counts_of_a_run():
    dbt = {"counts": {"pass": 9, "warn": 2, "error": 1, "fail": 1}}
    (r,) = status.runs_view([run("2026-11-05T14:00:00", dbt=dbt)])
    assert (r["warnings"], r["errors"]) == (2, 2)


def test_calendar_marks_each_day():
    runs = [
        run("2026-11-05T14:00:00", changed=False),
        run("2026-11-06T14:00:00", changed=False),
        run("2026-11-06T18:00:00", changed=True),
        run("2026-11-07T14:00:00", state="failed"),
    ]
    cal = status.calendar(runs, dt.date(2026, 11, 8), days=5)
    assert [c["day"].day for c in cal] == [4, 5, 6, 7, 8]
    assert [c["state"] for c in cal] == ["none", "unchanged", "changed", "failed", "none"]
    assert cal[2]["runs"] == 2


def test_schedule_delay_counts_only_scheduled_runs():
    runs = [
        run("2026-11-05T14:25:00"),
        run("2026-11-06T13:23:00"),
        run("2026-11-06T09:00:00", trigger="manual"),
    ]
    assert status.schedule_delay(runs) == (7 * 60, 8 * 60 + 2)
    assert status.schedule_delay([run("2026-11-06T09:00:00", trigger="manual")]) is None


def test_texts_by_day_fill_the_days_without_pages():
    texts = {
        ("a", "en"): {"generated_at": dt.datetime(2026, 11, 1, 3)},
        ("a", "es"): {"generated_at": "2026-11-03T02:00:00"},
        ("b", "en"): {"generated_at": dt.datetime(2026, 11, 3, 4)},
        ("c", "en"): {"generated_at": None},
    }
    days = status.texts_by_day(texts)
    assert [(d["day"].day, d["en"], d["es"]) for d in days] == [(1, 1, 0), (2, 1, 0), (3, 2, 1)]
    assert status.texts_by_day({}) == []


def test_freshness_against_each_rhythm_and_the_overall_state():
    today = dt.date(2026, 11, 7)
    rows = [
        {"source": "a", "every_days": 7, "last_checked": dt.date(2026, 11, 1)},
        {"source": "b", "every_days": 1, "last_checked": dt.date(2026, 11, 5)},
        {"source": "c", "every_days": 31, "last_checked": None},
    ]
    fresh = status.freshness(rows, today)
    assert [(s["age"], s["fresh"]) for s in fresh] == [(6, True), (2, False), (None, False)]
    ok = {"status": "ok"}
    tests = {"data": {"pass": 5, "warn": 2}, "unit": {"pass": 3}}
    assert status.overall(ok, tests, fresh[:1])
    assert not status.overall(ok, tests, fresh)  # a late source
    assert not status.overall(ok, {"data": {"fail": 1}}, fresh[:1])
    assert not status.overall({"status": "failed"}, tests, fresh[:1])
    assert not status.overall(None, tests, [])


def test_charts_keep_their_labels_apart_and_show_the_latest_runs():
    view = status.runs_view([run(f"2026-11-{d:02d}T14:00:00", minutes=d) for d in range(1, 16)])
    bars = status.bar_chart(view, last=10)
    assert len(bars["bars"]) == 10
    assert bars["bars"][-1]["run"]["started_at"].day == 15  # newest on the right
    tallest = max(sum(s["h"] for s in b["segments"]) for b in bars["bars"])
    assert tallest <= bars["height"]
    points = [{"day": dt.date(2026, 10, 1) + dt.timedelta(days=i), "en": i, "es": i}
              for i in range(30)]  # fmt: skip
    line = status.line_chart(points)
    a, b = (ln["label_y"] for ln in line["lines"])
    assert abs(a - b) >= 14  # same values, labels still apart
    assert len(line["days"]) <= 7 and line["days"][-1]["day"] == points[-1]["day"]


# ----------------------------------------------------------------- the page


@pytest.fixture
def builder(monkeypatch):
    from paleo import report
    from paleo.site.build import SiteBuilder
    from paleo.site.data import SiteData

    monkeypatch.setattr(report, "dbt_issues", lambda path: None)
    dbt = {
        "counts": {"pass": 10, "warn": 2},
        "tests": {"data": {"pass": 8, "warn": 2}, "unit": {"pass": 2}},
        "issues": [
            {"status": "warn", "node": "assert_pbdb_lag_warning", "failures": 3},
            {"status": "warn", "node": "some_new_check", "failures": 1},
        ],
    }
    taxa = [{"taxon_name": "Tyrannosaurus rex", "taxon_key": "t-rex", "page_type": "new",
             "pbdb_has_taxon": True, "image_source": "phylopic",
             "image_level": "clade"}]  # fmt: skip
    data = SiteData(
        taxa, {}, {}, {}, {}, dt.date(2026, 11, 7),
        runs=[run("2026-11-06T14:00:00", steps=STEPS, dbt=dbt,
                  sources_changed={"pbdb/taxa": 1, "brand_new/kind": 2}),
              run("2026-11-05T14:00:00", trigger="manual")],
        freshness=[{"source": "pbdb_taxa", "family": "pbdb", "sort": 1, "every_days": 7,
                    "name_es": "PBDB · nombres", "name_en": "PBDB · names",
                    "cadence_es": "semanal", "cadence_en": "weekly",
                    "last_checked": dt.date(2026, 11, 6), "records": 5}],
    )  # fmt: skip
    return SiteBuilder(data, base="/pa")


def render(b, lang):
    page = next(p for p in b.pages() if p.kind == "status" and p.lang == lang)
    return b.render(page)


def test_status_page_in_both_languages_has_the_same_structure(builder):
    es, en = render(builder, "es"), render(builder, "en")

    def shape(html):
        return re.findall(r"<(h2|svg|table|tr|li|rect)\b", html)

    assert shape(es) == shape(en)
    assert "Estado de los datos" in es and "Data status" in en
    assert 'href="/pa/en/status.html"' in es


def test_status_page_explains_known_warnings_and_names_unknown_ones(builder):
    es = render(builder, "es")
    assert "aún no están en PBDB: 3" in es
    assert "<code>some_new_check</code>" in es
    assert "brand_new/kind" in es  # an unknown source is named, not hidden
