-- Every published sentence cites at least one fact that exists (ALCANCE.md §16).
-- Texts whose facts were extracted again are held back by fct_taxon_text (see
-- assert_texts_waiting_for_rewrite); what reaches the site must cite real facts.
with sentences as (
    select t.taxon_key, t.lang, s.value as sentence
    from {{ ref('fct_taxon_text') }} as t
    cross join json_each(t.sections) as sec
    cross join json_each(sec.value -> 'sentences') as s
    where t.text_status = 'verified'
),

cited as (
    select taxon_key, lang, sentence ->> 'text' as text, unnest(
        coalesce(json_extract_string(sentence, '$.fact_ids[*]'), ['__none__'])
    ) as fact_id
    from sentences
)

select c.taxon_key, c.lang, c.text, c.fact_id
from cited as c
left join {{ ref('stg_narrative__facts') }} as f
    on f.taxon_key = c.taxon_key and f.fact_id = c.fact_id
where f.fact_id is null
