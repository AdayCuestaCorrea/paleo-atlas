"""The GBIF reconciliation job (paleo.gbif_job.spec) in DuckDB SQL.

    uv run python -m paleo.gbif_job.duckdb_job GBIF_FILES PBDB_GENERA OUT_DIR

GBIF_FILES: Parquet or CSV files of a simple download (glob). PBDB_GENERA: Parquet
with taxon_name, family_name. Writes one Parquet file per output to OUT_DIR.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

from paleo.gbif_job.spec import (
    GBIF_COLUMNS,
    OUTPUTS,
    POINT_STEP,
    TOP_INSTITUTIONS,
    TOP_UNMATCHED,
)


def _reader(gbif: str) -> str:
    if gbif.endswith((".csv", ".csv.gz", ".txt")):
        return f"read_csv('{gbif}', delim='\\t', quote='', header=true, all_varchar=true)"
    return f"read_parquet('{gbif}', union_by_name=true)"


def load(con: duckdb.DuckDBPyConnection, gbif: str, pbdb_genera: str) -> None:
    """Views ``gbif`` (columns lower-cased, as in the spec) and ``pbdb``."""
    con.execute(f"create or replace view gbif_raw as select * from {_reader(gbif)}")
    actual = {c[0].lower(): c[0] for c in con.execute("describe gbif_raw").fetchall()}
    cols = ", ".join(
        f'"{actual[c]}" as {c}' if c in actual else f"null as {c}" for c in GBIF_COLUMNS
    )
    con.execute(f"create or replace view gbif_cols as select {cols} from gbif_raw")
    # The name keys of the spec, computed once: interpreted genus, verbatim genus, family.
    con.execute("""
        create or replace view gbif as
        select *,
            nullif(coalesce(genus, split_part(scientificname, ' ', 1)), '') as name_key,
            nullif(split_part(verbatimscientificname, ' ', 1), '') as verbatim_key,
            nullif(family, '') as family_key
        from gbif_cols""")
    con.execute(
        "create or replace view pbdb as select taxon_name, family_name "
        f"from read_parquet('{pbdb_genera}')"
    )


SQL = f"""
create or replace temp table names as
select name_key as name, verbatim_key as verbatim_genus, family_key as family,
       count(*) as records
from gbif
group by all;

create or replace temp table resolved as
with exact as (
    select n.name, n.verbatim_genus, n.family, p.taxon_name as genus, 'exact' as method
    from names as n inner join pbdb as p on p.taxon_name = n.name
),
synonym as (
    select n.name, n.verbatim_genus, n.family, p.taxon_name as genus, 'synonym' as method
    from names as n inner join pbdb as p on p.taxon_name = n.verbatim_genus
    where n.name is null or n.name not in (select taxon_name from pbdb)
),
typo_candidates as (
    select n.name, n.verbatim_genus, n.family, p.taxon_name as genus
    from names as n
    inner join pbdb as p
        on left(p.taxon_name, 1) = left(n.name, 1)
       and levenshtein(n.name, p.taxon_name) <= 1
       and (n.family is null or p.family_name is null or n.family = p.family_name)
    where n.name not in (select taxon_name from pbdb)
      and (n.verbatim_genus is null or n.verbatim_genus not in (select taxon_name from pbdb))
),
typo as (
    select name, verbatim_genus, family, min(genus) as genus, 'typo' as method
    from typo_candidates
    group by all
    having count(distinct genus) = 1
)
select * from exact
union all select * from synonym
union all select * from typo;

create or replace temp table matched as
select g.*, r.genus as pbdb_genus, r.method,
    floor(try_cast(g.decimallatitude as double) / {POINT_STEP} + 0.5) * {POINT_STEP} as lat,
    floor(try_cast(g.decimallongitude as double) / {POINT_STEP} + 0.5) * {POINT_STEP} as lon
from gbif as g
inner join resolved as r
    on r.name is not distinct from g.name_key
   and r.verbatim_genus is not distinct from g.verbatim_key
   and r.family is not distinct from g.family_key;

create or replace temp table genus_specimens as
with totals as (
    select pbdb_genus, count(*) as specimens,
           count(distinct nullif(institutioncode, '')) as institutions
    from matched group by pbdb_genus
),
countries as (
    select pbdb_genus, list(countrycode order by n desc, countrycode) as countries
    from (select pbdb_genus, countrycode, count(*) as n from matched
          where nullif(countrycode, '') is not null group by all)
    group by pbdb_genus
),
points as (
    select pbdb_genus, list({{'lat': lat, 'lon': lon, 'n': n}} order by lat, lon) as points
    from (select pbdb_genus, lat, lon, count(*) as n from matched
          where lat is not null and lon is not null group by all)
    group by pbdb_genus
),
top_institutions as (
    select pbdb_genus,
           list({{'code': institutioncode, 'n': n}} order by n desc, institutioncode)
               [1:{TOP_INSTITUTIONS}] as top_institutions
    from (select pbdb_genus, institutioncode, count(*) as n from matched
          where nullif(institutioncode, '') is not null group by all)
    group by pbdb_genus
),
methods as (
    select pbdb_genus, list({{'method': method, 'n': n}} order by method) as by_method
    from (select pbdb_genus, method, count(*) as n from matched group by all)
    group by pbdb_genus
)
select t.pbdb_genus as genus, t.specimens, t.institutions,
       c.countries, p.points, m.by_method, i.top_institutions
from totals as t
left join countries as c using (pbdb_genus)
left join points as p using (pbdb_genus)
left join methods as m using (pbdb_genus)
left join top_institutions as i using (pbdb_genus)
order by genus;

create or replace temp table institutions as
select institutioncode as institution_code, count(*) as specimens,
       count(distinct pbdb_genus) as genera
from matched where nullif(institutioncode, '') is not null
group by all order by institution_code;

create or replace temp table countries as
select countrycode as country_code, count(*) as specimens, count(distinct pbdb_genus) as genera
from matched where nullif(countrycode, '') is not null
group by all order by country_code;

create or replace temp table unmatched as
select coalesce(n.name, '') as name, cast(sum(n.records) as bigint) as records,
       case when n.name is null then 'no_name' else 'not_in_catalog' end as reason
from names as n
anti join resolved as r
    on r.name is not distinct from n.name
   and r.verbatim_genus is not distinct from n.verbatim_genus
   and r.family is not distinct from n.family
group by all
order by records desc, name
limit {TOP_UNMATCHED};
"""


def run(
    gbif: str, pbdb_genera: str, out_dir: Path, *, threads: int | None = None
) -> dict[str, int]:
    """Run the job; returns the number of rows of each output."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    if threads:
        con.execute(f"set threads = {threads}")
    try:
        load(con, gbif, pbdb_genera)
        con.execute(SQL)
        counts = {}
        for name in OUTPUTS:
            con.execute(f"copy {name} to '{out_dir / name}.parquet' (format parquet)")
            counts[name] = con.execute(f"select count(*) from {name}").fetchone()[0]
        return counts
    finally:
        con.close()


if __name__ == "__main__":
    print(run(sys.argv[1], sys.argv[2], Path(sys.argv[3])))
