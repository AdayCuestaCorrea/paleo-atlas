-- Facts accepted and rejected by the deterministic checks, per taxon (paleo facts).
-- Published on "How we assess sources" (ALCANCE.md §12.1, step 6, and §17).
select
    taxon_key,
    coalesce(json_array_length(facts), 0) as facts_accepted,
    coalesce(json_array_length(rejected), 0) as facts_rejected
from {{ read_narrative('facts') }}
