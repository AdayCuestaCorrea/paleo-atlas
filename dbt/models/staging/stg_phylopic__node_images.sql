-- Every PhyloPic image kept for each queried name (latest lookup): the node's primary
-- image first (position 0), then the others of the node and its descendants. Lookups
-- stored before the list existed only have the primary. The silhouette of the size
-- comparator takes the first one with an allowed license (the primary is sometimes
-- non-commercial while others of the same animal are CC0 or CC BY).
with latest as (
    select key, version_date, payload
    from {{ read_raw_store('phylopic', 'nodes') }}
    qualify version_date = max(version_date) over (partition by key)
),

images as (
    select key, version_date, i.image, i.pos - 1 as position
    from latest,
        unnest(cast(json_extract(payload, '$.images') as json[])) with ordinality as i(image, pos)
    where json_extract(payload, '$.images') is not null
    union all
    select key, version_date, json_extract(payload, '$.image'), 0
    from latest
    where json_extract(payload, '$.images') is null
        and json_extract(payload, '$.image') is not null
        and payload ->> '$.image' <> 'null'
)

select
    key || '#' || position as image_key,
    key as queried_name,
    version_date as checked_on,
    position,
    image ->> 'uuid' as image_uuid,
    image ->> 'node' as image_node,
    image ->> 'attribution' as attribution,
    image ->> 'contributor' as contributor,
    image ->> 'license_url' as license_url,
    image ->> 'vector_url' as vector_url,
    image ->> 'raster_url' as raster_url,
    image ->> 'page_url' as page_url,
    case
        when image ->> 'license_url' like '%publicdomain/zero%' then 'cc0'
        when image ->> 'license_url' like '%publicdomain/mark%' then 'public-domain'
        else 'cc-' || replace(
            regexp_extract(image ->> 'license_url', 'licenses/([a-z-]+/[0-9.]+)', 1), '/', '-'
        )
    end as license_id_raw
from images
