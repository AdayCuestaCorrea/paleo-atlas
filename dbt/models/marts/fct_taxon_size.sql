-- Size of a taxon page for the comparator (ALCANCE.md §11.3): only a length a verified
-- fact states (never invented), with the silhouette to draw it. A taxon without an
-- allowed silhouette keeps its size (shown as text) but is not drawn.
select
    s.taxon_key,
    t.taxon_name,
    s.min_m,
    s.max_m,
    s.qualifier,
    s.main_fact_id,
    s.span_min_m,
    s.span_max_m,
    s.partial_remains,
    s.only_old_estimates,
    s.estimates,
    json_array_length(s.estimates) as estimate_count,
    sil.silhouette_level,
    sil.silhouette_node,
    sil.image_uuid as silhouette_uuid,
    sil.vector_url as silhouette_url,
    sil.source_page_url as silhouette_page_url,
    sil.author as silhouette_author,
    sil.license_id as silhouette_license_id,
    sil.license_label as silhouette_license,
    sil.license_url as silhouette_license_url,
    sil.aspect as silhouette_aspect,
    sil.vector_url is not null as in_comparator
from {{ ref('stg_sizes__taxa') }} as s
inner join {{ ref('dim_taxon') }} as t using (taxon_key)
left join {{ ref('int_silhouette_best_per_taxon') }} as sil using (taxon_key)
