-- Latest PBDB lookup per queried name, with when it was first checked and,
-- for names still missing, since when they have been missing (PBDB lag, §16).
with versions as (
    select * from {{ ref('stg_pbdb__taxa_versions') }}
),

summary as (
    select
        queried_name,
        min(version_date) as first_checked_on,
        min(version_date) filter (where found) as first_found_on
    from versions
    group by queried_name
)

select
    v.*,
    s.first_checked_on,
    s.first_found_on
from versions as v
inner join summary as s using (queried_name)
qualify v.version_date = max(v.version_date) over (partition by v.queried_name)
