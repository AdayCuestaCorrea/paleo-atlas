-- Classification and time range for every taxon page.
-- Encyclopedia genera and known taxa: their own PBDB record. New taxa: their own record when PBDB already
-- has them; otherwise their genus (new species of a known genus) or the family
-- linked in the Wikipedia notes ("A member of the family Peirosauridae").
with pages as (
    select * from {{ ref('int_taxon_pages') }}
),

by_name as (
    select * from {{ ref('stg_pbdb__taxa') }} where found
),

-- PBDB records by name: the lookups by name, plus the encyclopedia catalog for the
-- genera nobody looked up by name.
pbdb as (
    select * from by_name
    union all by name
    select
        taxon_name as queried_name,
        true as found,
        pbdb_taxon_no,
        taxon_name as pbdb_name,
        'genus' as taxon_rank,
        attribution,
        parent_name,
        phylum,
        class_name,
        order_name,
        family_name,
        taxon_name as genus_name,
        occurrence_count,
        -- PBDB's own range: the taxobox age is applied below, for every genus page
        pbdb_max_ma as first_appearance_max_ma,
        pbdb_min_ma as last_appearance_min_ma,
        pbdb_early_interval as early_interval,
        pbdb_late_interval as late_interval
    from {{ ref('int_catalog_genera') }}
    where taxon_name not in (select queried_name from by_name)
),

new_taxa as (
    select {{ taxon_key('taxon_name') }} as taxon_key, taxon_name, notes_terms
    from {{ ref('stg_wikipedia__new_taxa') }}
),

note_family as (
    select n.taxon_key, p.pbdb_name as family_from_notes, p.order_name, p.class_name, p.phylum
    from new_taxa as n
    cross join unnest(n.notes_terms) as t(term)
    -- PBDB ranks some families as "unranked clade"; the -idae suffix is the ICZN family ending.
    inner join pbdb as p
        on p.queried_name = t.term
       and (p.taxon_rank = 'family' or p.pbdb_name like '%idae')
    qualify row_number() over (partition by n.taxon_key order by len(p.pbdb_name)) = 1
)

select
    pg.taxon_key,
    pg.taxon_name,
    pg.page_type,
    own.found is not null as pbdb_has_taxon,
    coalesce(own.taxon_rank, case when pg.taxon_name like '% % %' then 'subspecies'
                                  when pg.taxon_name like '% %' then 'species' else 'genus' end) as taxon_rank,
    own.attribution as pbdb_attribution,
    coalesce(own.parent_name, genus.parent_name) as parent_clade,
    own.pbdb_taxon_no,
    coalesce(own.genus_name, genus.pbdb_name, case when pg.taxon_name like '% %' then split_part(pg.taxon_name, ' ', 1) end) as genus_name,
    coalesce(own.family_name, genus.family_name, nf.family_from_notes) as family_name,
    coalesce(own.order_name, genus.order_name, nf.order_name) as order_name,
    coalesce(own.class_name, genus.class_name, nf.class_name) as class_name,
    coalesce(own.phylum, genus.phylum, nf.phylum) as phylum,
    -- Genus pages: the Wikipedia taxobox's age when it has one (int_catalog_genera);
    -- PBDB's range stays in pbdb_* for the "fossil record in PBDB" line.
    coalesce(wr.max_ma, own.first_appearance_max_ma) as first_appearance_max_ma,
    case when wr.taxon_name is not null then wr.min_ma else own.last_appearance_min_ma end
        as last_appearance_min_ma,
    case when wr.taxon_name is not null then wr.early_interval else own.early_interval end
        as early_interval,
    case when wr.taxon_name is not null then wr.late_interval else own.late_interval end
        as late_interval,
    case when wr.taxon_name is not null then 'wikipedia'
         when own.first_appearance_max_ma is not null then 'pbdb' end as age_source,
    own.first_appearance_max_ma as pbdb_max_ma,
    own.last_appearance_min_ma as pbdb_min_ma,
    own.occurrence_count,
    case
        when own.found then 'pbdb'
        when genus.found then 'pbdb_genus'
        when nf.family_from_notes is not null then 'wikipedia_notes'
        else 'none'
    end as classification_source
from pages as pg
left join pbdb as own on own.queried_name = pg.taxon_name
left join pbdb as genus
    on genus.queried_name = split_part(pg.taxon_name, ' ', 1)
   and pg.taxon_name like '% %'
   and genus.taxon_rank = 'genus'
left join note_family as nf on nf.taxon_key = pg.taxon_key
left join {{ ref('stg_wikipedia__fossil_ranges') }} as wr
    on wr.taxon_name = pg.taxon_name and pg.taxon_name not like '% %'
