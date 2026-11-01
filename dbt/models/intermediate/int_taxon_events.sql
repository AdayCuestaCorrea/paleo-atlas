-- Timeline events for every taxon page (ALCANCE.md §9).
with pages as (
    select taxon_key from {{ ref('int_taxon_pages') }}
),

studies as (
    select * from {{ ref('int_study_reliability') }}
),

descriptions as (
    select
        n.taxon_key,
        'description' as event_type,
        s.study_id,
        cast(null as varchar) as research_id,
        coalesce(s.issued_on, cast(n.first_seen_at as date)) as event_date,
        s.issued_on is not null as date_is_publication,
        coalesce(s.issued_precision, 'seen') as date_precision
    from (
        select
            {{ taxon_key('taxon_name') }} as taxon_key,
            coalesce('doi:' || primary_doi, 'naming:' || {{ taxon_key('taxon_name') }}) as study_id,
            min(revision_timestamp) as first_seen_at
        from {{ ref('stg_wikipedia__new_taxa_revisions') }}
        group by all
    ) as n
    inner join studies as s using (study_id)
),

new_studies as (
    select
        l.taxon_key,
        'new_study' as event_type,
        s.study_id,
        r.research_id,
        coalesce(s.issued_on, cast(r.revision_timestamp as date)) as event_date,
        s.issued_on is not null as date_is_publication,
        coalesce(s.issued_precision, 'seen') as date_precision
    from {{ ref('int_research_taxon_links') }} as l
    inner join {{ ref('stg_wikipedia__research_items') }} as r using (research_id)
    inner join studies as s
        on s.study_id = coalesce('doi:' || r.primary_doi, 'research:' || r.research_id)
),

base as (
    select * from descriptions
    union all
    select * from new_studies
),

updates as (
    -- A correction or retraction of a study becomes an event on every taxon it concerns.
    select
        b.taxon_key,
        case when s.is_retracted then 'study_retracted' else 'study_corrected' end as event_type,
        b.study_id,
        b.research_id,
        s.last_updated_on as event_date,
        s.last_updated_on is not null as date_is_publication,
        'day' as date_precision
    from base as b
    inner join studies as s using (study_id)
    where s.is_retracted or s.is_corrected
)

select
    md5(concat_ws('|', taxon_key, event_type, study_id)) as event_id,
    e.*
from (select * from base union all select * from updates) as e
where taxon_key in (select taxon_key from pages)
qualify row_number() over (partition by taxon_key, event_type, study_id order by event_date) = 1
