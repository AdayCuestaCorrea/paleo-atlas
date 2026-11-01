-- Taxa that get a page: the new taxa of the yearly pages, plus every species,
-- subspecies or genus that PBDB knows and that a study links or names in italics
-- (decision of 2026-11-02: basic pages for known taxa in the MVP).
with new_taxa as (
    select
        {{ taxon_key('taxon_name') }} as taxon_key,
        taxon_name,
        'new' as page_type,
        taxonomic_block,
        taxon_group
    from {{ ref('stg_wikipedia__new_taxa') }}
),

mentions as (
    select * from {{ ref('int_research_taxon_links') }}
),

known as (
    select
        taxon_key,
        any_value(taxon_name order by taxon_name) as taxon_name,
        'known' as page_type,
        any_value(taxonomic_block) as taxonomic_block,
        any_value(taxon_group) as taxon_group
    from mentions
    where match_source = 'pbdb'
      and taxon_rank in ('species', 'subspecies', 'genus')
      and taxon_key not in (select taxon_key from new_taxa)
    group by taxon_key
)

select * from new_taxa
union all
select * from known
