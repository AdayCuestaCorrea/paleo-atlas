-- The silhouette the size comparator draws for each taxon page: the first PhyloPic
-- image with an allowed license walking up from the taxon itself, through its genus and
-- every clade of its PBDB classification (lowest first), to the clade of its group
-- (seed group_clades). Unlike the page picture, every intermediate clade counts: a
-- titanosaur must not get the order's (Saurischia) silhouette. Proportions come from
-- the largest raster PhyloPic renders (".../raster/1536x497.png"); poses useless as a
-- measure are left out (seed silhouette_exclusions).
with lineage as (
    select taxon_key, taxon_name as node, 'taxon' as level, 0 as depth
    from {{ ref('dim_taxon') }}
    union all
    select taxon_key, genus_name, 'genus', 1
    from {{ ref('dim_taxon') }}
    where genus_name is not null and genus_name <> taxon_name
    union all
    select t.taxon_key, c.node.name, 'clade', 2 + len(t.classification) - c.pos
    from {{ ref('dim_taxon') }} as t,
         unnest(t.classification) with ordinality as c(node, pos)
    union all
    select t.taxon_key, g.clade_name, 'group', 1000
    from {{ ref('dim_taxon') }} as t
    inner join {{ ref('group_clades') }} as g using (taxon_group)
),

candidates as (
    select
        l.taxon_key,
        l.level,
        l.depth,
        l.node,
        i.image_uuid,
        i.vector_url,
        i.page_url,
        coalesce(i.attribution, i.contributor) as author,
        i.license_id_raw as license_id,
        a.label as license_label,
        a.license_url,
        try_cast(regexp_extract(i.raster_url, '/raster/(\d+)x\d+\.', 1) as double) as raster_w,
        try_cast(regexp_extract(i.raster_url, '/raster/\d+x(\d+)\.', 1) as double) as raster_h
    from lineage as l
    inner join {{ ref('stg_phylopic__images') }} as i
        on i.queried_name = l.node and i.found_on_phylopic
    inner join {{ ref('license_allowlist') }} as a
        on a.license_id = i.license_id_raw and a.allowed
    where i.vector_url is not null
      and i.image_uuid not in (select image_uuid from {{ ref('silhouette_exclusions') }})
)

select
    taxon_key,
    level as silhouette_level,
    node as silhouette_node,
    image_uuid,
    vector_url,
    page_url as source_page_url,
    author,
    license_id,
    license_label,
    license_url,
    round(raster_h / raster_w, 4) as aspect
from candidates
where raster_w > 0 and raster_h > 0
qualify row_number() over (partition by taxon_key order by depth, node) = 1
