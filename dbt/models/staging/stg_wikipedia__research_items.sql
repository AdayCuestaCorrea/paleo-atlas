-- Studies as listed on the latest stored revision of each yearly page.
select *
from {{ ref('stg_wikipedia__research_revisions') }}
{{ latest_revision_only('revid', 'page_title') }}
