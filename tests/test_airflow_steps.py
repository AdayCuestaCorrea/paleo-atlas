"""The Airflow DAGs run the same commands as GitHub Actions (ALCANCE.md §7, Fase 2).

Reads .github/workflows/pipeline.yml and airflow/dags/paleo_steps.py (plain Python,
no Airflow needed) and compares the `paleo` commands one by one, in order.
"""

import importlib.util
import re
import shlex
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
# Where or how a command runs, not what it does: each orchestrator sets its own.
ORCHESTRATOR_OPTIONS = {"--trigger", "--provider", "--out", "--jobs", "--site", "--output"}


def load_steps():
    spec = importlib.util.spec_from_file_location(
        "paleo_steps", ROOT / "airflow" / "dags" / "paleo_steps.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up
    spec.loader.exec_module(module)
    return module


def normalize(command: str) -> str:
    words, skip = [], False
    for word in shlex.split(command):
        if skip:
            skip = False
        elif word in ORCHESTRATOR_OPTIONS:
            skip = True
        else:
            words.append(word)
    return " ".join(words)


def actions_commands() -> list[str]:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "pipeline.yml").read_text())
    found = []
    for step in workflow["jobs"]["update"]["steps"]:
        for match in re.finditer(r"uv run paleo ([^\n|&;]*)", step.get("run", "")):
            found.append(normalize(match.group(1)))
    return found


def ci_fixture_commands() -> list[str]:
    """`uv run` commands of the CI test job after the unit tests (the fixture run)."""
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    names = [s.get("name") for s in workflow["jobs"]["test"]["steps"]]
    found = []
    for step in workflow["jobs"]["test"]["steps"][names.index("Unit tests") + 1 :]:
        found += [normalize(m) for m in re.findall(r"uv run ([^\n|&;]*)", step.get("run", ""))]
    return found


def test_ci_parity_dag_runs_the_fixture_job_of_ci():
    steps = load_steps()
    assert [normalize(c) for _, _, c in steps.CI_FIXTURE] == ci_fixture_commands()


def test_daily_dag_runs_the_commands_of_the_actions_workflow_in_order():
    steps = load_steps()
    expected = [c for c in actions_commands() if c not in steps.ACTIONS_ONLY]
    assert [normalize(c) for c in steps.commands(steps.DAILY)] == expected


def test_every_actions_only_command_exists_in_the_workflow():
    steps = load_steps()
    assert set(steps.ACTIONS_ONLY) <= set(actions_commands())


def test_normalize_drops_orchestrator_options_only():
    assert normalize('report start --trigger "$trigger" --changed') == "report start --changed"
    assert normalize("facts --provider groq") == "facts"
    assert normalize("site --check --out /x") == "site --check"
