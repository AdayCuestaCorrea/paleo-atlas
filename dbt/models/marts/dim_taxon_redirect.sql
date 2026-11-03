-- Old page URLs that now redirect to another page: known species folded into the
-- encyclopedia page of their genus (int_folded_species). The site writes a small
-- redirect page at each old URL so links from "Latest" and the recaps keep working.
select
    f.species_key as from_key,
    f.genus_key as to_key,
    f.species_name as subject_name
from {{ ref('int_folded_species') }} as f
inner join {{ ref('int_taxon_pages') }} as p on p.taxon_key = f.genus_key
