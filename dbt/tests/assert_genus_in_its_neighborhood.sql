-- Every level of a genus's kinship neighbourhood includes the genus itself.
select taxon_key, level
from {{ ref('fct_taxon_neighborhood') }}
group by taxon_key, level
having not bool_or(is_self)
