"""The DAGs load in Airflow 3.3 and have the expected shape (CI job `dags`)."""

from pathlib import Path

import pytest
from airflow.dag_processing.dagbag import DagBag

DAGS = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(str(DAGS))


def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_the_four_dags_exist_and_start_paused_without_catchup(dagbag):
    assert set(dagbag.dags) == {"paleo_daily", "paleo_weekly", "paleo_monthly", "paleo_ci_parity"}
    for dag in dagbag.dags.values():
        assert dag.catchup is False and dag.max_active_runs == 1


def test_daily_branches_on_change_detection(dagbag):
    dag = dagbag.dags["paleo_daily"]
    detect = dag.get_task("detect")
    branches = {t.task_id for t in detect.downstream_list} - {"fail_if_any_failed"}
    assert branches == {"ingest_wikipedia", "parse_unchanged"}
    assert dag.get_task("report_finish").trigger_rule == "all_done"
    assert dag.get_task("commit_data").trigger_rule == "all_done"
    assert dag.get_task("ingest_pbdb").retries == 2
    assert "git push" not in dag.get_task("commit_data").bash_command
    # A failed task fails the run, although the report and the commit still run.
    watcher = dag.get_task("fail_if_any_failed")
    assert watcher.trigger_rule == "one_failed"
    assert {t.task_id for t in watcher.upstream_list} == {t.task_id for t in dag.tasks} - {
        "fail_if_any_failed"
    }


def test_narrative_is_skipped_unless_asked_for(dagbag):
    facts = dagbag.dags["paleo_daily"].get_task("facts")
    assert "exit 99" in facts.bash_command and "--soft" in facts.bash_command
    assert dagbag.dags["paleo_daily"].params["narrative"] == "none"
