-- History events from PBDB's taxonomic opinions (ALCANCE.md §9, Phase 3 H4), one row
-- per name and event, before they are placed on pages (int_backfill_events).
-- PBDB lists one opinion for every author who used a name, and authors disagree for
-- decades (Brontosaurus: a synonym of Apatosaurus from 1903, of Camarasaurus in 1927,
-- valid again in 2015). So an event is the FIRST opinion that gives a name a new
-- status (synonym of X, nomen dubium, replaced by X, moved to genus X), plus
-- "revalidated" when PBDB's current classification accepts again a name that earlier
-- opinions had sunk. A plain "belongs to" is never an event.
--
-- Phase 7 (a review of 15 pages): a negative opinion that PBDB's current
-- classification does not follow and that came after it is left out (Stegosaurus
-- stenops, conserved by the ICZN in 2013, "nomen dubium" in 2017); "revalidated" is
-- dated by the first opinion that accepts the name again after the last negative one,
-- not by whichever paper PBDB's current classification cites; a reference is only
-- attached when its year is the opinion's (PBDB files some opinions under a later
-- work that cites them: Gilmore 1931 under Galton and Sues 1983); and the references
-- of the seed opinion_exclusions (reports outside peer review) give no events.
with opinions as (
    select
        *,
        try_cast(split_part(opinion_id, ':', 2) as bigint) as opinion_no
    from {{ ref('stg_pbdb__opinions') }}
    where opinion_year is not null and taxon_rank in ('genus', 'species')
      and reference_id not in (select reference_id from {{ ref('opinion_exclusions') }})
),

current_year as (
    select pbdb_taxon_no, max(opinion_year) as current_year
    from opinions
    where is_current_classification and status = 'belongs to'
    group by pbdb_taxon_no
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
    left join current_year using (pbdb_taxon_no)
    where event_type is not null
      and (current_year is null or event_type = 'recombined' or opinion_year <= current_year)
    qualify row_number() over (
        partition by pbdb_taxon_no, event_type,
            case when event_type = 'invalidated' then status else parent_name end
        order by opinion_year, opinion_no
    ) = 1
),

last_negative as (
    -- Negative opinions after the current classification are left out (above).
    select pbdb_taxon_no, max(opinion_year) as negative_year
    from classified
    inner join current_year using (pbdb_taxon_no)
    where event_type in ('synonymized', 'replaced', 'invalidated')
      and opinion_year <= current_year
    group by pbdb_taxon_no
),

revalidated as (
    -- Only names PBDB accepts today, after a negative opinion. Dated by PBDB's current
    -- classification when at most one other acceptance lies in between (Brontosaurus:
    -- Romer 1966, then Tschopp et al. 2015); when several do, the name was back in use
    -- long before, so by the first acceptance after the last negative opinion
    -- (Ankylosaurus: a synonym of Euoplocephalus until 1966, not "valid again" in 2017).
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
    inner join last_negative as n using (pbdb_taxon_no)
    inner join current_year as cy using (pbdb_taxon_no)
    cross join lateral (
        select count(*) as between_n from opinions as b
        where b.pbdb_taxon_no = c.pbdb_taxon_no and b.status = 'belongs to'
          and b.opinion_year > n.negative_year and b.opinion_year < cy.current_year
    ) as k
    where c.status = 'belongs to'
      and c.opinion_year > n.negative_year
      and (
          (k.between_n <= 1 and c.is_current_classification)
          or (k.between_n > 1 and not c.is_current_classification)
      )
    qualify row_number() over (partition by c.pbdb_taxon_no order by c.opinion_year, c.opinion_no) = 1
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
    case
        when r.publication_year is null or abs(r.publication_year - e.opinion_year) <= 1
            then coalesce('doi:' || r.doi, 'pbdb:' || e.reference_id)
        else 'pbdbop:' || e.pbdb_taxon_no || ':' || e.event_type || ':' || e.opinion_year
    end as study_id,
    case when ref_ok then r.title end as reference_title,
    case when ref_ok then r.journal end as reference_journal,
    case when ref_ok then r.doi end as reference_doi
from (
    select * from status_changes
    union all select * from revalidated
    union all select * from descriptions
) as e
left join {{ ref('stg_pbdb__refs') }} as r using (reference_id)
cross join lateral (
    select r.publication_year is null or abs(r.publication_year - e.opinion_year) <= 1 as ref_ok
)
