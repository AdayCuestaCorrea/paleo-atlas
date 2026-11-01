-- Gallery candidates per taxon: files its Wikipedia articles show (in article
-- order, EN then ES) and files of its Commons category.
with latest as (
    select key as taxon_name, payload
    from {{ read_raw_store('commons', 'taxon_files') }}
    qualify version_date = max(version_date) over (partition by key)
)

select
    {{ taxon_key('taxon_name') }} as taxon_key,
    taxon_name,
    'article' as found_in,
    f.position as position,
    f.file_name
from latest
cross join unnest(cast(payload -> '$.article_files' as varchar[])) with ordinality as f(file_name, position)
union all
select
    {{ taxon_key('taxon_name') }},
    taxon_name,
    'category',
    f.position,
    f.file_name
from latest
cross join unnest(cast(payload -> '$.category_files' as varchar[])) with ordinality as f(file_name, position)
