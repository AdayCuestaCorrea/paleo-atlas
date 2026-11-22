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
    -- PBDB sometimes lists the same taxon twice in one download (one record with its
    -- occurrences, one without): the one with more occurrences wins, and the rest of
    -- the order only makes the choice the same on every build.
    qualify row_number() over (
        partition by c.pbdb_taxon_no
        order by s.priority, c.base_name, c.occurrence_count desc nulls last,
                 c.attribution nulls last, c.parent_name, c.family_name nulls last
    ) = 1
),

species as (
    select
        genus_name,
        list(distinct pbdb_name order by pbdb_name) as species_names,
        count(distinct pbdb_name) as species_count
    from {{ ref('stg_pbdb__catalog') }}
    -- PBDB also files under a genus species it keeps in another genus name
    -- (Ojoceratops fowleri under Triceratops): only the genus' own binomials count.
    where taxon_rank = 'species' and pbdb_name like genus_name || ' %'
    group by genus_name
)

select
    {{ taxon_key('g.pbdb_name') }} as taxon_key,
    g.pbdb_name as taxon_name,
    g.taxonomic_block,
    g.taxon_group,
    g.pbdb_taxon_no,
    g.attribution,
    g.parent_no,
    g.parent_name,
    g.phylum,
    g.class_name,
    g.order_name,
    g.family_name,
    g.type_taxon,
    g.occurrence_count,
    -- The age: the Wikipedia taxobox's when it has one, else PBDB's range; PBDB's own
    -- range is kept apart (pbdb_*) for the "fossil record in PBDB" line.
    coalesce(r.max_ma, g.first_appearance_max_ma) as first_appearance_max_ma,
    case when r.taxon_name is not null then r.min_ma else g.last_appearance_min_ma end
        as last_appearance_min_ma,
    case when r.taxon_name is not null then r.early_interval else g.early_interval end
        as early_interval,
    case when r.taxon_name is not null then r.late_interval else g.late_interval end
        as late_interval,
    case when r.taxon_name is not null then 'wikipedia'
         when g.first_appearance_max_ma is not null then 'pbdb' end as age_source,
    g.first_appearance_max_ma as pbdb_max_ma,
    g.last_appearance_min_ma as pbdb_min_ma,
    g.early_interval as pbdb_early_interval,
    g.late_interval as pbdb_late_interval,
    coalesce(s.species_names, []) as species_names,
    coalesce(s.species_count, 0) as species_count,
    g.version_date as catalog_version_date
from genera as g
left join species as s on s.genus_name = g.pbdb_name
left join {{ ref('stg_wikipedia__fossil_ranges') }} as r on r.taxon_name = g.pbdb_name
-- Two genera with the same name (homonyms: Paracorax is a fossil cormorant and a
-- shark) would share a key: one page per name, the earlier block first (archosaurs,
-- marine reptiles, fishes), then the most specific clade. The test
-- assert_catalog_homonyms lists the genera left without a page.
qualify row_number() over (
    partition by taxon_key
    order by
        case g.taxonomic_block when 'archosaurs' then 1 when 'marine_reptiles' then 2 else 3 end,
        g.priority,
        g.pbdb_taxon_no
) = 1
