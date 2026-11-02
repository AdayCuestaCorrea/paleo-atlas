-- One row per genus of the encyclopedia: the extinct genera of the enabled clades of
-- the scope seed (ALCANCE.md §4), each in the most specific clade that contains it
-- (a bird is also a dinosaur and an archosaur: the lowest priority wins), with its
-- accepted species.
with scope as (
    select * from {{ ref('scope_clades') }} where enabled
),

genera as (
    select c.*, s.block as taxonomic_block, s.taxon_group, s.priority
    from {{ ref('stg_pbdb__catalog') }} as c
    inner join scope as s on s.pbdb_base_name = c.base_name
    where c.taxon_rank = 'genus'
    qualify row_number() over (
        partition by c.pbdb_taxon_no order by s.priority, c.base_name
    ) = 1
),

species as (
    select
        genus_name,
        list(distinct pbdb_name order by pbdb_name) as species_names,
        count(distinct pbdb_name) as species_count
    from {{ ref('stg_pbdb__catalog') }}
    where taxon_rank = 'species'
    group by genus_name
)

select
    {{ taxon_key('g.pbdb_name') }} as taxon_key,
    g.pbdb_name as taxon_name,
    g.taxonomic_block,
    g.taxon_group,
    g.pbdb_taxon_no,
    g.attribution,
    g.parent_name,
    g.phylum,
    g.class_name,
    g.order_name,
    g.family_name,
    g.type_taxon,
    g.occurrence_count,
    g.first_appearance_max_ma,
    g.last_appearance_min_ma,
    g.early_interval,
    g.late_interval,
    coalesce(s.species_names, []) as species_names,
    coalesce(s.species_count, 0) as species_count,
    g.version_date as catalog_version_date
from genera as g
left join species as s on s.genus_name = g.pbdb_name
-- Two genera with the same name in different clades (homonyms) would share a key:
-- keep the one in the most specific clade.
qualify row_number() over (partition by taxon_key order by g.priority, g.pbdb_taxon_no) = 1
