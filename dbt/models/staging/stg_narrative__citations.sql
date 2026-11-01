-- Citable sources of each taxon page (one row per chunk referenced by the facts file).
with docs as (
    select taxon_key, citations from {{ read_narrative('facts') }}
)

select
    d.taxon_key || ':' || c.key as citation_key,
    d.taxon_key,
    c.key as chunk_id,
    c.value ->> 'source' as source,
    c.value ->> 'title' as title,
    c.value ->> 'url' as url,
    c.value ->> 'doi' as doi,
    c.value ->> 'license' as license
from docs as d
cross join json_each(d.citations) as c
