-- Latest Crossref metadata per DOI. Abstracts are never stored here (§19).
with versions as (
    select key as doi, version_date, payload
    from {{ read_raw_store('crossref', 'works') }}
    qualify version_date = max(version_date) over (partition by key)
),

works as (
    select
        doi,
        version_date,
        cast(json_extract(payload, '$.found') as boolean) as found_in_crossref,
        json_extract(payload, '$.work') as work
    from versions
)

select
    doi,
    version_date as checked_on,
    found_in_crossref,
    work ->> 'type' as work_type,
    {{ strip_html("work ->> '$.title[0]'") }} as title,
    {{ strip_html("work ->> '$.container-title[0]'") }} as journal,
    work ->> 'publisher' as publisher,
    cast(json_extract(work, '$.ISSN') as varchar[]) as issns,
    try_cast(
        concat_ws(
            '-',
            work ->> '$.issued.date-parts[0][0]',
            coalesce(lpad(work ->> '$.issued.date-parts[0][1]', 2, '0'), '01'),
            coalesce(lpad(work ->> '$.issued.date-parts[0][2]', 2, '0'), '01')
        ) as date
    ) as issued_on,
    cast(work ->> '$.issued.date-parts[0][0]' as integer) as issued_year,
    -- Crossref may only know the year or the month; issued_on fills the rest with 01.
    case
        when work ->> '$.issued.date-parts[0][2]' is not null then 'day'
        when work ->> '$.issued.date-parts[0][1]' is not null then 'month'
        when work ->> '$.issued.date-parts[0][0]' is not null then 'year'
    end as issued_precision,
    work ->> 'URL' as url,
    json_extract(work, '$.updated-by') as updated_by
from works
