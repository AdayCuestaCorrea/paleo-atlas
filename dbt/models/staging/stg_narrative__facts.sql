-- One row per verified fact, with the citation of the chunk it comes from.
-- Quotes from copyrighted abstracts are null here (kept only in the local cache).
with docs as (
    select * from {{ read_narrative('facts') }}
),

facts as (
    select
        d.taxon_key,
        d.generator,
        d.prompt_version,
        f.value as fact
    from docs as d
    cross join json_each(d.facts) as f
)

select
    taxon_key || ':' || (fact ->> 'fact_id') as fact_key,
    taxon_key,
    fact ->> 'fact_id' as fact_id,
    fact ->> 'statement' as statement,
    fact ->> 'category' as category,
    fact ->> 'chunk_id' as chunk_id,
    fact ->> 'lang' as source_lang,
    fact ->> 'quote' as public_quote,
    generator,
    prompt_version
from facts
