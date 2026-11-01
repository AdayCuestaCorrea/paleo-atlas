-- Latest Commons metadata per file listed in the Wikipedia tables.
select
    key as file_name,
    version_date as checked_on,
    cast(json_extract(payload, '$.found') as boolean) as found_on_commons,
    payload ->> 'url' as url,
    payload ->> 'thumb_url' as thumb_url,
    payload ->> 'description_url' as description_url,
    payload ->> 'mime' as mime_type,
    cast(payload ->> 'width' as integer) as width,
    cast(payload ->> 'height' as integer) as height,
    payload ->> 'license_short_name' as license_name,
    payload ->> 'license_url' as license_url,
    {{ strip_html("payload ->> 'artist_html'") }} as author,
    {{ strip_html("payload ->> 'credit_html'") }} as credit,
    payload ->> 'restrictions' as restrictions,
    -- Normalized license id, matched against the license_allowlist seed.
    case
        when payload ->> 'license_short_name' is null then null
        when lower(payload ->> 'license_short_name') similar to '(public domain|pd|pd-.*)' then 'public-domain'
        when lower(payload ->> 'license_short_name') = 'cc0' then 'cc0'
        else regexp_replace(lower(trim(payload ->> 'license_short_name')), '[^a-z0-9.]+', '-', 'g')
    end as license_id
from {{ read_raw_store('commons', 'files') }}
qualify version_date = max(version_date) over (partition by key)
