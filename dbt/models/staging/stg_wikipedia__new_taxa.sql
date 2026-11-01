-- New taxa as listed on the latest stored revision of each yearly page.
select *
from {{ ref('stg_wikipedia__new_taxa_revisions') }}
{{ latest_revision_only('revid', 'page_title') }}
