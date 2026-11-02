"""Airflow vs GitHub Actions: same input, same output (ALCANCE.md §7, Fase 2).

Triggers the `paleo_ci_parity` DAG in the local Airflow (airflow/docker-compose.yaml),
waits for it, downloads the fingerprint that the CI job uploaded for the same commit
and compares both, table by table and file by file:

    uv run python scripts/parity.py

Exits 0 when Airflow and Actions produced exactly the same warehouse and website.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fingerprint import compare

API = "http://127.0.0.1:8080"
DAG = "paleo_ci_parity"
WORK = Path(__file__).resolve().parents[1] / "airflow" / "work"


def airflow() -> httpx.Client:
    token = httpx.get(f"{API}/auth/token").json()["access_token"]  # local, all admins
    return httpx.Client(base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=30)


def run_dag(client: httpx.Client) -> str:
    client.patch(f"/api/v2/dags/{DAG}", json={"is_paused": False}).raise_for_status()
    try:
        run = client.post(f"/api/v2/dags/{DAG}/dagRuns", json={"logical_date": None})
        run.raise_for_status()
        run_id = run.json()["dag_run_id"]
        print(f"Triggered {DAG}: {run_id}")
        while True:
            state = client.get(f"/api/v2/dags/{DAG}/dagRuns/{quote(run_id)}").json()["state"]
            if state in ("success", "failed"):
                return state
            time.sleep(5)
    finally:
        client.patch(f"/api/v2/dags/{DAG}", json={"is_paused": True})


def ci_fingerprint(commit: str, folder: Path) -> dict:
    runs = json.loads(
        subprocess.run(
            ["gh", "run", "list", "--workflow", "ci.yml", "--commit", commit,
             "--status", "success", "--json", "databaseId", "--limit", "1"],
            check=True, capture_output=True, text=True,
        ).stdout
    )  # fmt: skip
    if not runs:
        sys.exit(f"No successful CI run for {commit[:7]} yet: push it and wait for CI.")
    subprocess.run(
        ["gh", "run", "download", str(runs[0]["databaseId"]), "-n", "fingerprint", "-D",
         str(folder)],
        check=True,
    )  # fmt: skip
    return json.loads((folder / "fingerprint.json").read_text(encoding="utf-8"))


def main() -> int:
    state = run_dag(airflow())
    if state != "success":
        print(f"{DAG} ended {state}: see the task logs in the Airflow UI.")
        return 1
    local = json.loads((WORK / "ci-fingerprint.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        remote = ci_fingerprint(local["commit"], Path(tmp))
    diffs = compare(local, remote)
    for line in diffs[:50]:
        print(line)
    print(
        f"Airflow vs Actions at {local['commit'][:7]}: {len(local['tables'])} tables and "
        f"{len(local['site_files'])} site files, {len(diffs)} differences"
    )
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
