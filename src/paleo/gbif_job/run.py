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
    extension, some of them empty (0 bytes, not valid Parquet: they are skipped);
    SIMPLE_CSV zips hold one tab-separated ``.csv``."""
    folder = download_zip.with_suffix("")
    if not folder.exists():
        with zipfile.ZipFile(download_zip) as z:
            z.extractall(folder, members=[m for m in z.infolist() if m.file_size > 0])
    for empty in folder.rglob("*"):
        if empty.is_file() and empty.stat().st_size == 0:
            empty.unlink()
    parts = next(folder.rglob("occurrence.parquet"), None)
    if parts is not None and parts.is_dir():
        return str(parts / "*")
    csv = sorted(folder.rglob("*.csv"))
    if not csv:
        raise FileNotFoundError(f"no data files in {download_zip}")
    return str(csv[0])


def latest_download() -> str | None:
    """Key of the most recent GBIF download recorded in the raw store."""
    from paleo.ingest.gbif import store

    downloads = store(get_paths().raw)
    records = [downloads.latest(k) for k in downloads.stored_keys()]
    records = [r["payload"] for r in records if r and r["payload"].get("status") == "SUCCEEDED"]
    if not records:
        return None
    return max(records, key=lambda r: (r.get("created") or "", r["key"]))["key"]


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
    extracts = data / "raw" / "gbif" / "extract"
    out = out_dir or extracts / key
    fresh = out.with_name(f".{out.name}.new")
    if fresh.exists():
        shutil.rmtree(fresh)
    start = time.perf_counter()
    if engine == "duckdb":
        from paleo.gbif_job.duckdb_job import run

        counts = run(gbif_files, str(genera), fresh)
    else:
        counts = spark_job().run(gbif_files, str(genera), str(fresh))
    seconds = time.perf_counter() - start
    if engine == "spark":
        _single_files(fresh)
    if out.exists() and same_content(out, fresh):
        # Same rows: keep the files as they are. The two engines write the same data
        # with different bytes, and the data branch must not change for nothing.
        shutil.rmtree(fresh)
        return counts, seconds
    if out_dir is None and extracts.exists():
        for old in extracts.iterdir():  # one extract at a time; git keeps the history
            if old != fresh:
                shutil.rmtree(old)
    elif out.exists():
        shutil.rmtree(out)
    fresh.rename(out)
    return counts, seconds


def same_content(a: Path, b: Path) -> bool:
    """True when two extracts hold the same rows in every output (whatever the bytes)."""
    from paleo.gbif_job.spec import OUTPUTS

    def rows(folder: Path, name: str) -> list[str]:
        target = folder / f"{name}.parquet"
        if not target.exists():
            return []
        con = duckdb.connect()
        try:
            return sorted(map(repr, con.execute(f"select * from '{target}'").fetchall()))
        finally:
            con.close()

    return all(rows(a, name) == rows(b, name) for name in OUTPUTS)


def _single_files(out: Path) -> None:
    """Spark writes each output as a folder (one part file, _SUCCESS, .crc files): keep
    just the part file, as ``<name>.parquet``, the same layout as the DuckDB job."""
    from paleo.gbif_job.spec import OUTPUTS

    for name in OUTPUTS:
        folder = out / f"{name}.parquet"
        if not folder.is_dir():
            continue
        (part,) = folder.glob("part-*.parquet")
        tmp = out / f".{name}.parquet"
        part.rename(tmp)
        shutil.rmtree(folder)
        tmp.rename(folder)
