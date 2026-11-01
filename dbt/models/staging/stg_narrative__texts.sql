-- Verified narrative texts, one row per taxon and language.
select
    taxon_key || ':' || lang as text_key,
    taxon_key,
    lang,
    status,
    generator,
    prompt_version,
    facts_hash,
    generated_at,
    word_count,
    sections
from {{ read_narrative('texts') }}
