-- Verified texts held back because their facts were extracted again and the text was
-- not rewritten yet (Groq ran out of daily quota in between): the page shows the
-- fallback meanwhile. Expected for a few days after a change of the facts prompt.
{{ config(severity = 'warn') }}
select t.taxon_key, t.lang
from {{ ref('stg_narrative__texts') }} as t
inner join {{ ref('fct_taxon_text') }} as f
    on f.taxon_key = t.taxon_key and f.lang = t.lang
where t.status = 'verified' and f.text_status = 'pending'
