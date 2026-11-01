-- Latest PhyloPic lookup per queried name (species, genus or clade).
select
    key as queried_name,
    version_date as checked_on,
    cast(json_extract(payload, '$.found') as boolean) as found_on_phylopic,
    payload ->> 'node_uuid' as node_uuid,
    payload ->> '$.image.uuid' as image_uuid,
    payload ->> '$.image.attribution' as attribution,
    payload ->> '$.image.contributor' as contributor,
    payload ->> '$.image.license_url' as license_url,
    payload ->> '$.image.vector_url' as vector_url,
    payload ->> '$.image.raster_url' as raster_url,
    payload ->> '$.image.page_url' as page_url,
    -- "https://creativecommons.org/licenses/by-nc-sa/3.0/" -> "cc-by-nc-sa-3.0"
    case
        when payload ->> '$.image.license_url' like '%publicdomain/zero%' then 'cc0'
        when payload ->> '$.image.license_url' like '%publicdomain/mark%' then 'public-domain'
        else 'cc-' || replace(
            regexp_extract(payload ->> '$.image.license_url', 'licenses/([a-z-]+/[0-9.]+)', 1), '/', '-'
        )
    end as license_id_raw
from {{ read_raw_store('phylopic', 'nodes') }}
qualify version_date = max(version_date) over (partition by key)
