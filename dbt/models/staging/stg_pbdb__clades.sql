-- Clades above genus of each block (latest monthly download): the clades inside the
-- block root and the root's ancestors (§11.2, Phase 3 H7). One row per clade.
-- Compact field names (vocab=com): oid id, rnk rank, nam name, par parent,
-- fea first appearance (oldest Ma), lla last appearance (youngest Ma).
{%- set clade = "STRUCT(oid VARCHAR, rnk VARCHAR, nam VARCHAR, par VARCHAR, fea DOUBLE, lla DOUBLE)" %}
with versions as (
    select key as base_name, version_date, payload
    from {{ read_optional_typed_raw_store('pbdb', 'clades',
        'STRUCT(clades ' ~ clade ~ '[], ancestors ' ~ clade ~ '[])') }}
    qualify version_date = max(version_date) over (partition by key)
),

records as (
    select base_name, unnest(payload.clades) as r from versions
    union all
    select base_name, unnest(payload.ancestors) as r from versions
)

select
    r.oid as clade_no,
    any_value(r.nam) as clade_name,
    any_value(r.rnk) as clade_rank,
    -- PBDB's root ("Life") is its own parent.
    nullif(any_value(r.par), any_value(r.oid)) as parent_no,
    any_value(r.fea) as first_appearance_max_ma,
    any_value(r.lla) as last_appearance_min_ma
from records
where r.oid is not null
group by r.oid
