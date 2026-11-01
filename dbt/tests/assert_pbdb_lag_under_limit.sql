-- ...but after {{ var('pbdb_lag_weeks') }} weeks a missing taxon is an error worth
-- investigating (wrong name, synonym, or a taxon PBDB will not add). Decision A7.
-- `as_of` pins "today" for CI runs on fixtures; production runs use now().
{% set as_of = var('as_of', none) %}
select taxon_key, first_seen_on_wikipedia
from {{ ref('dim_taxon') }}
where page_type = 'new'
  and not pbdb_has_taxon
  and first_seen_on_wikipedia < {{ "timestamptz '" ~ as_of ~ "'" if as_of else 'now()' }} - to_weeks({{ var('pbdb_lag_weeks') }})
