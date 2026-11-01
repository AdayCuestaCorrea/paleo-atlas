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
    revision_timestamp as valid_from,
    lead(revision_timestamp) over (partition by new_taxon_id order by revid) as valid_to,
    lead(revision_timestamp) over (partition by new_taxon_id order by revid) is null as is_current,
    row_number() over (partition by new_taxon_id order by revid) as version_number
from changes
