-- The LLM's category and scientific names for each news article (paleo news classify).
-- An empty array is an article that names no taxon.
select
    key as news_key,
    category,
    coalesce(taxa, []) as llm_taxa,
    input_hash,
    generator,
    prompt_version,
    classified_at
from {{ read_narrative('news_labels') }}
