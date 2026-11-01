-- One row per study listed under the "… research" headings of each yearly page.
-- `text_internal` is Wikipedia prose (CC BY-SA 4.0): input for fact extraction
-- only, never published (ALCANCE.md §19).
with source as (
    select * from {{ read_wikipedia_interim('research') }}
    {{ latest_revision_only('revid', 'page_title') }}
)

select
    research_id,
    page_title,
    revid,
    cast(regexp_extract(page_title, '^(\d{4})', 1) as integer) as page_year,
    {{ wikipedia_block('page_title') }} as taxonomic_block,
    {{ wikipedia_group('section_path') }} as taxon_group,
    section_path,
    section_path[len(section_path)] as research_topic,
    italic_links as candidate_taxa,
    links as linked_terms,
    "references" as study_references,
    list_filter("references", lambda r: r.doi is not null)[1].doi as primary_doi,
    "references"[1].title as study_title,
    "references"[1].venue as study_venue,
    "references"[1].year as study_year,
    len("references") as reference_count,
    text as text_internal,
    parse_warnings,
    len(parse_warnings) as parse_warning_count
from source
