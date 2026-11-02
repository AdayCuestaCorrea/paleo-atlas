-- History of each new taxon's Wikipedia entry as SCD type 2, computed from every
-- stored revision (raw files are versioned in git, so this is reproducible and
-- idempotent; ALCANCE.md D9). A new version starts whenever a tracked field changes.
with revisions as (
    select
        new_taxon_id,
        {{ taxon_key('taxon_name') }} as taxon_key,
        revid,
        revision_timestamp,
        novelty,
        status,
        name_authors,
        age_text,
        type_locality,
        countries,
        notes_text,
        primary_doi,
        md5(concat_ws('|', novelty, status, name_authors, age_text, type_locality,
                      array_to_string(countries, ','), notes_text, primary_doi)) as row_hash
    from {{ ref('stg_wikipedia__new_taxa_revisions') }}
),

changes as (
    select *
    from revisions
    qualify row_hash is distinct from lag(row_hash) over (partition by new_taxon_id order by revid)
)

select
    *,
    -- Fields that changed from the previous version (empty for the first one): the
    -- "entry changed" events of the timeline (ALCANCE.md §9).
    case when lag(revid) over w is null then []::varchar[] else list_filter([
        case when novelty is distinct from lag(novelty) over w then 'novelty' end,
        case when status is distinct from lag(status) over w then 'status' end,
        case when name_authors is distinct from lag(name_authors) over w then 'authors' end,
        case when age_text is distinct from lag(age_text) over w then 'age' end,
        case when type_locality is distinct from lag(type_locality) over w then 'locality' end,
        case when countries is distinct from lag(countries) over w then 'countries' end,
        case when notes_text is distinct from lag(notes_text) over w then 'notes' end,
        case when primary_doi is distinct from lag(primary_doi) over w then 'study' end
    ], lambda x: x is not null) end as changed_fields,
    revision_timestamp as valid_from,
    lead(revision_timestamp) over (partition by new_taxon_id order by revid) as valid_to,
    lead(revision_timestamp) over (partition by new_taxon_id order by revid) is null as is_current,
    row_number() over (partition by new_taxon_id order by revid) as version_number
from changes
window w as (partition by new_taxon_id order by revid)
