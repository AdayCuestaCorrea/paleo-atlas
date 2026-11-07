-- One row per news article (Phase 5): outlet, language, headline, link, date, the
-- feed's summary where allowed, the LLM's category (null until classified) and the
-- taxon pages it is about.
with taxa as (
    select news_key, list(taxon_key order by taxon_key) as taxon_keys
    from {{ ref('int_news_taxa') }}
    group by news_key
)

select
    i.news_key,
    i.outlet,
    i.lang,
    i.title,
    i.url,
    i.published_at,
    i.summary,
    l.category,
    l.generator,
    l.prompt_version,
    coalesce(t.taxon_keys, []) as taxon_keys
from {{ ref('stg_news__items') }} as i
left join {{ ref('stg_news__labels') }} as l using (news_key)
left join taxa as t using (news_key)
