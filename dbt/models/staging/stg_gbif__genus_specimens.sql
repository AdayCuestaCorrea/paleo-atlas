-- GBIF fossil specimens per PBDB genus (the monthly extract, paleo.gbif_job): how many,
-- in how many institutions and countries, the points of the map and the institutions
-- with most specimens. Empty until the first monthly run.
select *
from {{ read_optional_parquet('raw/gbif/extract/*/genus_specimens.parquet', {
    'genus': 'varchar', 'specimens': 'bigint', 'institutions': 'bigint',
    'countries': 'varchar[]', 'points': 'struct(lat double, lon double, n bigint)[]',
    'by_method': 'struct(method varchar, n bigint)[]',
    'top_institutions': 'struct(code varchar, n bigint)[]'
}) }}
