"""Run one pipeline command and record it like a GitHub Actions step.

    python step.py NAME [--soft] -- COMMAND...

Appends (or replaces, after a retry) the step in $PALEO_JOBS, a JSON file with the
shape of GitHub's "list jobs for a workflow run" API, so `paleo report finish --jobs`
reads Airflow runs and Actions runs alike. ``--soft`` mirrors ``continue-on-error``:
a failure is recorded as the step's outcome, but the task still succeeds.
Exit code 99 (the task decided to skip itself) is passed through and not recorded.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

SKIP = 99


def now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def record(path: Path, step: dict) -> None:
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    jobs = doc.setdefault("jobs", [])
    job = next((j for j in jobs if j.get("name") == "update"), None)
    if job is None:
        job = {"name": "update", "steps": []}
        jobs.append(job)
    job["steps"] = [s for s in job["steps"] if s["name"] != step["name"]] + [step]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str]) -> int:
    if "--" not in argv or argv.index("--") == 0:
        print(__doc__, file=sys.stderr)
        return 2
    split = argv.index("--")
    name, *flags = argv[:split]
    command = argv[split + 1 :]
    started = now()
    code = subprocess.run(command, check=False).returncode
    if code == SKIP:
        return SKIP
    outcome = "success" if code == 0 else "failure"
    soft = "--soft" in flags
    step = {
        "name": name,
        "status": "completed",
        "conclusion": "success" if soft else outcome,
        "outcome": outcome,
        "started_at": started,
        "completed_at": now(),
    }
    if jobs := os.environ.get("PALEO_JOBS"):
        record(Path(jobs), step)
    if code and soft:
        print(f"{name} failed with exit code {code}; continuing (continue-on-error).")
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
