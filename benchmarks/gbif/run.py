"""Spark vs DuckDB on the GBIF reconciliation job (ALCANCE.md §7, Phase 3).

    uv run --group spark python benchmarks/gbif/run.py DOWNLOAD_KEY [--repeats 3]

Same job (paleo.gbif_job.spec), same inputs, same machine. For each engine and input
size (10 %, 50 % and 100 % of the download, chosen by gbifid so both engines read the
same rows) it runs the job ``--repeats`` times, each in a fresh process, and records:

* wall time (median of the repeats);
* peak memory of the whole process tree (Python + the Spark JVM), sampled from /proc;
* rows per second;
* lines of code of each implementation.

Writes benchmarks/gbif/results.json; benchmarks/gbif/results.md reports and discusses it.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from paleo.config import get_paths  # noqa: E402
from paleo.gbif_job.run import export_genera, unpack  # noqa: E402

FRACTIONS = (0.1, 0.5, 1.0)
IMPLEMENTATIONS = {
    "duckdb": ROOT / "src" / "paleo" / "gbif_job" / "duckdb_job.py",
    "spark": ROOT / "spark" / "jobs" / "gbif_reconcile.py",
}
RUNNER = """
import sys, json, time
sys.path.insert(0, {src!r})
engine, gbif, genera, out = sys.argv[1:5]
t = time.perf_counter()
if engine == "duckdb":
    from paleo.gbif_job.duckdb_job import run
    counts = run(gbif, genera, __import__("pathlib").Path(out))
else:
    import importlib.util
    spec = importlib.util.spec_from_file_location("job", {spark!r})
    job = importlib.util.module_from_spec(spec); spec.loader.exec_module(job)
    counts = job.run(gbif, genera, out)
print(json.dumps({{"seconds": time.perf_counter() - t, "counts": counts}}))
"""


def lines_of_code(path: Path) -> int:
    """Non-blank lines that are not comments or docstrings (rough, same rule for both)."""
    count, in_doc = 0, False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith('"""') or s.endswith('"""'):
            if not (s.count('"""') == 2 and len(s) > 6):
                in_doc = not in_doc
            continue
        if in_doc or not s or s.startswith("#"):
            continue
        count += 1
    return count


def tree_rss(pid: int) -> int:
    """Resident memory (bytes) of a process and all its descendants, from /proc."""
    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            statm = (proc / "statm").read_text().split()
        except OSError:
            continue
        children.setdefault(int(stat[1]), []).append(int(proc.name))
        rss[int(proc.name)] = int(statm[1]) * os.sysconf("SC_PAGE_SIZE")
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        total += rss.get(p, 0)
        stack.extend(children.get(p, []))
    return total


def run_once(engine: str, gbif: str, genera: str, out: Path) -> dict:
    code = RUNNER.format(src=str(ROOT / "src"), spark=str(IMPLEMENTATIONS["spark"]))
    env = {**os.environ, "SPARK_LOCAL_IP": "127.0.0.1"}
    proc = subprocess.Popen(
        [sys.executable, "-c", code, engine, gbif, genera, str(out)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env,
    )  # fmt: skip
    peak, stop = 0, threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.is_set():
            peak = max(peak, tree_rss(proc.pid))
            time.sleep(0.2)

    sampler = threading.Thread(target=sample, daemon=True)
    start = time.perf_counter()
    sampler.start()
    stdout, _ = proc.communicate()
    wall = time.perf_counter() - start
    stop.set()
    sampler.join()
    if proc.returncode:
        raise RuntimeError(f"{engine} failed with exit code {proc.returncode}")
    result = json.loads(stdout.strip().splitlines()[-1])
    return {"wall_s": wall, "job_s": result["seconds"], "peak_rss_mb": peak / 2**20,
            "counts": result["counts"]}  # fmt: skip


def subset(gbif: str, fraction: float, folder: Path) -> tuple[str, int]:
    """The same rows for both engines: gbifid hash below the fraction."""
    if fraction >= 1:
        rows = duckdb.execute(f"select count(*) from read_parquet('{gbif}')").fetchone()[0]
        return gbif, rows
    target = folder / f"gbif_{int(fraction * 100)}.parquet"
    duckdb.execute(
        f"copy (select * from read_parquet('{gbif}') "
        f"where hash(gbifid) % 1000 < {int(fraction * 1000)}) to '{target}' (format parquet)"
    )
    return str(target), duckdb.execute(f"select count(*) from '{target}'").fetchone()[0]


def machine() -> dict:
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text()
                .splitlines() if line.startswith("model name")), platform.processor())  # fmt: skip
    mem = int(Path("/proc/meminfo").read_text().split()[1]) / 2**20
    java = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr.split("\n")[
        0
    ]
    import pyspark

    return {"cpu": cpu, "cores": os.cpu_count(), "ram_gb": round(mem, 1),
            "python": platform.python_version(), "duckdb": duckdb.__version__,
            "pyspark": pyspark.__version__, "java": java}  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("key", help="GBIF download key (paleo gbif extract)")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    cache = get_paths().data / "cache" / "gbif" / args.key
    gbif = unpack(cache / f"{args.key}.zip")
    genera = str(export_genera(cache / "pbdb_genera.parquet"))
    loc = {engine: lines_of_code(path) for engine, path in IMPLEMENTATIONS.items()}
    results = {"machine": machine(), "download": args.key, "runs": [], "lines_of_code": loc}
    with tempfile.TemporaryDirectory() as tmp:
        for fraction in FRACTIONS:
            data, rows = subset(gbif, fraction, Path(tmp))
            for engine in IMPLEMENTATIONS:
                runs = [run_once(engine, data, genera, Path(tmp) / f"{engine}-{i}")
                        for i in range(args.repeats)]  # fmt: skip
                summary = {
                    "engine": engine, "fraction": fraction, "rows": rows,
                    "wall_s": statistics.median(r["wall_s"] for r in runs),
                    "job_s": statistics.median(r["job_s"] for r in runs),
                    "peak_rss_mb": statistics.median(r["peak_rss_mb"] for r in runs),
                    "all_wall_s": [round(r["wall_s"], 2) for r in runs],
                    "counts": runs[0]["counts"],
                }  # fmt: skip
                summary["rows_per_s"] = rows / summary["wall_s"]
                results["runs"].append(summary)
                wall, peak = summary["wall_s"], summary["peak_rss_mb"]
                print(f"{engine:6} {fraction:>4.0%} {rows:>10,} rows  wall {wall:7.1f} s  "
                      f"peak {peak:7.0f} MB")  # fmt: skip
    out = Path(__file__).with_name("results.json")
    out.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
