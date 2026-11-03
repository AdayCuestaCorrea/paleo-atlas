-- One row per study with its reliability badges (ALCANCE.md §10). The studies cited
-- only by the history backwards are 'unchecked' (int_backfill_studies).
select * from {{ ref('int_study_reliability') }}
union all by name
select
    study_id,
    doi,
    title,
    journal,
    publication_year,
    doi is not null as has_doi,
    false as found_in_crossref,
    false as is_peer_reviewed_journal,
    false as is_preprint,
    false as is_retracted,
    false as is_corrected,
    lower(journal) in (select lower(journal) from {{ ref('trusted_journals') }}) as in_trusted_journal,
    false as in_doaj,
    'unchecked' as reliability_status
from {{ ref('int_backfill_studies') }}
