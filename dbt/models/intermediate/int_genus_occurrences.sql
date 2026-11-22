-- Where each genus has been found (PBDB occurrences): countries by number of
-- occurrences, for the page, the index by country and, later, the map (§11.1).
-- PBDB files under a genus every find ever attributed to it, also isolated teeth
-- later reassigned (Velociraptor in Canada) and synonyms (Brachiosaurus in Tanzania,
-- now Giraffatitan). A country counts as confirmed when it has a find within the
-- genus' age in its Wikipedia taxobox and, if the genus has finds identified to
-- species, one of those; the rest are listed apart (ALCANCE.md, Phase 7).
with occ as (
    select o.*, c.name_en as country_name
    from {{ ref('stg_pbdb__occurrences') }} as o
    left join {{ ref('countries') }} as c on c.country_code = o.country_code
),

ranges as (
    select taxon_name as genus_name, max_ma, min_ma
    from {{ ref('stg_wikipedia__fossil_ranges') }}
),

has_species as (
    select genus_name, bool_or(taxon_name like '% %') as any_species
    from occ
    group by genus_name
),

-- A find is solid when its age overlaps the taxobox age and, if the genus has finds
-- identified to species, is one of them.
judged as (
    select
        o.*,
        (r.genus_name is null or (o.max_ma > r.min_ma and o.min_ma < r.max_ma)
            or (o.max_ma is null))
        and (not hs.any_species or o.taxon_name like '% %') as solid
    from occ as o
    left join ranges as r using (genus_name)
    left join has_species as hs using (genus_name)
),

-- Points of the map of finds: coordinates rounded to 0.5 degrees, as in the GBIF
-- extract (paleo.gbif_job.spec), with how many occurrences fall in each cell.
points as (
    select genus_name,
        list({'lat': lat, 'lon': lon, 'n': n} order by lat, lon) as points
    from (
        select genus_name,
            floor(latitude / 0.5 + 0.5) * 0.5 as lat,
            floor(longitude / 0.5 + 0.5) * 0.5 as lon,
            count(*) as n
        from occ
        where latitude is not null and longitude is not null
        group by all
    )
    group by genus_name
),

by_country_all as (
    select genus_name, country_code, any_value(country_name) as country_name, count(*) as n,
        bool_or(solid) as solid
    from judged
    where country_code is not null
    group by genus_name, country_code
),

-- No solid find at all means the rule does not fit this genus (its taxobox age and
-- PBDB's dates disagree everywhere): then every country stays, as PBDB lists them.
confirmed as (
    select *, solid or not bool_or(solid) over (partition by genus_name) as confirmed
    from by_country_all
)

select
    g.genus_name,
    {{ taxon_key('g.genus_name') }} as taxon_key,
    count(*) as occurrence_count,
    (select list(country_name order by n desc, country_name) from confirmed as b
     where b.genus_name = g.genus_name and country_name is not null and b.confirmed)
        as countries,
    (select list(country_code order by n desc, country_code) from confirmed as b
     where b.genus_name = g.genus_name and b.confirmed) as country_codes,
    (select list(country_code order by n desc, country_code) from confirmed as b
     where b.genus_name = g.genus_name and not b.confirmed) as doubtful_country_codes,
    min(latitude) as min_latitude,
    max(latitude) as max_latitude,
    min(longitude) as min_longitude,
    max(longitude) as max_longitude,
    any_value(pt.points) as points
from occ as g
left join points as pt using (genus_name)
group by g.genus_name
