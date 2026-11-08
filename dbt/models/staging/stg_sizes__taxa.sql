-- Adult body length of each taxon read from its verified facts (paleo sizes extract):
-- the main estimate, the span of every estimate and the estimates themselves (JSON,
-- main first, each with its sentence, quote and source).
select
    taxon_key,
    min_m,
    max_m,
    qualifier,
    main_fact_id,
    span_min_m,
    span_max_m,
    coalesce(partial_remains, false) as partial_remains,
    coalesce(only_old_estimates, false) as only_old_estimates,
    estimates
from {{ read_narrative('sizes') }}
