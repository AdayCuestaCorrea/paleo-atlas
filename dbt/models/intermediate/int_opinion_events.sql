-- History events from PBDB's taxonomic opinions (ALCANCE.md §9, Phase 3 H4), one row
-- per name and event, before they are placed on pages (int_backfill_events).
-- PBDB lists one opinion for every author who used a name, and authors disagree for
-- decades (Brontosaurus: a synonym of Apatosaurus from 1903, of Camarasaurus in 1927,
-- valid again in 2015). So an event is the FIRST opinion that gives a name a new
-- status (synonym of X, nomen dubium, replaced by X, moved to genus X), plus
-- "revalidated" when PBDB's current classification accepts again a name that earlier
-- opinions had sunk. A plain "belongs to" is never an event.
with opinions as (
    select
        *,
        try_cast(split_part(opinion_id, ':', 2) as bigint) as opinion_no
    from {{ ref('stg_pbdb__opinions') }}
    where opinion_year is not null and taxon_rank in ('genus', 'species')
),

classified as (
    select
        *,
        case
            when status in ('subjective synonym of', 'objective synonym of') then 'synonymized'
            when status = 'replaced by' then 'replaced'
            when status in ('nomen dubium', 'nomen nudum', 'nomen vanum', 'nomen oblitum')
                then 'invalidated'
            when spelling_reason = 'recombination' and taxon_rank = 'species' then 'recombined'
        end as event_type
    from opinions
),

status_changes as (
    select
        pbdb_taxon_no,
        taxon_name as subject_name,
        taxon_rank,
        event_type,
        -- The senior synonym, the replacement name, the kind of nomen or the new genus.
        case when event_type = 'invalidated' then status else parent_name end as related_name,
        opinion_author,
        opinion_year,
        reference_id
    from classified
    where event_type is not null
    qualify row_number() over (
        partition by pbdb_taxon_no, event_type,
            case when event_type = 'invalidated' then status else parent_name end
        order by opinion_year, opinion_no
    ) = 1
),

revalidated as (
    select
        c.pbdb_taxon_no,
        c.taxon_name as subject_name,
        c.taxon_rank,
        'revalidated' as event_type,
        cast(null as varchar) as related_name,
        c.opinion_author,
        c.opinion_year,
        c.reference_id
    from opinions as c
    where c.is_current_classification
      and c.status = 'belongs to'
      and exists (
          select 1
          from classified as e
          where e.pbdb_taxon_no = c.pbdb_taxon_no
            and e.event_type in ('synonymized', 'replaced', 'invalidated')
            and e.opinion_year < c.opinion_year
      )
),

descriptions as (
    -- The earliest opinion with the original spelling: the naming publication.
    select
        pbdb_taxon_no,
        taxon_name as subject_name,
        taxon_rank,
        'description' as event_type,
        cast(null as varchar) as related_name,
        opinion_author,
        opinion_year,
        reference_id
    from opinions
    where spelling_reason = 'original spelling'
    qualify row_number() over (partition by pbdb_taxon_no order by opinion_year, opinion_no) = 1
)

select
    e.*,
    coalesce('doi:' || r.doi, 'pbdb:' || e.reference_id) as study_id,
    r.title as reference_title,
    r.journal as reference_journal,
    r.doi as reference_doi
from (
    select * from status_changes
    union all select * from revalidated
    union all select * from descriptions
) as e
left join {{ ref('stg_pbdb__refs') }} as r using (reference_id)
