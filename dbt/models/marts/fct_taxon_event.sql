-- Timeline of every taxon page, newest first within each taxon.
select
    e.event_id,
    e.taxon_key,
    e.event_type,
    e.event_date,
    -- false: no publication date known, event_date is when we first saw it
    e.date_is_publication,
    -- day | month | year (publication date precision) or seen (first seen by us)
    e.date_precision,
    e.study_id,
    e.research_id,
    s.reliability_status,
    s.title as study_title,
    s.journal as study_journal
from {{ ref('int_taxon_events') }} as e
left join {{ ref('dim_study') }} as s using (study_id)
