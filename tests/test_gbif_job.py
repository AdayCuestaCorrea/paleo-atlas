"""The GBIF reconciliation job (paleo.gbif_job.spec): DuckDB, and Spark when available."""

import shutil

import duckdb
import pytest

from paleo.gbif_job import duckdb_job

PBDB = [("Tyrannosaurus", "Tyrannosauridae"), ("Plateosaurus", "Plateosauridae"),
        ("Allosaurus", "Allosauridae"), ("Proa", None), ("Prob", None)]  # fmt: skip


def rec(gid, genus, verbatim, family, country, inst, lat=None, lon=None, name=None):
    """A GBIF record: interpreted genus, verbatim (original) name, family…"""
    name = name if name is not None else (f"{genus} sp." if genus else "")
    return (gid, genus, name, verbatim, family, country, lat, lon, inst)


T = "Tyrannosauridae"
GBIF = [
    rec("1", "Tyrannosaurus", "Tyrannosaurus rex", T, "US", "AMNH", "47.3", "-106.9"),
    rec("2", "Tyrannosaurus", "Tyrannosaurus rex", T, "CA", "ROM", "51.0", "-112.0"),
    rec("3", "Tyrannosaurus", "Tyrannosaurus rex", T, "US", "AMNH", "47.4", "-106.8"),
    # GBIF moved the name; the verbatim genus is the PBDB one
    rec("4", "Dinosaurus", "Plateosaurus erlenbergiensis", "Plateosauridae", "DE", "SMNS"),
    # one letter off, same family
    rec("5", "Allosaurs", "Allosaurs fragilis", "Allosauridae", "US", "YPM"),
    # one letter off but another family: not a typo of Tyrannosaurus
    rec("6", "Tyranosaurus", "Tyranosaurus sp.", "Allosauridae", "US", "X"),
    # one letter off two genera: ambiguous
    rec("7", "Proc", "Proc a", None, "FR", "Y"),
    rec("8", None, "", None, "FR", "Y"),
    rec("9", "Megalosaurus", "Megalosaurus bucklandii", "Megalosauridae", "UK", "OUM"),
]
COLUMNS = ["gbifID", "genus", "scientificName", "verbatimScientificName", "family",
           "countryCode", "decimalLatitude", "decimalLongitude", "institutionCode"]  # fmt: skip


def write_inputs(tmp_path):
    con = duckdb.connect()
    con.execute(f"create table g ({', '.join(f'{c} varchar' for c in COLUMNS)})")
    con.executemany(f"insert into g values ({', '.join('?' * len(COLUMNS))})", GBIF)
    con.execute(f"copy g to '{tmp_path}/gbif.parquet' (format parquet)")
    con.execute("create table p (taxon_name varchar, family_name varchar)")
    con.executemany("insert into p values (?, ?)", PBDB)
    con.execute(f"copy p to '{tmp_path}/pbdb.parquet' (format parquet)")
    con.close()
    return str(tmp_path / "gbif.parquet"), str(tmp_path / "pbdb.parquet")


def read(path, name):
    target = path / f"{name}.parquet"
    pattern = f"{target}/*.parquet" if target.is_dir() else str(target)
    return duckdb.sql(f"select * from read_parquet('{pattern}')").fetchall()


def test_reconciliation_and_aggregates_in_duckdb(tmp_path):
    gbif, pbdb = write_inputs(tmp_path)
    counts = duckdb_job.run(gbif, pbdb, tmp_path / "out")
    assert counts == {"genus_specimens": 3, "institutions": 4, "countries": 3, "unmatched": 4}
    rows = {r[0]: r for r in read(tmp_path / "out", "genus_specimens")}
    t = rows["Tyrannosaurus"]
    assert t[1:4] == (3, 2, ["US", "CA"])  # specimens, institutions, countries (most first)
    # points rounded to 0.5 degrees: records 1 and 3 fall in the same cell
    assert t[4] == [{"lat": 47.5, "lon": -107.0, "n": 2}, {"lat": 51.0, "lon": -112.0, "n": 1}]
    assert t[6] == [{"code": "AMNH", "n": 2}, {"code": "ROM", "n": 1}]  # top institutions
    assert rows["Plateosaurus"][5] == [{"method": "synonym", "n": 1}]
    assert rows["Allosaurus"][5] == [{"method": "typo", "n": 1}]
    unmatched = {r[0]: r[2] for r in read(tmp_path / "out", "unmatched")}
    assert unmatched == {"Tyranosaurus": "not_in_catalog", "Proc": "not_in_catalog",
                         "": "no_name", "Megalosaurus": "not_in_catalog"}  # fmt: skip


@pytest.mark.skipif(
    shutil.which("java") is None or __import__("importlib").util.find_spec("pyspark") is None,
    reason="PySpark or Java not available (uv sync --group spark)",
)
def test_spark_writes_the_same_extract_as_duckdb(tmp_path):
    import importlib.util
    from pathlib import Path

    gbif, pbdb = write_inputs(tmp_path)
    duckdb_job.run(gbif, pbdb, tmp_path / "duck")
    path = Path(__file__).resolve().parents[1] / "spark" / "jobs" / "gbif_reconcile.py"
    spec = importlib.util.spec_from_file_location("gbif_reconcile", path)
    job = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(job)
    job.run(gbif, pbdb, str(tmp_path / "spark"))
    for name in ("genus_specimens", "institutions", "countries", "unmatched"):
        assert sorted(map(str, read(tmp_path / "duck", name))) == sorted(
            map(str, read(tmp_path / "spark", name))
        ), name
