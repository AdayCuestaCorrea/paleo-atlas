-- Every ancestor clade of each genus of the catalog (§11.2, Phase 3 H7): the closure
-- of PBDB's parent links, depth 1 = the parent. PBDB's classification is a
-- classification, not a phylogenetic analysis (the site says so).
with recursive genera as (
    select taxon_key, taxon_name, parent_no from {{ ref('int_catalog_genera') }}
    where parent_no is not null
),

clades as (
    select * from {{ ref('stg_pbdb__clades') }}
),

chain(taxon_key, clade_no, depth) as (
    select taxon_key, parent_no, 1 from genera
    union all
    select c.taxon_key, k.parent_no, c.depth + 1
    from chain as c
    inner join clades as k on k.clade_no = c.clade_no
    where k.parent_no is not null and c.depth < 100
)

select
    c.taxon_key,
    c.clade_no,
    k.clade_name,
    k.clade_rank,
    c.depth
from chain as c
inner join clades as k on k.clade_no = c.clade_no
