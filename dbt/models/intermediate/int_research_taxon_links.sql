-- Which taxa each study is about: wikilinks and italic unlinked names that resolve
-- to a PBDB taxon or to one of this year's new taxa.
with research as (
    select research_id, taxonomic_block, taxon_group, linked_terms, unlinked_names
    from {{ ref('stg_wikipedia__research_items') }}
),

mentioned as (
    select research_id, taxonomic_block, taxon_group, unnest(linked_terms) as mentioned_name, 'link' as mention_kind
    from research
    union all
    select research_id, taxonomic_block, taxon_group, unnest(unlinked_names), 'italic'
    from research
),

new_taxa as (
    select taxon_name from {{ ref('stg_wikipedia__new_taxa') }}
),

resolved as (
    select
        m.research_id,
        m.mentioned_name,
        m.mention_kind,
        m.taxonomic_block,
        m.taxon_group,
        case
            when n.taxon_name is not null then n.taxon_name
            else coalesce(p.accepted_name, p.pbdb_name)
        end as taxon_name,
        case when n.taxon_name is not null then 'new_taxon' else 'pbdb' end as match_source,
        p.taxon_rank
    from mentioned as m
    left join new_taxa as n on n.taxon_name = m.mentioned_name
    left join {{ ref('stg_pbdb__taxa') }} as p
        on p.queried_name = m.mentioned_name and p.found
    where n.taxon_name is not null or p.found
)

select
    research_id,
    {{ taxon_key('taxon_name') }} as taxon_key,
    taxon_name,
    coalesce(taxon_rank, 'species') as taxon_rank,
    match_source,
    min(mention_kind) as mention_kind,  -- 'italic' < 'link'
    any_value(taxonomic_block) as taxonomic_block,
    any_value(taxon_group) as taxon_group
from resolved
group by all
