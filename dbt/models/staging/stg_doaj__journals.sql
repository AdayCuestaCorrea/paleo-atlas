-- Latest DOAJ lookup per ISSN (paleo ingest studies): is the journal listed in the
-- Directory of Open Access Journals? A secondary reliability signal (ALCANCE.md §10).
select
    upper(key) as issn,
    version_date as checked_on,
    cast(json_extract(payload, '$.listed') as boolean) as listed_in_doaj,
    json_extract_string(payload, '$.title') as doaj_title
from {{ read_raw_store('doaj', 'journals') }}
qualify row_number() over (partition by key order by version_date desc) = 1
