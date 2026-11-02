-- GBIF fossil specimens of each genus page (§8): counts, countries, map points and the
-- institutions with most specimens, with the DOI of the download they come from.
with download as (
    select doi, citation from {{ ref('stg_gbif__downloads') }}
    qualify created_at = max(created_at) over ()
)

select
    p.taxon_key,
    s.specimens,
    s.institutions,
    s.countries,
    s.points,
    s.top_institutions,
    s.by_method,
    d.doi as gbif_doi
from {{ ref('int_taxon_pages') }} as p
inner join {{ ref('stg_gbif__genus_specimens') }} as s on s.genus = p.taxon_name
left join download as d on true
