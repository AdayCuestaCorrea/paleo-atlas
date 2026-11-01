-- Every stored PBDB lookup, one row per queried name and version (history input).
-- A name may match several PBDB records (homonyms); Chordata is preferred, as the
-- atlas only covers vertebrates.
with versions as (
    select key as queried_name, version_date, payload
    from {{ read_raw_store('pbdb', 'taxa') }}
),

records as (
    select
        v.queried_name,
        v.version_date,
        cast(json_extract(v.payload, '$.found') as boolean) as found,
        r.value as record,
        r.ordinality as record_position
    from versions as v
    left join lateral (
        select value, row_number() over () as ordinality
        from json_each(json_extract(v.payload, '$.records'))
    ) as r on true
),

ranked as (
    select
        *,
        row_number() over (
            partition by queried_name, version_date
            order by (record ->> 'phylum' = 'Chordata') desc nulls last, record_position
        ) as preference
    from records
)

select
    queried_name,
    version_date,
    found,
    record ->> 'taxon_no' as pbdb_taxon_no,
    record ->> 'taxon_name' as pbdb_name,
    record ->> 'taxon_rank' as taxon_rank,
    record ->> 'taxon_attr' as attribution,
    record ->> 'accepted_name' as accepted_name,
    record ->> 'parent_name' as parent_name,
    record ->> 'phylum' as phylum,
    record ->> 'class' as class_name,
    nullif(record ->> 'order', 'NO_ORDER_SPECIFIED') as order_name,
    nullif(record ->> 'family', 'NO_FAMILY_SPECIFIED') as family_name,
    nullif(record ->> 'genus', 'NO_GENUS_SPECIFIED') as genus_name,
    record ->> 'is_extant' as is_extant,
    cast(record ->> 'n_occs' as integer) as occurrence_count,
    cast(record ->> 'firstapp_max_ma' as double) as first_appearance_max_ma,
    cast(record ->> 'lastapp_min_ma' as double) as last_appearance_min_ma,
    record ->> 'early_interval' as early_interval,
    coalesce(record ->> 'late_interval', record ->> 'early_interval') as late_interval
from ranked
where preference = 1
