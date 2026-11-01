-- The image shown on each taxon page: an allowed license only; the most precise
-- level first (taxon > genus > clade); Commons before PhyloPic at the same level.
select *
from {{ ref('int_image_candidates') }}
where license_allowed
qualify row_number() over (
    partition by taxon_key
    order by
        case image_level when 'taxon' then 1 when 'genus' then 2 else 3 end,
        case image_source when 'commons' then 1 else 2 end,
        clade_position,
        image_ref
) = 1
