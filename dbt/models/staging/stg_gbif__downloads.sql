-- The GBIF download each extract comes from: key, DOI (to cite, §19) and filter.
with downloads as (
    select key as download_key, version_date, payload
    from {{ read_optional_raw_store('gbif', 'downloads') }}
)

select
    download_key,
    payload ->> 'doi' as doi,
    payload ->> 'citation' as citation,
    cast(payload ->> 'total_records' as bigint) as total_records,
    payload ->> 'license' as license,
    cast(payload ->> 'created' as timestamp) as created_at,
    version_date
from downloads
qualify version_date = max(version_date) over (partition by download_key)
