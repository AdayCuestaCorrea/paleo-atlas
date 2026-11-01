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


def latest_rows(interim_root: Path, kind: str) -> Iterator[dict[str, Any]]:
    """Rows of ``kind`` (``new_taxa`` or ``research``) from every page's latest parse."""
    for folder in latest_revision_dirs(interim_root):
        yield from read_jsonl(folder / f"{kind}.jsonl")
