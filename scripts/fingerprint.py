"""Fingerprint of a pipeline run: what it produced, independent of where it ran.

One hash per warehouse table (its rows, sorted) and one per website file. CI writes
it for the fixture job and uploads it; the `paleo_ci_parity` DAG writes it for the
same job in Airflow, and scripts/parity.py compares both (ALCANCE.md §7, Fase 2):

    uv run python scripts/fingerprint.py --site site/_build --output fingerprint.json
    uv run python scripts/fingerprint.py --compare a.json b.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import duckdb

from paleo.config import get_paths, project_root


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def warehouse_hashes(warehouse: Path) -> dict[str, dict]:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        tables = [
            r[0]
            for r in con.execute(
                "select table_name from information_schema.tables "
                "where table_schema = 'main' order by 1"
            ).fetchall()
        ]
        out = {}
        for table in tables:
            rows = con.execute(f'select * from main."{table}"').fetchall()
            lines = sorted(json.dumps(row, default=str, ensure_ascii=False) for row in rows)
            out[table] = {"rows": len(rows), "sha256": _sha("\n".join(lines).encode())}
        return out
    finally:
        con.close()


def site_hashes(site: Path) -> dict[str, str]:
    return {
        str(p.relative_to(site)): _sha(p.read_bytes())
        for p in sorted(site.rglob("*"))
        if p.is_file()
    }


def fingerprint(warehouse: Path, site: Path) -> dict:
    tables = warehouse_hashes(warehouse)
    files = site_hashes(site)
    return {
        "commit": os.environ.get("PALEO_COMMIT") or os.environ.get("GITHUB_SHA") or "unknown",
        "warehouse_sha256": _sha(json.dumps(tables, sort_keys=True).encode()),
        "site_sha256": _sha(json.dumps(files, sort_keys=True).encode()),
        "tables": tables,
        "site_files": files,
    }


def compare(a: dict, b: dict) -> list[str]:
    """Differences between two fingerprints (empty when both runs produced the same)."""
    diffs = []
    for name in sorted(set(a["tables"]) | set(b["tables"])):
        if a["tables"].get(name) != b["tables"].get(name):
            diffs.append(f"table {name}: {a['tables'].get(name)} != {b['tables'].get(name)}")
    for path in sorted(set(a["site_files"]) | set(b["site_files"])):
        if a["site_files"].get(path) != b["site_files"].get(path):
            diffs.append(f"site file {path} differs")
    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", type=Path, default=project_root() / "site" / "_build")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("A", "B"))
    args = parser.parse_args()
    if args.compare:
        a, b = (json.loads(p.read_text(encoding="utf-8")) for p in args.compare)
        diffs = compare(a, b)
        for line in diffs[:50]:
            print(line)
        print(
            f"{len(a['tables'])} tables and {len(a['site_files'])} site files compared: "
            f"{len(diffs)} differences ({a['commit'][:7]} vs {b['commit'][:7]})"
        )
        return 1 if diffs else 0
    doc = fingerprint(get_paths().warehouse, args.site)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(
        f"warehouse {doc['warehouse_sha256'][:12]} ({len(doc['tables'])} tables) · "
        f"site {doc['site_sha256'][:12]} ({len(doc['site_files'])} files)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
