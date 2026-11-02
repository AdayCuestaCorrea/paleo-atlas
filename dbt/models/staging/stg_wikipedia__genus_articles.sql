-- Latest Wikipedia/Wikidata lookup of each encyclopedia genus (paleo.ingest.genus_articles):
-- the English article its name leads to, the Wikidata item, its PBDB ids (P842), the
-- Spanish article, the free lead image and whether the item descends from the block
-- root in Wikidata (P171). Not verified yet: see int_genus_wikipedia.
with latest as (
    select key as genus_name, version_date, payload
    from {{ read_raw_store('wikimedia', 'genus_articles') }}
    qualify version_date = max(version_date) over (partition by key)
)

select
    genus_name,
    version_date,
    payload ->> 'en_title' as en_title,
    payload ->> 'es_title' as es_title,
    cast(payload ->> 'redirected' as boolean) as redirected,
    cast(payload ->> 'disambiguation' as boolean) as disambiguation,
    payload ->> 'wikidata_item' as wikidata_item,
    cast(json_extract(payload, '$.pbdb_ids') as varchar[]) as pbdb_ids,
    coalesce(cast(payload ->> 'in_scope_tree' as boolean), false) as in_scope_tree,
    payload ->> 'lead_image' as lead_image
from latest
