-- A Spanish text is an adaptation of a verified English one: never ES without EN.
select es.taxon_key
from {{ ref('fct_taxon_text') }} as es
inner join {{ ref('fct_taxon_text') }} as en
    on en.taxon_key = es.taxon_key and en.lang = 'en'
where es.lang = 'es' and es.text_status = 'verified' and en.text_status <> 'verified'
