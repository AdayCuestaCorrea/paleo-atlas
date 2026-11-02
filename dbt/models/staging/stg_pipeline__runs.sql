-- One row per pipeline run (paleo report start/finish): when change detection ran,
-- what triggered it and whether it found something new. Feeds the freshness test
-- and the "sources checked on" date of the website.
select
    started_at,
    finished_at,
    trigger,
    changed,
    status
from {{ read_runs() }}
