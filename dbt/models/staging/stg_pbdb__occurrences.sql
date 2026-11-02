-- PBDB occurrences of each block (latest download), identified at least to genus:
-- where and when each genus was found. Compact PBDB field names (vocab=com) are
-- renamed here. Read with a typed schema, like the catalog (tens of thousands of rows).
with versions as (
    select key as base_name, version_date, payload.records as records
    from read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/raw/pbdb/occurrences/*/*.json',
        format = 'auto',
        maximum_object_size = 268435456,
        columns = {
            key: 'VARCHAR',
            version_date: 'DATE',
            payload: 'STRUCT(records STRUCT(
                oid VARCHAR, tna VARCHAR, tid VARCHAR, oei VARCHAR, oli VARCHAR,
                eag DOUBLE, lag DOUBLE, cc2 VARCHAR, stp VARCHAR, lat VARCHAR, lng VARCHAR
            )[])'
        }
    )
    qualify version_date = max(version_date) over (partition by key)
),

records as (
    select base_name, version_date, unnest(records) as r from versions
)

select
    r.oid as occurrence_id,
    base_name,
    version_date,
    r.tna as taxon_name,
    split_part(r.tna, ' ', 1) as genus_name,
    r.tid as pbdb_taxon_id,
    r.oei as early_interval,
    coalesce(r.oli, r.oei) as late_interval,
    r.eag as max_ma,
    r.lag as min_ma,
    nullif(r.cc2, '') as country_code,
    r.stp as state,
    try_cast(r.lat as double) as latitude,
    try_cast(r.lng as double) as longitude
from records
qualify row_number() over (partition by r.oid order by base_name) = 1
