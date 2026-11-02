-- One row per new taxon and stored revision of each yearly page (input for history).
with source as (
    select * from {{ read_wikipedia_interim('new_taxa') }}
),

cleaned as (
    select
        page_title || ' | ' || trim(name) as new_taxon_id,
        page_title,
        revid,
        revision_timestamp,
        cast(regexp_extract(page_title, '^(\d{4})', 1) as integer) as page_year,
        {{ wikipedia_block('page_title') }} as taxonomic_block,
        {{ wikipedia_group('section_path') }} as taxon_group,
        section_path,
        table_index,
        row_index,
        trim(name) as taxon_name,
        name_link as wikipedia_article,
        novelty as novelty_raw,
        case regexp_replace(lower(coalesce(novelty, '')), '[^a-z]', '', 'g')
            when 'genetspnov' then 'new_genus_and_species'
            when 'spnov' then 'new_species'
            when 'genetcombnov' then 'new_genus_new_combination'
            when 'gennov' then 'new_genus'
            when 'combnov' then 'new_combination'
            when 'sspnov' then 'new_subspecies'
            when 'nomnov' then 'replacement_name'
            when '' then 'unspecified'
            else 'other'
        end as novelty,
        status as status_raw,
        case
            when status is null or trim(status) in ('', '-', '–', '—') then 'unspecified'
            when lower(status) = 'valid' then 'valid'
            when lower(status) like 'in press%' then 'in_press'
            when lower(status) like '%disputed%' then 'disputed'
            when lower(status) like '%nomen nudum%' then 'nomen_nudum'
            when lower(status) like '%preprint%' then 'preprint'
            when lower(status) like '%junior synonym%' then 'junior_synonym'
            else 'other'
        end as status,
        authors as name_authors,
        age as age_text,
        age_links as age_terms,
        type_locality,
        countries,
        countries[1] as country,
        regions,
        notes as notes_text,
        note_links as notes_terms,
        images as image_files,
        "references" as study_references,
        list_filter("references", lambda r: r.doi is not null)[1].doi as primary_doi,
        "references"[1].title as study_title,
        "references"[1].venue as study_venue,
        "references"[1].year as study_year,
        len("references") as reference_count,
        parse_warnings,
        len(parse_warnings) as parse_warning_count
    from source
),

-- Rows outside the scope of §4 (turtles, lizards, most bony fishes…) never enter.
scoped as (
    select
        * replace (
            {{ wikipedia_in_scope(
                'taxonomic_block', 'taxon_group',
                "split_part(taxon_name, ' ', 1) in (select genus from " ~ ref('featured_fishes') ~ ")",
                "coalesce(notes_text, '') || ' ' || array_to_string(coalesce(notes_terms, []), ' ')"
            ) }} as taxon_group
        )
    from cleaned
)

select * from scoped where taxon_group is not null
