-- A known species whose genus has an encyclopedia page is shown on the genus page
-- (int_folded_species), never as a page of its own beside it.
select t.taxon_key
from {{ ref('dim_taxon') }} as t
inner join {{ ref('dim_taxon') }} as g
    on g.taxon_key = {{ taxon_key("split_part(t.taxon_name, ' ', 1)") }} and g.page_type = 'genus'
where t.page_type = 'known' and t.taxon_name like '% %'
