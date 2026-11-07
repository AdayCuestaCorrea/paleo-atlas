-- One definition per glossary term and language (paleo glossary write), with the
-- Wikipedia revision it was written from and whether it passed every check. Rejected
-- ones are kept to count them; only verified ones are published.
select
    term_id || '.' || lang as definition_key,
    term_id,
    lang,
    term,
    definition,
    status,
    coalesce(problems, []) as problems,
    source.lang as source_lang,
    source.title as source_title,
    source.revid as source_revid,
    generator,
    judge,
    prompt_version,
    generated_at
from {{ read_narrative('glossary') }}
