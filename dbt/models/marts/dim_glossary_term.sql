-- The glossary (ALCANCE.md §12.2): one row per term of the seed, with its forms, how
-- many verified pages use it and its definition in each language, published only when
-- verified (written from a cited Wikipedia revision and passing every check).
with defs as (
    select * from {{ ref('stg_glossary__definitions') }} where status = 'verified'
)

select
    t.term_id,
    t.category,
    t.term_en,
    t.term_es,
    string_split(coalesce(t.forms_en, ''), '|') as forms_en,
    string_split(coalesce(t.forms_es, ''), '|') as forms_es,
    t.pages_en,
    t.pages_es,
    en.definition as definition_en,
    en.source_title as source_title_en,
    en.source_revid as source_revid_en,
    es.definition as definition_es,
    es.source_lang as source_lang_es,
    es.source_title as source_title_es,
    es.source_revid as source_revid_es,
    en.definition is not null as published_en,
    es.definition is not null as published_es
from {{ ref('glossary_terms') }} as t
left join defs as en on en.term_id = t.term_id and en.lang = 'en'
left join defs as es on es.term_id = t.term_id and es.lang = 'es'
