-- New taxa listed on the yearly pages of past years (latest stored revision of each
-- page). History only (Phase 3, H4): they never get a page of their own as new taxa.
select *
from ({{ wikipedia_new_taxa_rows('wikipedia_past') }})
{{ latest_revision_only('revid', 'page_title') }}
