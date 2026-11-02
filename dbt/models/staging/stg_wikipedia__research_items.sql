-- Studies as listed on the latest stored revision of each yearly page. A study may be
-- listed on two pages (a fish tooth in a plesiosaur bone is on the reptile and the
-- fish page): one row per study, from the first block (archosaurs, marine reptiles,
-- fishes), with the taxa mentioned on every page.
with latest as (
    select *
    from {{ ref('stg_wikipedia__research_revisions') }}
    {{ latest_revision_only('revid', 'page_title') }}
),

mentions as (
    select
        research_id,
        list_distinct(flatten(list(linked_terms))) as linked_terms,
        list_distinct(flatten(list(unlinked_names))) as unlinked_names,
        list_distinct(flatten(list(candidate_taxa))) as candidate_taxa,
        list(page_title order by page_title) as listed_on
    from latest
    group by research_id
)

select
    l.* replace (
        m.linked_terms as linked_terms,
        m.unlinked_names as unlinked_names,
        m.candidate_taxa as candidate_taxa
    ),
    m.listed_on
from latest as l
inner join mentions as m using (research_id)
qualify row_number() over (
    partition by l.research_id
    order by case l.taxonomic_block when 'archosaurs' then 1 when 'marine_reptiles' then 2 else 3 end,
             l.page_title
) = 1
