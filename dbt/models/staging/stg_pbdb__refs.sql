-- References of the PBDB opinions that can become history events (title, journal,
-- year, DOI), one stored list per block.
with versions as (
    select key as base_name, version_date, payload.records as records
    from {{ read_optional_typed_raw_store('pbdb', 'refs', 'STRUCT(records STRUCT( oid VARCHAR, pty VARCHAR, tit VARCHAR, pby VARCHAR, pbt VARCHAR, doi VARCHAR, ref VARCHAR )[])') }}
    qualify version_date = max(version_date) over (partition by key)
),

records as (
    select unnest(records) as r from versions
)

select distinct on (r.oid)
    r.oid as reference_id,
    r.pty as publication_type,
    {{ strip_html('r.tit') }} as title,  -- PBDB keeps <i> around the names
    nullif(trim(r.pbt), '') as journal,
    try_cast(r.pby as integer) as publication_year,
    nullif(regexp_replace(lower(trim(r.doi)), '^(https?://(dx\.)?doi\.org/|doi:\s*)', ''), '') as doi,
    r.ref as formatted
from records
order by r.oid
