-- Spanish versions of the study titles (paleo titles), one row per DOI.
-- title_source is the English title that was translated; paleo titles translates
-- again when Crossref changes it.
select
    lower(doi) as doi,
    title as title_source,
    title_es,
    generator,
    prompt_version,
    translated_at
from {{ read_narrative('study_titles') }}
