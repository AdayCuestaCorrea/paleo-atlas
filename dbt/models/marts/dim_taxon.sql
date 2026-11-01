-- One row per taxon page: the 2026 new taxa and the known taxa that 2026 studies
-- are about. This is what the site renders (ALCANCE.md §11.1).
with history as (
    select taxon_key, min(revision_timestamp) as first_seen_on_wikipedia
    from {{ ref('int_new_taxa_history') }}
    group by taxon_key
),

new_taxa as (
    select
        {{ taxon_key('taxon_name') }} as taxon_key,
        wikipedia_article,
        novelty,
        status,
        name_authors,
        age_text,
        type_locality,
        country,
        countries,
        regions,
        notes_text,
        primary_doi as naming_doi
    from {{ ref('stg_wikipedia__new_taxa') }}
),

pbdb as (
    select queried_name, first_checked_on, first_found_on from {{ ref('stg_pbdb__taxa') }}
)

select
    p.taxon_key,
    p.taxon_name,
    p.page_type,
    p.taxonomic_block,
    p.taxon_group,
    c.taxon_rank,
    c.genus_name,
    c.family_name,
    c.order_name,
    c.class_name,
    c.phylum,
    c.classification_source,
    c.pbdb_has_taxon,
    c.pbdb_taxon_no,
    c.pbdb_attribution,
    c.first_appearance_max_ma,
    c.last_appearance_min_ma,
    c.early_interval,
    c.late_interval,
    c.occurrence_count,
    n.wikipedia_article,
    n.novelty,
    n.status,
    n.name_authors,
    n.age_text,
    n.type_locality,
    n.country,
    n.countries,
    n.regions,
    n.notes_text,
    n.naming_doi,
    h.first_seen_on_wikipedia,
    b.first_checked_on as pbdb_first_checked_on,
    b.first_found_on as pbdb_first_found_on,
    i.image_source,
    i.image_level,
    i.image_url,
    i.source_page_url as image_page_url,
    i.author as image_author,
    i.license_id as image_license_id,
    i.license_label as image_license,
    i.license_url as image_license_url
from {{ ref('int_taxon_pages') }} as p
left join {{ ref('int_taxon_classification') }} as c using (taxon_key)
left join new_taxa as n using (taxon_key)
left join history as h using (taxon_key)
left join pbdb as b on b.queried_name = p.taxon_name
left join {{ ref('int_image_best_per_taxon') }} as i using (taxon_key)
