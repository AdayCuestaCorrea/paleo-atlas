-- Known species whose genus has an encyclopedia page (Phase 3): they get no page of
-- their own (decision of 2026-11-03, revising v8). Their events go to the genus page
-- with the species name, and their old URL redirects there (dim_taxon_redirect).
-- New species of the year keep their own page.
with species as (
    select
        taxon_key as species_key,
        any_value(taxon_name order by taxon_name) as species_name,
        {{ taxon_key("split_part(any_value(taxon_name order by taxon_name), ' ', 1)") }} as genus_key
    from {{ ref('int_research_taxon_links') }}
    where match_source = 'pbdb' and taxon_rank in ('species', 'subspecies')
    group by taxon_key
)

select s.*
from species as s
inner join {{ ref('int_catalog_genera') }} as g on g.taxon_key = s.genus_key
where s.species_key not in (
    select {{ taxon_key('taxon_name') }} from {{ ref('stg_wikipedia__new_taxa') }}
)
