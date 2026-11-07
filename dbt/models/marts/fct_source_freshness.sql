-- How fresh each source is (ALCANCE.md §5): the last time it was checked and its
-- expected rhythm (seed source_cadence). The yearly Wikipedia pages are checked on every
-- run; GBIF keeps no check log, so its last download counts.
with last_run as (
    select max(started_at)::date as checked_on from {{ ref('stg_pipeline__runs') }}
),

gbif as (
    select max(version_date) as checked_on, count(distinct key) as records
    from {{ read_optional_raw_store('gbif', 'downloads') }}
)

select
    s.source,
    s.sort,
    s.name_es,
    s.name_en,
    s.cadence_es,
    s.cadence_en,
    s.every_days,
    case s.family
        when 'runs' then (select checked_on from last_run)
        when 'gbif/downloads' then (select checked_on from gbif)
        else c.last_checked
    end as last_checked,
    case s.family
        when 'runs' then null
        when 'gbif/downloads' then (select records from gbif)
        else c.records
    end as records
from {{ ref('source_cadence') }} as s
left join {{ ref('stg_raw__checked') }} as c on c.source = s.family
