-- Timeline of every taxon page, newest first within each taxon.
select
    e.event_id,
    e.taxon_key,
    e.event_type,
    e.event_date,
    e.study_id,
    e.research_id,
    s.reliability_status,
    s.title as study_title,
    s.journal as study_journal
from {{ ref('int_taxon_events') }} as e
left join {{ ref('dim_study') }} as s using (study_id)
