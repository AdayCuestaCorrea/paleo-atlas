-- One row per taxon page: the 2026 new taxa, the genera of the encyclopedia and the
-- known taxa that 2026 studies are about. This is what the site renders (§11.1).
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
),

genera as (
    select taxon_key, species_names, species_count, type_taxon, catalog_version_date
    from {{ ref('int_catalog_genera') }}
),

occurrences as (
    select genus_name, countries as occurrence_countries, country_codes, points as pbdb_points
    from {{ ref('int_genus_occurrences') }}
),

gbif as (
    select taxon_key, specimens as gbif_specimens, institutions as gbif_institutions,
        points as gbif_points, top_institutions as gbif_top_institutions, gbif_doi
    from {{ ref('fct_specimens_by_taxon') }}
),

genus_pages as (
    select taxon_key as genus_key, taxon_name as genus_page_name
    from {{ ref('int_taxon_pages') }}
    where page_type = 'genus'
),

classification_paths as (
    -- PBDB's full classification of each genus (§11.2, H7), from the root of its block
    -- (Archosauria for every archosaur, birds included) down to its parent clade.
    select
        l.taxon_key,
        list({'name': l.clade_name, 'rank': l.clade_rank} order by l.depth desc)
            filter (where l.depth <= coalesce(r.root_depth, l.depth)) as classification
    from {{ ref('int_genus_lineage') }} as l
    left join (
        select
            taxon_key,
            coalesce(
                max(depth) filter (where clade_name in (select pbdb_base_name from {{ ref('scope_clades') }})),
                max(depth) filter (where clade_name = 'Vertebrata')
            ) as root_depth
        from {{ ref('int_genus_lineage') }}
        group by taxon_key
    ) as r using (taxon_key)
    group by l.taxon_key
)

select
    p.taxon_key,
    p.taxon_name,
    p.page_type,
    p.taxonomic_block,
    p.taxon_group,
    c.taxon_rank,
    c.genus_name,
    -- The encyclopedia page of the genus of a species page (null for genus pages).
    case when p.page_type <> 'genus' then gp.genus_key end as genus_key,
    g.species_names,
    g.species_count,
    g.type_taxon,
    g.catalog_version_date,
    gb.gbif_specimens,
    gb.gbif_institutions,
    gb.gbif_points,
    gb.gbif_top_institutions,
    gb.gbif_doi,
    case when c.taxon_rank = 'genus' then o.pbdb_points end as pbdb_points,
    c.family_name,
    c.order_name,
    c.class_name,
    c.phylum,
    c.classification_source,
    -- Species pages show the classification of their genus.
    coalesce(cp.classification, cpg.classification) as classification,
    case when coalesce(cp.classification, cpg.classification) is not null then 'pbdb' end
        as lineage_source,
    c.pbdb_has_taxon,
    c.pbdb_taxon_no,
    c.pbdb_attribution,
    c.first_appearance_max_ma,
    c.last_appearance_min_ma,
    c.early_interval,
    c.late_interval,
    c.occurrence_count,
    coalesce(n.wikipedia_article, w.en_title) as wikipedia_article,
    w.es_title as wikipedia_article_es,
    w.wikidata_item,
    n.novelty,
    n.status,
    n.name_authors,
    n.age_text,
    n.type_locality,
    n.country,
    -- New taxa: the countries of the Wikipedia table; genera: where PBDB has them.
    coalesce(n.countries, case when c.taxon_rank = 'genus' then o.occurrence_countries end)
        as countries,
    case when c.taxon_rank = 'genus' then o.country_codes end as country_codes,
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
left join genera as g using (taxon_key)
left join occurrences as o on o.genus_name = p.taxon_name
left join gbif as gb using (taxon_key)
left join {{ ref('int_genus_wikipedia') }} as w using (taxon_key)
left join genus_pages as gp
    on gp.genus_page_name = c.genus_name
   and gp.genus_key <> p.taxon_key
left join classification_paths as cp on cp.taxon_key = p.taxon_key
left join classification_paths as cpg on cpg.taxon_key = {{ taxon_key('c.genus_name') }}
