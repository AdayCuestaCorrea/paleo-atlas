-- The history backwards (ALCANCE.md §9, Phase 3 H4), placed on the taxon pages:
-- PBDB's taxonomic opinions (int_opinion_events) and the yearly Wikipedia pages of
-- past years (names described and studies). An event about a species also goes to
-- its genus page, and a synonymy also to the page of the senior name, with the name
-- concerned (`subject_name`) when it is not the page's own taxon.
-- Dates are years (precision 'year'): the opinions only carry the year, and past
-- studies are not looked up in Crossref.
with pages as (
    select taxon_key from {{ ref('int_taxon_pages') }}
),

opinion_events as (
    select
        event_type,
        subject_name,
        related_name,
        study_id,
        cast(null as varchar) as research_id,
        opinion_year as event_year,
        opinion_author as attribution,
        'Paleobiology Database' as source_title,
        3 as source_rank,
        -- Where it is shown: the name itself and, for a synonymy or a replacement,
        -- the senior name too.
        case
            when event_type in ('synonymized', 'replaced') then [subject_name, related_name]
            else [subject_name]
        end as shown_on
    from {{ ref('int_opinion_events') }}
),

past_descriptions as (
    select
        case when novelty = 'new_combination' then 'recombined' else 'description' end
            as event_type,
        taxon_name as subject_name,
        case when novelty = 'new_combination' then split_part(taxon_name, ' ', 1) end
            as related_name,
        coalesce('doi:' || primary_doi, 'wikipast:' || md5(new_taxon_id)) as study_id,
        cast(null as varchar) as research_id,
        page_year as event_year,
        name_authors as attribution,
        page_title as source_title,
        case when primary_doi is not null then 1 else 2 end as source_rank,
        [taxon_name] as shown_on
    from {{ ref('stg_wikipedia_past__new_taxa') }}
    where taxon_name is not null
),

past_studies as (
    select
        'new_study' as event_type,
        cast(null as varchar) as subject_name,
        cast(null as varchar) as related_name,
        coalesce('doi:' || primary_doi, 'research:' || research_id) as study_id,
        research_id,
        page_year as event_year,
        cast(null as varchar) as attribution,
        page_title as source_title,
        case when primary_doi is not null then 1 else 2 end as source_rank,
        list_distinct(list_concat(linked_terms, unlinked_names, candidate_taxa)) as shown_on
    from {{ ref('stg_wikipedia_past__research') }}
),

events as (
    select * from opinion_events
    union all select * from past_descriptions
    union all select * from past_studies
),

placed as (
    -- Each name is shown on its own page and, for a species, on its genus page.
    select
        e.*,
        k.taxon_key
    from events as e,
        lateral (
            select distinct unnest([
                {{ taxon_key('n.name') }},
                case when n.name like '% %' then {{ taxon_key("split_part(n.name, ' ', 1)") }} end
            ]) as taxon_key
            from (select unnest(e.shown_on) as name) as n
        ) as k
    where k.taxon_key in (select taxon_key from pages)
)

select
    taxon_key,
    event_type,
    study_id,
    research_id,
    make_date(event_year, 1, 1) as event_date,
    false as date_is_publication,
    'year' as date_precision,
    cast(null as varchar) as change_id,
    cast(null as varchar[]) as changed_fields,
    -- The name concerned, left out when it is the page's own taxon.
    case when {{ taxon_key('subject_name') }} <> taxon_key then subject_name end as subject_name,
    related_name,
    attribution,
    source_title,
    source_rank,
    'backfill' as origin
from placed
where event_year between 1750 and year(current_date)
