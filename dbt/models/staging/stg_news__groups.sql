-- Which story each news article belongs to (paleo news dedup): articles that tell the
-- same story share a group, named after its smallest key. Only articles that are not
-- noise are grouped.
select key as news_key, "group" as story_key, method as grouped_by
from {{ read_narrative('news_groups') }}
