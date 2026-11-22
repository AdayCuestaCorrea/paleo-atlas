-- Age of each genus as its English Wikipedia taxobox gives it (fossil_range, read by
-- paleo ranges from the same article revision the page's text cites). Curated, unlike
-- PBDB's first and last appearance, which spans every occurrence ever filed under the
-- genus (reassigned teeth, synonyms): the site shows this one first (ALCANCE.md, Phase 7).
select
    taxon_name,
    max_ma,
    min_ma,
    early_interval,
    late_interval,
    label,
    title,
    revid
from {{ read_narrative('ranges') }}
where max_ma is not null and min_ma is not null and max_ma >= min_ma
