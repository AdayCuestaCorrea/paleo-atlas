-- Which taxon pages each news article is about (Phase 5). Two ways, both checked
-- against the encyclopedia:
--   * text: the page's scientific name appears as a whole word in the headline or the
--     summary (case-sensitive: a genus is always capitalized), for names of 5 letters
--     or more (Jian, Mei or Yi are also people's names: those need the LLM); or a
--     common name of the seed taxon_aliases (megalodon -> Otodus), in any case;
--   * llm: a name the model read in the article (paleo news classify), kept only if
--     it is a page (or its genus is: a genus page or a new genus with a page of its
--     own) and the article really names it: its genus, or the abbreviation "T. rex"
--     of the species.
-- A species without a page of its own links to its genus. When the LLM confirmed the
-- page an article is about, the pages found only in the text are dropped: they are
-- animals mentioned in passing ("a close cousin of Velociraptor").
with articles as (
    select news_key, title || coalesce(' ' || summary, '') as text
    from {{ ref('stg_news__items') }}
),

pages as (
    select taxon_key, taxon_name, page_type
    from {{ ref('dim_taxon') }}
),

aliases as (
    select a.alias, p.taxon_key, p.taxon_name
    from {{ ref('taxon_aliases') }} as a
    inner join pages as p using (taxon_name)
),

by_text as (
    select a.news_key, p.taxon_key, 'text' as matched_by
    from articles as a
    inner join pages as p
        on length(p.taxon_name) >= 5
        and contains(a.text, p.taxon_name)
        and regexp_matches(a.text, '(^|[^A-Za-z])' || p.taxon_name || '($|[^A-Za-z])')
    union all
    select a.news_key, al.taxon_key, 'text' as matched_by
    from articles as a
    inner join aliases as al
        on regexp_matches(a.text, '(^|[^[:alpha:]])' || al.alias || '($|[^[:alpha:]])', 'i')
),

llm_names as (
    select l.news_key, a.text, coalesce(al.taxon_name, n.name) as name
    from {{ ref('stg_news__labels') }} as l
    inner join articles as a using (news_key)
    cross join lateral (select trim(unnest(l.llm_taxa)) as name) as n
    left join aliases as al on lower(al.alias) = lower(n.name)
),

by_llm as (
    select n.news_key, coalesce(exact.taxon_key, genus.taxon_key) as taxon_key, 'llm' as matched_by
    from llm_names as n
    left join pages as exact on lower(exact.taxon_name) = lower(n.name)
    left join pages as genus
        on genus.page_type in ('genus', 'new')
        and not contains(genus.taxon_name, ' ')
        and lower(genus.taxon_name) = lower(split_part(n.name, ' ', 1))
    where coalesce(exact.taxon_key, genus.taxon_key) is not null
        and (
            contains(lower(n.text), lower(split_part(n.name, ' ', 1)))
            or (split_part(n.name, ' ', 2) <> ''
                and contains(n.text, left(n.name, 1) || '. ' || split_part(n.name, ' ', 2)))
            or exists (
                select 1 from aliases as al
                where al.taxon_name = n.name
                    and contains(lower(n.text), lower(al.alias))
            )
        )
),

matched as (
    select news_key, taxon_key, list_sort(list(distinct matched_by)) as matched_by
    from (select * from by_text union all select * from by_llm)
    group by news_key, taxon_key
)

select news_key, taxon_key, matched_by
from matched as m
where list_contains(m.matched_by, 'llm')
    or not exists (
        select 1 from matched as o
        where o.news_key = m.news_key and list_contains(o.matched_by, 'llm')
    )
