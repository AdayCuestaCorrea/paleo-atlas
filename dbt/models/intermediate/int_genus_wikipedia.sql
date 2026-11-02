-- Wikipedia articles that are really about an encyclopedia genus. A name can lead to
-- a homonym ("Coloradia" is also a moth), so an article is only kept when its
-- Wikidata item carries the PBDB id (P842) of the genus or of one of its species
-- AND descends from the root of its block in Wikidata's taxonomy (P171). P842 alone
-- is not enough: the moth's item carries the dinosaur's PBDB id by mistake.
-- Disambiguation pages are never kept.
with lookups as (
    select * from {{ ref('stg_wikipedia__genus_articles') }}
),

pbdb_ids as (
    -- every PBDB id that identifies the genus: its own and its species'
    select pbdb_name as genus_name, pbdb_taxon_no
    from {{ ref('stg_pbdb__catalog') }} where taxon_rank = 'genus'
    union
    select genus_name, pbdb_taxon_no
    from {{ ref('stg_pbdb__catalog') }} where taxon_rank = 'species'
),

matches as (
    select l.genus_name
    from lookups as l
    cross join unnest(l.pbdb_ids) as u(pbdb_id)
    inner join pbdb_ids as p on p.genus_name = l.genus_name and p.pbdb_taxon_no = u.pbdb_id
    group by l.genus_name
)

select
    l.genus_name,
    {{ taxon_key('l.genus_name') }} as taxon_key,
    l.en_title,
    l.es_title,
    l.wikidata_item,
    l.lead_image,
    l.version_date as checked_on
from lookups as l
inner join matches as m using (genus_name)
where l.en_title is not null
  and not coalesce(l.disambiguation, false)
  and l.in_scope_tree
