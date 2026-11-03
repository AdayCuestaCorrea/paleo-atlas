-- PBDB's parent links must end at the root: a chain that reaches the recursion limit
-- of int_genus_lineage (depth 100) means a cycle.
select taxon_key, max(depth) as depth
from {{ ref('int_genus_lineage') }}
group by taxon_key
having max(depth) >= 99
