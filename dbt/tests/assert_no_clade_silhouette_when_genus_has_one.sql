-- No taxon of the size comparator is drawn with a relative's or a clade's silhouette
-- while PhyloPic has an allowed, usable one of its own genus (the v42/v44/v47 lesson:
-- check every taxon, not only the ones that changed). The PhyloPic lookup of a genus
-- also takes its species' nodes ("Acrocanthosaurus atokensis"), so their images are
-- stored under the genus name.
select s.taxon_key, s.silhouette_level, s.silhouette_node, i.image_uuid
from {{ ref('fct_taxon_size') }} as s
inner join {{ ref('dim_taxon') }} as t using (taxon_key)
inner join {{ ref('stg_phylopic__node_images') }} as i
    on i.queried_name = coalesce(t.genus_name, split_part(t.taxon_name, ' ', 1))
inner join {{ ref('license_allowlist') }} as a
    on a.license_id = i.license_id_raw and a.allowed
where coalesce(s.silhouette_level, 'none') not in ('taxon', 'genus')
  and t.taxon_group <> 'pterosaurs'
  and i.vector_url is not null
  and i.raster_url is not null
  and i.image_uuid not in (select image_uuid from {{ ref('silhouette_exclusions') }})
  and split_part(coalesce(i.image_node, i.queried_name), ' ', 1) = split_part(i.queried_name, ' ', 1)
  and (i.synonym_of is null or list_contains(t.species_names, i.image_node))
