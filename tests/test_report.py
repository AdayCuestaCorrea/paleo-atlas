"""Run log and run report (paleo report start / finish)."""

import datetime as dt
import json

import duckdb
import pytest

from paleo import report

T0 = dt.datetime(2026, 11, 2, 6, 23, tzinfo=dt.UTC)


def make_warehouse(path, new_taxa=2, verified_es=1):
    con = duckdb.connect(str(path))
    con.execute(
        "create table dim_taxon as select * from (values "
        "('a', 'new', true, 'commons', 'taxon'), ('b', 'new', false, 'phylopic', 'clade'), "
        "('c', 'known', true, null, null)) t(taxon_key, page_type, pbdb_has_taxon, "
        "image_source, image_level)"
    )
    if new_taxa > 2:
        con.execute("insert into dim_taxon values ('d', 'new', false, null, null)")
    con.execute(
        "create table fct_taxon_event as select * from (values ('a', 'description'), "
        "('c', 'new_study')) t(taxon_key, event_type)"
    )
    con.execute("create table dim_study as select 1 as study_id")
    con.execute(
        "create table fct_taxon_text as select * from (values ('a', 'en', 'verified'), "
        "('a', 'es', 'verified')) t(taxon_key, lang, text_status)"
    )
    con.execute("create table fct_taxon_image as select 'a' as taxon_key")
    con.close()


def test_a_run_is_started_finished_and_compared_with_the_previous_one(tmp_path):
    data = tmp_path / "data"
    store = data / "raw" / "pbdb" / "taxa" / "spinosaurus"
    store.mkdir(parents=True)
    (store / "2026-11-02.json").write_text("{}")
    (data / "raw" / "wikipedia" / "2026-in-archosaur-paleontology").mkdir(parents=True)
    (data / "raw" / "wikipedia" / "2026-in-archosaur-paleontology" / "10.json").write_text("{}")
    target = tmp_path / "run_results.json"
    target.write_text(json.dumps({"results": [
        {"unique_id": "test.paleo.assert_pbdb_lag_warning", "status": "warn", "failures": 3},
        {"unique_id": "model.paleo.dim_taxon", "status": "success", "failures": None},
    ]}))  # fmt: skip
    warehouse = tmp_path / "w.duckdb"
    make_warehouse(warehouse)

    report.start_run(data, trigger="schedule", changed=True, now=T0 - dt.timedelta(days=1))
    report.finish_run(data, warehouse=warehouse, run_results=target, now=T0)
    assert not report.ran_today(data, today=T0.date())

    (data / "raw" / "wikipedia" / "2026-in-archosaur-paleontology" / "11.json").write_text("{}")
    warehouse.unlink()
    make_warehouse(warehouse, new_taxa=3)
    report.start_run(data, trigger="backup", changed=True, now=T0)
    run = report.finish_run(data, warehouse=warehouse, run_results=target, now=T0)

    assert report.ran_today(data, today=T0.date())
    assert run["status"] == "ok"  # a dbt warning is not a failure
    assert run["sources_changed"] == {"pbdb/taxa": 1}
    assert run["wikipedia_new_revisions"] == ["2026-in-archosaur-paleontology"]
    assert run["summary"]["totals"]["taxa_new"] == 3
    assert run["summary"]["totals"]["texts_pending"] == 2
    assert run["summary"]["pbdb"]["new"] == {"matched": 1, "total": 3}
    assert run["changes_since_previous"] == {"taxa_new": 1, "texts_pending": 1}
    assert run["dbt"]["issues"] == [
        {"status": "warn", "node": "assert_pbdb_lag_warning", "failures": 3}
    ]
    text = report.markdown(run)
    assert "3 (+1)" in text and "new 33 %" in text and "assert_pbdb_lag_warning" in text
    days = sorted(p.name for p in report.runs_dir(data).glob("*.json"))
    assert days == ["2026-11-01.json", "2026-11-02.json"]


def test_failed_steps_mark_the_run_and_skipped_ones_are_left_out(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"jobs": [{"name": "update", "steps": [
        {"name": "Ingest", "conclusion": "success",
         "started_at": "2026-11-02T06:23:00Z", "completed_at": "2026-11-02T06:24:30Z"},
        {"name": "dbt build", "conclusion": "failure",
         "started_at": "2026-11-02T06:24:30Z", "completed_at": "2026-11-02T06:24:40Z"},
        {"name": "Build the website", "conclusion": "skipped",
         "started_at": "2026-11-02T06:24:40Z", "completed_at": "2026-11-02T06:24:40Z"},
        {"name": "Run report", "conclusion": None, "started_at": "2026-11-02T06:24:41Z",
         "completed_at": None},
    ]}]}))  # fmt: skip
    data = tmp_path / "data"
    report.start_run(data, trigger="manual", changed=False, now=T0)
    run = report.finish_run(
        data, warehouse=tmp_path / "none.duckdb", run_results=tmp_path / "none.json", jobs=jobs
    )
    assert run["status"] == "failed" and run["summary"] is None
    assert [(s["name"], s["seconds"]) for s in run["steps"]] == [("Ingest", 90), ("dbt build", 10)]
    assert not report.ran_today(data, today=T0.date())


def test_finish_needs_a_started_run_and_triggers_are_checked(tmp_path):
    with pytest.raises(RuntimeError):
        report.finish_run(tmp_path, warehouse=tmp_path / "w", run_results=tmp_path / "r")
    with pytest.raises(ValueError):
        report.start_run(tmp_path, trigger="cron", changed=True)


def test_a_step_the_api_still_shows_running_is_kept_as_partial(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"jobs": [{"name": "update", "steps": [
        {"name": "dbt build", "conclusion": "success",
         "started_at": "2026-11-02T06:24:00Z", "completed_at": "2026-11-02T06:24:20Z"},
        {"name": "Build the website", "conclusion": None,
         "started_at": "2026-11-02T06:24:20Z", "completed_at": None},
        {"name": "Run report", "conclusion": None,
         "started_at": "2026-11-02T06:26:20Z", "completed_at": None},
    ]}]}))  # fmt: skip
    now = dt.datetime(2026, 11, 2, 6, 26, 30, tzinfo=dt.UTC)
    steps = report.step_results(jobs, now=now)
    assert steps[1] == {"name": "Build the website", "conclusion": "in_progress", "seconds": 130,
                        "partial": True}  # fmt: skip
    assert [s["name"] for s in steps] == ["dbt build", "Build the website"]  # not the report


def test_dbt_counts_tell_data_tests_from_unit_tests(tmp_path):
    results = tmp_path / "run_results.json"
    results.write_text(json.dumps({"results": [
        {"unique_id": "model.p.m", "status": "success"},
        {"unique_id": "test.p.not_null_x.abc1234567", "status": "pass"},
        {"unique_id": "test.p.lag.abc1234567", "status": "warn", "failures": 3},
        {"unique_id": "unit_test.p.m.u1", "status": "pass"},
    ]}))  # fmt: skip
    out = report.dbt_issues(results)
    assert out["tests"] == {"data": {"pass": 1, "warn": 1}, "unit": {"pass": 1}}
    assert out["issues"] == [{"status": "warn", "node": "lag", "failures": 3}]
