"""Resolve the merge conflicts of the data branch (data-fase-3 into data).

Both branches store raw snapshots with paleo.store.RawStore and the same code paths,
so their conflicts are predictable:

* ``_checked.json`` (when each key was last checked): keep every key, with the most
  recent date of the two sides.
* A version or revision file added on both sides the same day: identical except for
  ``fetched_at`` (or other volatile fields), so either side is right; ours is kept.
  If the content really differs, the file is left in conflict for a person.
* ``runs/<day>.json`` (arrays of run records): the union, ordered by start time.

Run it inside the data checkout, in the middle of the merge:

    git merge origin/data-fase-3          # stops with conflicts
    uv run python ../scripts/merge_data.py
    git commit
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

VOLATILE = {"fetched_at", "elapsed_time"}


def merge_checked(ours: dict[str, str], theirs: dict[str, str]) -> dict[str, str]:
    """Every key, with its most recent check date (ISO dates sort as text)."""
    keys = set(ours) | set(theirs)
    return {k: max(d for d in (ours.get(k), theirs.get(k)) if d) for k in sorted(keys)}


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def same_snapshot(ours: Any, theirs: Any) -> bool:
    """True when two stored snapshots differ only in volatile fields."""
    return _strip(ours) == _strip(theirs)


def merge_runs(ours: list[dict[str, Any]], theirs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for run in ours + theirs:
        seen.setdefault(run.get("started_at", json.dumps(run, sort_keys=True)), run)
    return sorted(seen.values(), key=lambda r: r.get("started_at") or "")


def _side(path: str, stage: int) -> Any:
    out = subprocess.run(["git", "show", f":{stage}:{path}"], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None


def resolve(path: str) -> bool:
    """Resolve one conflicted file; False when it needs a person."""
    ours, theirs = _side(path, 2), _side(path, 3)
    name = Path(path).name
    if ours is None or theirs is None:
        return False
    if name == "_checked.json":
        text = json.dumps(merge_checked(ours, theirs), indent=1, ensure_ascii=False) + "\n"
    elif path.startswith("runs/") and isinstance(ours, list):
        text = json.dumps(merge_runs(ours, theirs), indent=1, ensure_ascii=False) + "\n"
    elif same_snapshot(ours, theirs):
        subprocess.run(["git", "checkout", "--ours", "--", path], check=True)
        subprocess.run(["git", "add", "--", path], check=True)
        return True
    else:
        return False
    Path(path).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "--", path], check=True)
    return True


def main() -> int:
    command = ["git", "diff", "--name-only", "--diff-filter=U"]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    conflicted = [p for p in out.stdout.splitlines() if p]
    left = [p for p in conflicted if not p.endswith(".json") or not resolve(p)]
    print(f"{len(conflicted) - len(left)} of {len(conflicted)} conflicts resolved")
    for path in left:
        print(f"  needs a person: {path}")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
