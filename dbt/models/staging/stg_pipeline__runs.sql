-- One row per pipeline run (paleo report start/finish): when change detection ran,
-- what triggered it and whether it found something new. Feeds the freshness test,
-- the "sources checked on" date of the website and the data status page (steps and
-- their durations, warehouse totals, dbt results, what changed; JSON as logged).
select
    started_at,
    finished_at,
    trigger,
    changed,
    status,
    steps,
    summary,
    dbt,
    sources_changed,
    changes_since_previous,
    wikipedia_new_revisions
from {{ read_runs() }}
