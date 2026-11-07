-- When each stored source (raw/<source>/<kind>) was last checked and how many keys it
-- holds, from RawStore's _checked.json: a check is recorded even when nothing changed,
-- unlike the dated versions, which only appear on a change.
select
    regexp_extract(filename, 'raw/([^/]+/[^/]+)/_checked\.json$', 1) as source,
    len(map_keys(json::map(varchar, varchar))) as records,
    cast(list_max(map_values(json::map(varchar, varchar))) as date) as last_checked
from {{ read_checked() }}
