-- One row per study (naming studies of new taxa and research items) with the
-- verifiable reliability signals shown as badges (ALCANCE.md §10).
with naming as (
    select
        coalesce('doi:' || primary_doi, 'naming:' || {{ taxon_key('taxon_name') }}) as study_id,
        primary_doi as doi,
        study_title as wiki_title,
        study_venue as wiki_venue,
        study_year as wiki_year,
        "study_references"[1].template as citation_template,
        revision_timestamp as seen_at
    from {{ ref('stg_wikipedia__new_taxa_revisions') }}
),

research as (
    select
        coalesce('doi:' || primary_doi, 'research:' || research_id) as study_id,
        primary_doi as doi,
        study_title,
        study_venue,
        study_year,
        "study_references"[1].template,
        revision_timestamp
    from {{ ref('stg_wikipedia__research_revisions') }}
),

studies as (
    select
        study_id,
        any_value(doi) as doi,
        any_value(wiki_title) as wiki_title,
        any_value(wiki_venue) as wiki_venue,
        any_value(wiki_year) as wiki_year,
        any_value(citation_template) as citation_template,
        min(seen_at) as first_seen_at
    from (select * from naming union all select * from research)
    group by study_id
),

crossref as (
    select
        *,
        coalesce(json_extract_string(updated_by, '$[*].type'), []) as update_types,
        cast(left(list_max(json_extract_string(updated_by, '$[*].updated.date-time')), 10) as date)
            as last_updated_on
    from {{ ref('stg_crossref__works') }}
)

select
    s.study_id,
    s.doi,
    coalesce(c.title, s.wiki_title) as title,
    coalesce(c.journal, s.wiki_venue) as journal,
    coalesce(c.issued_year, s.wiki_year) as publication_year,
    c.issued_on,
    c.issued_precision,
    c.last_updated_on,
    s.first_seen_at,
    c.work_type,
    c.language,
    s.doi is not null as has_doi,
    coalesce(c.found_in_crossref, false) as found_in_crossref,
    coalesce(c.work_type = 'journal-article' and len(c.issns) > 0, false) as is_peer_reviewed_journal,
    coalesce(
        c.work_type = 'posted-content'
        or s.citation_template ilike '%rxiv%'
        or coalesce(c.journal, s.wiki_venue) ilike '%rxiv%',
        false
    ) as is_preprint,
    list_has_any(c.update_types, ['retraction', 'withdrawal', 'removal']) as is_retracted,
    list_has_any(c.update_types, ['correction', 'erratum', 'corrigendum']) as is_corrected,
    lower(coalesce(c.journal, s.wiki_venue)) in (
        select lower(journal) from {{ ref('trusted_journals') }}
    ) as in_trusted_journal,
    coalesce(list_has_any(
        list_transform(c.issns, lambda x: upper(x)),
        (select coalesce(list(issn), []) from {{ ref('stg_doaj__journals') }} where listed_in_doaj)
    ), false) as in_doaj,
    case
        when list_has_any(c.update_types, ['retraction', 'withdrawal', 'removal']) then 'retracted'
        when c.work_type = 'posted-content' or s.citation_template ilike '%rxiv%' then 'preprint'
        when c.work_type = 'journal-article' and len(c.issns) > 0 then 'peer_reviewed'
        else 'unverified'
    end as reliability_status
from studies as s
left join crossref as c on c.doi = s.doi
