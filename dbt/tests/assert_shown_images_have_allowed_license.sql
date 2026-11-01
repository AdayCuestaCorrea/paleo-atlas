-- No taxon page may show an image whose license is not on the allowlist (§19).
select d.taxon_key, d.image_license_id
from {{ ref('dim_taxon') }} as d
left join {{ ref('license_allowlist') }} as a on a.license_id = d.image_license_id
where d.image_url is not null
  and not coalesce(a.allowed, false)
