-- Genus names that PBDB uses in two blocks of the scope (homonyms): only the first
-- block gets the page (int_catalog_genera). A warning, so each one is seen.
{{ config(severity = 'warn') }}

select lower(c.pbdb_name) as genus_name, list(distinct s.block order by s.block) as blocks
from {{ ref('stg_pbdb__catalog') }} as c
inner join {{ ref('scope_clades') }} as s on s.pbdb_base_name = c.base_name
where c.taxon_rank = 'genus' and s.enabled
group by 1
having count(distinct s.block) > 1
