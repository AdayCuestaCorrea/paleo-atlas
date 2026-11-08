-- Every image found for a taxon page, with its level of precision:
--   taxon  = the taxon itself (Commons file from the Wikipedia table, the lead image of
--            the verified Wikipedia article of a genus, or PhyloPic)
--   genus  = PhyloPic silhouette of its genus
--   clade  = PhyloPic silhouette of its family/order/class or of a group named in the notes
--   group  = PhyloPic silhouette of the clade that stands for its group (seed group_clades)
with pages as (
    select c.*, n.notes_terms, n.image_files
    from {{ ref('int_taxon_classification') }} as c
    left join (
        select {{ taxon_key('taxon_name') }} as taxon_key, notes_terms, image_files
        from {{ ref('stg_wikipedia__new_taxa') }}
    ) as n using (taxon_key)
),

commons as (
    select
        p.taxon_key,
        'commons' as image_source,
        'taxon' as image_level,
        1 as clade_position,
        i.file_name as image_ref,
        coalesce(i.thumb_url, i.url) as image_url,
        i.description_url as source_page_url,
        i.author,
        i.license_id
    from pages as p
    cross join unnest(p.image_files) as f(file_name)
    inner join {{ ref('stg_commons__images') }} as i
        on i.file_name = f.file_name and i.found_on_commons
),

lead_images as (
    -- Lead image of the verified Wikipedia article of an encyclopedia genus.
    select
        w.taxon_key,
        'commons' as image_source,
        'taxon' as image_level,
        2 as clade_position,
        i.file_name as image_ref,
        coalesce(i.thumb_url, i.url) as image_url,
        i.description_url as source_page_url,
        i.author,
        i.license_id
    from {{ ref('int_genus_wikipedia') }} as w
    inner join pages as p using (taxon_key)
    inner join {{ ref('stg_commons__images') }} as i
        on i.file_name = w.lead_image and i.found_on_commons
),

lookups as (
    -- (taxon, name to look up on PhyloPic, level, position among clade candidates)
    select taxon_key, taxon_name as lookup_name, 'taxon' as image_level, 1 as clade_position from pages
    union all
    select taxon_key, genus_name, 'genus', 1 from pages
    where genus_name is not null and genus_name <> taxon_name
    union all
    select taxon_key, parent_clade, 'clade', 1 from pages
    where parent_clade is not null and parent_clade <> genus_name
    union all
    select taxon_key, family_name, 'clade', 2 from pages where family_name is not null
    union all
    select taxon_key, order_name, 'clade', 3 from pages where order_name is not null
    union all
    select taxon_key, unnest(notes_terms), 'clade', 4 + unnest(range(len(notes_terms)))
    from pages where notes_terms is not null
    union all
    select taxon_key, class_name, 'clade', 100 from pages
    -- PBDB's "Reptilia" is too broad for an archosaur (a lizard silhouette): the
    -- group image is a better fallback.
    where class_name is not null and class_name not like 'NO\_%' escape '\'
      and class_name <> 'Reptilia'
    union all
    select p.taxon_key, g.clade_name, 'group', 1
    from {{ ref('int_taxon_pages') }} as p
    inner join {{ ref('group_clades') }} as g using (taxon_group)
),

phylopic as (
    select
        l.taxon_key,
        'phylopic' as image_source,
        l.image_level,
        l.clade_position,
        i.queried_name as image_ref,
        coalesce(i.raster_url, i.vector_url) as image_url,
        i.page_url as source_page_url,
        coalesce(i.attribution, i.contributor) as author,
        i.license_id_raw as license_id
    from lookups as l
    inner join {{ ref('stg_phylopic__images') }} as i
        on i.queried_name = l.lookup_name and i.found_on_phylopic
)

select
    c.*,
    coalesce(a.allowed, false) as license_allowed,
    a.label as license_label,
    a.license_url
from (
    select * from commons
    union all select * from lead_images
    union all select * from phylopic
) as c
left join {{ ref('license_allowlist') }} as a using (license_id)
-- Files checked by eye that show another animal, a map or a locality (seed image_exclusions).
where not exists (
    select 1 from {{ ref('image_exclusions') }} as x
    where c.image_source = 'commons' and x.taxon_key = c.taxon_key
      and replace(x.file_name, ' ', '_') = replace(c.image_ref, ' ', '_')
)
