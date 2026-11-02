-- Change detection must have run in the last 2 days (ALCANCE.md §16): otherwise the
-- schedule stopped and the website is silently going stale.
-- `as_of` pins "today" for CI runs on fixtures; production runs use now().
{% set as_of = var('as_of', none) %}
select max(started_at) as last_detection
from {{ ref('stg_pipeline__runs') }}
having max(started_at) is null
    or max(started_at) < {{ "timestamptz '" ~ as_of ~ "'" if as_of else 'now()' }} - interval 2 day
