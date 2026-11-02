"""Read the parsed (interim) Wikipedia output shared by every enrichment step."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def latest_revision_dirs(interim_root: Path) -> list[Path]:
    """Latest parsed revision folder of each Wikipedia page."""
    out = []
    for page in sorted((interim_root / "wikipedia").glob("*")):
        revisions = [p for p in page.iterdir() if p.is_dir() and p.name.isdigit()]
        if revisions:
            out.append(max(revisions, key=lambda p: int(p.name)))
    return out


def latest_rows(
    interim_root: Path, kind: str, *, in_scope_only: bool = True
) -> Iterator[dict[str, Any]]:
    """Rows of ``kind`` (``new_taxa`` or ``research``) from every page's latest parse.

    Rows outside the taxonomic scope (paleo.scope: turtles, lizards, most bony
    fishes on the reptile and fish pages) are left out, so no step spends requests
    or LLM quota on taxa that never get a page."""
    for folder in latest_revision_dirs(interim_root):
        for row in read_jsonl(folder / f"{kind}.jsonl"):
            if in_scope_only and "taxon_group" in row and row["taxon_group"] is None:
                continue
            yield row
