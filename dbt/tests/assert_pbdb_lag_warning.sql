-- New taxa not yet in PBDB: expected for a while (PBDB lags behind publication).
{{ config(severity = 'warn') }}
select taxon_key, first_seen_on_wikipedia
from {{ ref('dim_taxon') }}
where page_type = 'new' and not pbdb_has_taxon
