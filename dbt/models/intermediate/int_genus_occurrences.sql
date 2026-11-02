-- Where each genus has been found (PBDB occurrences): countries by number of
-- occurrences, for the page, the index by country and, later, the map (§11.1).
with occ as (
    select o.*, c.name_en as country_name
    from {{ ref('stg_pbdb__occurrences') }} as o
    left join {{ ref('countries') }} as c on c.country_code = o.country_code
),

by_country as (
    select genus_name, country_code, any_value(country_name) as country_name, count(*) as n
    from occ
    where country_code is not null
    group by all
)

select
    g.genus_name,
    {{ taxon_key('g.genus_name') }} as taxon_key,
    count(*) as occurrence_count,
    (select list(country_name order by n desc, country_name) from by_country as b
     where b.genus_name = g.genus_name and country_name is not null) as countries,
    (select list(country_code order by n desc, country_code) from by_country as b
     where b.genus_name = g.genus_name) as country_codes,
    min(latitude) as min_latitude,
    max(latitude) as max_latitude,
    min(longitude) as min_longitude,
    max(longitude) as max_longitude
from occ as g
group by g.genus_name
