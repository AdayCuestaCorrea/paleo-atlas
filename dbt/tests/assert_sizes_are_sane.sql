-- Every size the comparator shows is a positive length, min <= max, no longer than any
-- animal ever described (60 m), and the span of the estimates contains the main one.
select taxon_key, min_m, max_m, span_min_m, span_max_m
from {{ ref('fct_taxon_size') }}
where min_m is null or max_m is null
   or min_m <= 0 or min_m > max_m or max_m > 60
   or span_min_m > min_m or span_max_m < max_m
