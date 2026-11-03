-- Studies cited only by the history backwards (Phase 3 H4): PBDB references and the
-- studies of past yearly pages. They are not looked up in Crossref (that would mean
-- ~10,000 more records in git), so their reliability is 'unchecked' and the site
-- shows no badge for them; "How we assess sources" says so.
with cited as (
    select distinct study_id from {{ ref('int_backfill_events') }}
),

described as (
    select study_id, reference_doi as doi, reference_title as title,
        reference_journal as journal, opinion_year as publication_year
    from {{ ref('int_opinion_events') }}
    union all
    select coalesce('doi:' || primary_doi, 'wikipast:' || md5(new_taxon_id)),
        primary_doi, study_title, study_venue, coalesce(study_year, page_year)
    from {{ ref('stg_wikipedia_past__new_taxa') }}
    union all
    select coalesce('doi:' || primary_doi, 'research:' || research_id),
        primary_doi, study_title, study_venue, coalesce(study_year, page_year)
    from {{ ref('stg_wikipedia_past__research') }}
)

select
    c.study_id,
    any_value(d.doi) as doi,
    any_value(d.title) as title,
    any_value(d.journal) as journal,
    min(d.publication_year) as publication_year
from cited as c
inner join described as d using (study_id)
where c.study_id not in (select study_id from {{ ref('int_study_reliability') }})
group by c.study_id
