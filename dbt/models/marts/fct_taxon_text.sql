-- Narrative text of each taxon page per language (ALCANCE.md §12.1).
-- `text_status`: verified (published) or pending (the site shows the fallback
-- template text, §11.4). Every new taxon gets one row per language, and so does
-- every genus page with a Wikipedia article (Phase 3: the only genera that get a text).
with pages as (
    select taxon_key, taxon_name from {{ ref('dim_taxon') }}
    where page_type = 'new' or (page_type = 'genus' and wikipedia_article is not null)
),

langs as (
    select unnest(['en', 'es']) as lang
),

texts as (
    select * from {{ ref('stg_narrative__texts') }} where status = 'verified'
)

select
    p.taxon_key || ':' || l.lang as text_key,
    p.taxon_key,
    p.taxon_name,
    l.lang,
    case when t.taxon_key is null then 'pending' else 'verified' end as text_status,
    t.generator,
    t.prompt_version,
    t.generated_at,
    t.word_count,
    t.sections
from pages as p
cross join langs as l
left join texts as t on t.taxon_key = p.taxon_key and t.lang = l.lang
