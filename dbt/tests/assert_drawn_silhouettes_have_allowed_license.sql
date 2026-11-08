-- The comparator only draws silhouettes with an allowed license (ALCANCE.md §19).
select s.taxon_key, s.silhouette_license_id
from {{ ref('fct_taxon_size') }} as s
left join {{ ref('license_allowlist') }} as a on a.license_id = s.silhouette_license_id
where s.in_comparator and not coalesce(a.allowed, false)
