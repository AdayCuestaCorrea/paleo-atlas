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

verified as (
    select * from {{ ref('stg_narrative__texts') }} where status = 'verified'
),

broken as (
    -- A text written from facts that were extracted again (Groq re-extracts the facts
    -- first and may run out of quota before the text): if any sentence cites a fact
    -- that no longer exists, the page shows the fallback until the text is rewritten.
    select distinct v.taxon_key, v.lang
    from verified as v
    cross join json_each(v.sections) as sec
    cross join json_each(sec.value -> 'sentences') as s
    cross join unnest(
        coalesce(json_extract_string(s.value, '$.fact_ids[*]'), ['__none__'])
    ) as c (fact_id)
    left join {{ ref('stg_narrative__facts') }} as f
        on f.taxon_key = v.taxon_key and f.fact_id = c.fact_id
    where f.fact_id is null
),

texts as (
    select v.* from verified as v
    anti join broken as b on b.taxon_key = v.taxon_key and b.lang = v.lang
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
