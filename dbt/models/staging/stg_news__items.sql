-- Latest version of each news article from the paleontology feeds (paleo ingest news,
-- F9): outlet, language, headline, link, publication time and, where the outlet's terms
-- allow it, the feed's own summary.
select
    key as news_key,
    json_extract_string(payload, '$.outlet') as outlet,
    json_extract_string(payload, '$.lang') as lang,
    json_extract_string(payload, '$.title') as title,
    json_extract_string(payload, '$.url') as url,
    cast(json_extract_string(payload, '$.published') as timestamptz) as published_at,
    json_extract_string(payload, '$.summary') as summary,
    version_date as seen_on
from {{ read_optional_raw_store('news', 'items') }}
qualify row_number() over (partition by key order by version_date desc) = 1
