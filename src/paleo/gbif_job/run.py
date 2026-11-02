"""Glue for `paleo gbif reconcile`: inputs from the cache and the warehouse, the job,
and the extract in the versioned raw store (decision A11: aggregates only)."""

from __future__ import annotations

import importlib.util
import shutil
import time
import zipfile
from pathlib import Path

import duckdb

from paleo.config import get_paths, project_root

ENGINES = ("duckdb", "spark")


def unpack(download_zip: Path) -> str:
    """Unzip a simple download next to itself; returns the glob of its data files.

    SIMPLE_PARQUET zips hold a folder ``occurrence.parquet/`` of part files without
    extension; SIMPLE_CSV zips hold one tab-separated ``.csv``."""
    folder = download_zip.with_suffix("")
    if not folder.exists():
        with zipfile.ZipFile(download_zip) as z:
            z.extractall(folder)
    parts = next(folder.rglob("occurrence.parquet"), None)
    if parts is not None and parts.is_dir():
        return str(parts / "*")
    csv = sorted(folder.rglob("*.csv"))
    if not csv:
        raise FileNotFoundError(f"no data files in {download_zip}")
    return str(csv[0])


def export_genera(target: Path) -> Path:
    """PBDB genera of the encyclopedia (taxon_name, family_name) from the warehouse."""
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(get_paths().warehouse), read_only=True)
    try:
        con.execute(
            "copy (select taxon_name, family_name from main.int_catalog_genera order by 1) "
            f"to '{target}' (format parquet)"
        )
    finally:
        con.close()
    return target


def spark_job():
    path = project_root() / "spark" / "jobs" / "gbif_reconcile.py"
    spec = importlib.util.spec_from_file_location("gbif_reconcile", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reconcile(key: str, engine: str, out_dir: Path | None = None) -> tuple[dict[str, int], float]:
    """Run the job on download ``key``; returns (rows per output, seconds)."""
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {ENGINES}")
    data = get_paths().data
    zip_path = data / "cache" / "gbif" / key / f"{key}.zip"
    gbif_files = unpack(zip_path)
    genera = export_genera(data / "cache" / "gbif" / key / "pbdb_genera.parquet")
    out = out_dir or data / "raw" / "gbif" / "extract" / key
    if out.exists():
        shutil.rmtree(out)
    start = time.perf_counter()
    if engine == "duckdb":
        from paleo.gbif_job.duckdb_job import run

        counts = run(gbif_files, str(genera), out)
    else:
        counts = spark_job().run(gbif_files, str(genera), str(out))
    return counts, time.perf_counter() - start
