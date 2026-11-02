"""Paleo Atlas DAGs (ALCANCE.md §7, Fase 2): the GitHub Actions pipeline, in Airflow.

* ``paleo_daily``   — Tuesday to Sunday: change detection, then the full pipeline only
  if something changed (otherwise the warehouse and the site are just rebuilt).
* ``paleo_weekly``  — Mondays: everything, without change detection (weekly recap).
* ``paleo_monthly`` — every source queried again, then GBIF reconciled in Spark.
* ``paleo_ci_parity`` — the CI fixture job, to prove both produce the same output.

Every task calls a `paleo` command from paleo_steps.py (decision D4: no pipeline logic
here). Unlike Actions, nothing is published: the DAGs work on airflow/work/data, a clone
of the `data` branch, and commit there without pushing. All DAGs start paused.
"""

from __future__ import annotations

import datetime as dt
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param, TriggerRule, chain, task

sys.path.insert(0, str(Path(__file__).parent))  # paleo_steps.py, next to this file
from paleo_steps import CI_FIXTURE, CI_FIXTURE_AS_OF, DAILY, MONTHLY, Step, by_id

PALEO_HOME = "/opt/paleo"
PALEO = f"{PALEO_HOME}/.venv/bin/paleo"
STEP = f"python {PALEO_HOME}/airflow/bin/step.py"
WORK = "/opt/airflow/work"
DATA = f"{WORK}/data"
SITE_OUT = f"{WORK}/site"
JOBS = WORK + "/jobs/{{ dag.dag_id }}/{{ run_id | replace(':', '-') | replace('+', '-') }}.json"
# What `uv run` does in Actions: the project's virtualenv first on PATH (`paleo build`
# calls dbt from there).
VENV = {
    "VIRTUAL_ENV": f"{PALEO_HOME}/.venv",
    "PATH": f"{PALEO_HOME}/.venv/bin:" + os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
}
TASK_ENV = {**VENV, "PALEO_JOBS": JOBS}

# Where and how Airflow runs a command (not part of the contract with Actions).
EXTRA_OPTIONS = {
    "report start": "--trigger local",
    "report finish": f"--jobs {JOBS}",
    "site": f"--out {SITE_OUT}",
    "facts": "--provider {{ params.narrative }}",
    "write": "--provider {{ params.narrative }}",
    "titles": "--provider {{ params.narrative }}",
}

NETWORK_RETRIES = {
    "retries": 2,
    "retry_delay": dt.timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": dt.timedelta(minutes=10),
}

COMMON = {
    "start_date": pendulum.datetime(2026, 11, 2, tz="UTC"),
    "catchup": False,
    "max_active_runs": 1,  # like `concurrency: pipeline` in Actions
    "dagrun_timeout": dt.timedelta(minutes=90),  # like `timeout-minutes: 90`
    "tags": ["paleo-atlas"],
}

NARRATIVE = Param(
    "none",
    enum=["none", "ollama"],
    description="LLM for the texts of pending species: none (skip, the default) or the "
    "host's Ollama. Never Groq: its free daily quota belongs to GitHub Actions.",
)


def paleo(command: str) -> str:
    """Full command line for a `paleo` subcommand, with Airflow's own options."""
    for prefix, extra in EXTRA_OPTIONS.items():
        if command == prefix or command.startswith(prefix + " "):
            return f"{PALEO} {command} {extra}"
    return f"{PALEO} {command}"


def step_task(step: Step, **kwargs) -> BashOperator:
    (command,) = step.commands
    line = f"{STEP} {step.task_id}{' --soft' if step.narrative else ''} -- {paleo(command)}"
    if step.narrative:  # continue-on-error in Actions; skipped unless asked for
        line = (
            '[ "{{ params.narrative }}" = none ] && { echo "narrative=none: skipped"; exit 99; }\n'
            + line
        )
    options = NETWORK_RETRIES if step.network else {}
    return BashOperator(
        task_id=step.task_id,
        bash_command=line,
        env=TASK_ENV,
        append_env=True,
        **options,
        **kwargs,
    )


def checkout_task() -> BashOperator:
    """Like actions/checkout of the data branch: the latest published data, nothing else.

    The branch is the one the clone follows (``data``, or the data branch of a phase in
    progress: init-work.sh BRANCH). ``cache/`` survives the clean: it is local and never
    versioned (the GBIF download, abstracts), as a cache restored by Actions would be."""
    script = f"""
set -euo pipefail
if [ ! -d {DATA}/.git ]; then
  echo "No clone of the data branch in {DATA}: run airflow/bin/init-work.sh first." >&2
  exit 1
fi
cd {DATA}
branch=$(git rev-parse --abbrev-ref HEAD)
{STEP} checkout_data -- bash -c "git fetch --quiet origin $branch \\
  && git reset --quiet --hard origin/$branch && git clean -qfdx -e /cache/"
git log -1 --format="$branch branch at %h: %s"
"""
    return BashOperator(
        task_id="checkout_data",
        bash_command=script,
        env=TASK_ENV,
        append_env=True,
        **NETWORK_RETRIES,
    )


def commit_task() -> BashOperator:
    """The commit step of Actions with the same safeguard, but never pushed."""
    script = f"""
set -euo pipefail
cd {DATA}
git add -A
if git diff --cached --name-only | grep -E '^(cache|interim)/|\\.duckdb'; then
  echo "private or local files staged; refusing to commit" >&2
  exit 1
fi
if git diff --cached --quiet; then
  echo "No data changes."
  exit 0
fi
message="Data update $(date -u +%F)"
if [ -z "$(git diff --cached --name-only | grep -v '^runs/')" ]; then
  message="Run log $(date -u +%F)"
fi
git -c user.name="Paleo Atlas (local Airflow)" -c user.email="airflow@localhost" \\
  commit -q -m "$message (local Airflow, not pushed)"
# sed reads everything: head would close the pipe early and fail with SIGPIPE (141)
git show --stat --format='%h %s' HEAD | sed -n '1,40p'
"""
    return BashOperator(
        task_id="commit_data", bash_command=script, trigger_rule=TriggerRule.ALL_DONE
    )


def recorder():
    """airflow/bin/step.py, which records steps in the format `paleo report` reads."""
    if f"{PALEO_HOME}/airflow/bin" not in sys.path:
        sys.path.insert(0, f"{PALEO_HOME}/airflow/bin")
    import step

    return step


def watcher_task():
    """Fail the run if any task failed, as the Actions job does.

    Airflow sets a run's state from its last tasks, and the report and the commit run
    even after a failure (``all_done``, like ``if: always()``): without this task a run
    with a failed dbt build would end green.
    """

    @task(task_id="fail_if_any_failed", trigger_rule=TriggerRule.ONE_FAILED, retries=0)
    def _watcher() -> None:
        raise RuntimeError("a task failed in this run: see the failed tasks above")

    return _watcher()


def detect_task(force: bool):
    """ "Anything new?" of Actions: `paleo check`, then `paleo report start`.

    `paleo check` exits 0 (changed), 1 (nothing new) or 2 (the check failed, so
    everything runs and the error surfaces). Mondays (``force``) skip the check.
    """
    detect = by_id(DAILY)["detect"]
    check, start_changed, start_unchanged = detect.commands

    @task.branch(task_id="detect")
    def _detect(**context) -> str:
        rec = recorder()
        run_id = context["run_id"].replace(":", "-").replace("+", "-")
        jobs = f"{WORK}/jobs/{context['dag'].dag_id}/{run_id}.json"
        env = {**os.environ, **VENV}
        started = rec.now()
        code = 0
        if not force:
            code = subprocess.run(shlex.split(paleo(check)), env=env, check=False).returncode
        changed = code != 1
        start = paleo(start_changed if changed else start_unchanged)
        ok = subprocess.run(shlex.split(start), env=env, check=False).returncode == 0
        outcome = "success" if ok else "failure"
        rec.record(Path(jobs), {
            "name": "detect", "status": "completed", "conclusion": outcome,
            "outcome": outcome, "started_at": started, "completed_at": rec.now(),
        })  # fmt: skip
        if not ok:
            raise RuntimeError("paleo report start failed")
        if not changed:
            print("Nothing changed: only the run log, the warehouse and the site are refreshed.")
        return "ingest_wikipedia" if changed else "parse_unchanged"

    return _detect()


def pipeline_dag(dag_id: str, schedule: str, *, force: bool, doc: str) -> DAG:
    with DAG(
        dag_id,
        schedule=schedule,
        params={"narrative": NARRATIVE},
        doc_md=doc,
        **COMMON,
    ) as dag:
        steps = by_id(DAILY)
        t = {sid: step_task(s) for sid, s in steps.items() if sid != "detect"}
        checkout = checkout_task()
        detect = detect_task(force)
        # The build needs ingest done (narrative optional) or interim/ rebuilt.
        t["dbt_build"].trigger_rule = TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
        t["report_finish"].trigger_rule = TriggerRule.ALL_DONE  # if: always()
        commit = commit_task()

        chain(checkout, detect)
        detect >> [t["ingest_wikipedia"], t["parse_unchanged"]]
        chain(*(t[s] for s in (
            "ingest_wikipedia", "parse_wikipedia", "ingest_pbdb", "ingest_studies",
            "ingest_images", "ingest_articles", "facts", "write", "titles",
        )))  # fmt: skip
        [t["ingest_articles"], t["titles"], t["parse_unchanged"]] >> t["dbt_build"]
        chain(t["dbt_build"], t["site"], t["site_check"], t["report_finish"], commit)
        list(dag.tasks) >> watcher_task()
    return dag


paleo_daily = pipeline_dag(
    "paleo_daily",
    "23 6 * * 2-7",
    force=False,
    doc="Daily run (Tuesday to Sunday, 06:23 UTC like Actions): change detection, then "
    "the full pipeline only if a source changed.",
)

paleo_weekly = pipeline_dag(
    "paleo_weekly",
    "23 6 * * 1",
    force=True,
    doc="Monday run: everything, without change detection; `paleo site` writes the weekly recap.",
)


with DAG(
    "paleo_monthly",
    schedule="23 7 1 * *",
    doc_md="Monthly run: every source queried again, ignoring freshness (retractions, "
    "corrections, DOAJ changes), then the GBIF download of fossil specimens (GBIF can take "
    "hours to prepare it) reconciled with the PBDB genera in Spark, and the site rebuilt.",
    **{**COMMON, "dagrun_timeout": dt.timedelta(hours=10)},
) as paleo_monthly:
    m = {sid: step_task(s) for sid, s in by_id(MONTHLY).items()}
    m["gbif_extract"].execution_timeout = dt.timedelta(hours=8)
    m["report_finish"].trigger_rule = TriggerRule.ALL_DONE
    chain(
        checkout_task(), m["report_start"], m["parse_wikipedia"], m["refresh_pbdb"],
        m["refresh_studies"], m["refresh_images"], m["catalog_build"], m["gbif_extract"],
        m["gbif_reconcile"], m["dbt_build"], m["site"], m["site_check"], m["report_finish"],
        commit_task(),
    )  # fmt: skip
    list(paleo_monthly.tasks) >> watcher_task()


with DAG(
    "paleo_ci_parity",
    schedule=None,
    doc_md="The fixture job of ci.yml (no network): seed the fixtures, parse, dbt build "
    f"with as_of={CI_FIXTURE_AS_OF}, build and check the site, then write the fingerprint "
    "that scripts/parity.py compares with the one uploaded by CI for the same commit.",
    **COMMON,
) as paleo_ci_parity:
    env = {**VENV, "PALEO_DATA_DIR": f"{WORK}/ci-data"}
    ci_site = f"{WORK}/ci-site"
    ci_extra = {
        "site": f"--out {ci_site}",
        "site_check": f"--out {ci_site}",
        "fingerprint": f"--site {ci_site} --output {WORK}/ci-fingerprint.json",
    }
    prepare = BashOperator(
        task_id="prepare",
        bash_command=f"rm -rf {WORK}/ci-data {ci_site} && mkdir -p {WORK}/ci-data",
    )
    tasks = [
        BashOperator(
            task_id=task_id,
            bash_command=f"cd {PALEO_HOME}/{cwd} && {command} {ci_extra.get(task_id, '')}",
            env=env,
            append_env=True,
        )
        for task_id, cwd, command in CI_FIXTURE
    ]
    chain(prepare, *tasks)
