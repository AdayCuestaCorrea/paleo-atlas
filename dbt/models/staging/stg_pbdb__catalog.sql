-- Encyclopedia catalog (ALCANCE.md §7, Phase 3): every accepted extinct genus and species
-- that PBDB lists under each clade of the scope seed, from the latest download.
-- Ichnotaxa (footprints, eggs: flag I) and form taxa (flag F) are not organisms and
-- get no page.
-- Each download is several MB: it is read with a typed schema (not as JSON text,
-- which needs gigabytes of memory to unnest).
with versions as (
    select key as base_name, version_date, payload.records as records
    from read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/raw/pbdb/catalog/*/*.json',
        format = 'auto',
        maximum_object_size = 268435456,
        columns = {
            key: 'VARCHAR',
            version_date: 'DATE',
            payload: 'STRUCT(records STRUCT(
                taxon_no VARCHAR, taxon_name VARCHAR, taxon_rank VARCHAR,
                accepted_rank VARCHAR, flags VARCHAR, taxon_attr VARCHAR,
                parent_no VARCHAR, parent_name VARCHAR, phylum VARCHAR, "class" VARCHAR, "order" VARCHAR,
                family VARCHAR, genus VARCHAR, type_taxon VARCHAR, n_occs INTEGER,
                firstapp_max_ma DOUBLE, lastapp_min_ma DOUBLE,
                early_interval VARCHAR, late_interval VARCHAR
            )[])'
        }
    )
    qualify version_date = max(version_date) over (partition by key)
),

records as (
    select base_name, version_date, unnest(records) as r from versions
)

select
    base_name,
    version_date,
    r.taxon_no as pbdb_taxon_no,
    r.taxon_name as pbdb_name,
    -- The download only asks for genera and species, and PBDB leaves the rank out of
    -- some responses: one word is a genus, two a species.
    coalesce(
        r.taxon_rank, r.accepted_rank,
        case when r.taxon_name like '% %' then 'species' else 'genus' end
    ) as taxon_rank,
    r.taxon_attr as attribution,
    'txn:' || r.parent_no as parent_no,  -- the clade above (stg_pbdb__clades.clade_no)
    r.parent_name,
    r.phylum,
    r."class" as class_name,
    nullif(r."order", 'NO_ORDER_SPECIFIED') as order_name,
    nullif(r.family, 'NO_FAMILY_SPECIFIED') as family_name,
    nullif(r.genus, 'NO_GENUS_SPECIFIED') as genus_name,
    r.type_taxon,
    r.n_occs as occurrence_count,
    r.firstapp_max_ma as first_appearance_max_ma,
    r.lastapp_min_ma as last_appearance_min_ma,
    r.early_interval,
    coalesce(r.late_interval, r.early_interval) as late_interval
from records
where coalesce(r.flags, '') not similar to '.*[IF].*'
