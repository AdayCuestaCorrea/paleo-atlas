-- Taxonomic opinions of PBDB on the genera and species of each block (latest monthly
-- download): who said what about a name, and when (history backwards, §9, H4).
-- Compact field names (vocab=com): oid opinion, otp C = PBDB's current classification,
-- nam name, tid taxon, sta status, prl parent (or senior synonym), spl spelling reason,
-- cnm the name as spelled in that opinion, oat author, opy year, rid reference.
with versions as (
    select key as base_name, version_date, payload.records as records
    from {{ read_optional_typed_raw_store('pbdb', 'opinions', 'STRUCT(records STRUCT( oid VARCHAR, otp VARCHAR, rnk INTEGER, nam VARCHAR, tid VARCHAR, cnm VARCHAR, sta VARCHAR, prl VARCHAR, par VARCHAR, spl VARCHAR, oat VARCHAR, opy VARCHAR, rid VARCHAR )[])') }}
    qualify version_date = max(version_date) over (partition by key)
),

records as (
    select base_name, version_date, unnest(records) as r from versions
)

select
    r.oid as opinion_id,
    base_name,
    version_date,
    r.otp = 'C' as is_current_classification,
    case r.rnk when 5 then 'genus' when 3 then 'species' else 'other' end as taxon_rank,
    r.nam as taxon_name,
    r.tid as pbdb_taxon_no,
    coalesce(r.cnm, r.nam) as name_used,
    r.sta as status,
    r.prl as parent_name,
    r.par as parent_taxon_no,
    r.spl as spelling_reason,
    r.oat as opinion_author,
    try_cast(r.opy as integer) as opinion_year,
    r.rid as reference_id
from records
-- One opinion can be listed under two blocks (a fish genus in two seeds): keep one.
qualify row_number() over (partition by r.oid order by base_name) = 1
