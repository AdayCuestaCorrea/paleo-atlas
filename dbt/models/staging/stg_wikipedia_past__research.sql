-- Studies listed on the yearly pages of past years (latest stored revision of each
-- page). History only (Phase 3, H4): `new_study` events on the pages they mention;
-- they never create pages, texts or Crossref lookups.
select *
from ({{ wikipedia_research_rows('wikipedia_past') }})
{{ latest_revision_only('revid', 'page_title') }}
