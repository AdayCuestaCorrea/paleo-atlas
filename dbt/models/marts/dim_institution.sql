-- Museums and collections holding GBIF fossil specimens of the encyclopedia genera (§8).
select institution_code, specimens, genera
from {{ ref('stg_gbif__institutions') }}
