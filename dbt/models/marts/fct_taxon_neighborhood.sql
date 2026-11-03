-- The kinship neighbourhood of each genus page (§11.2, Phase 3 H7), in PBDB's
-- classification. Two levels: 'group', the lowest ancestor clade with at least
-- 3 genera of the encyclopedia under it, and 'up', the next ancestor with more.
-- Each level lists up to 20 genera, the closest first (deepest common ancestor),
-- with the clades between the level's clade and each genus, to draw the cladogram.
-- The whole tree is never drawn: only this neighbourhood.
{% set max_members = 20 %}
with genera as (
    -- Genera with a page (encyclopedia genus, or a new genus of the year).
    select g.taxon_key, g.taxon_name, g.first_appearance_max_ma, g.last_appearance_min_ma
    from {{ ref('int_catalog_genera') }} as g
    inner join {{ ref('int_taxon_pages') }} as p using (taxon_key)
),

lineage as (
    select l.* from {{ ref('int_genus_lineage') }} as l
    inner join genera using (taxon_key)
),

clade_sizes as (
    select clade_no, count(*) as genera from lineage group by clade_no
),

ranked as (
    select
        l.taxon_key,
        l.clade_no,
        l.clade_name,
        l.depth,
        s.genera,
        -- The 'group': the lowest clade with 3 genera or more.
        row_number() over (
            partition by l.taxon_key order by (s.genera >= 3) desc, l.depth
        ) as group_order
    from lineage as l
    inner join clade_sizes as s using (clade_no)
),

group_level as (
    select taxon_key, clade_no, clade_name, depth, genera, 'group' as level
    from ranked where group_order = 1 and genera >= 2
),

up_level as (
    -- The next clade up with more genera than the group.
    select r.taxon_key, r.clade_no, r.clade_name, r.depth, r.genera, 'up' as level
    from ranked as r
    inner join group_level as g on g.taxon_key = r.taxon_key
    where r.depth > g.depth and r.genera > g.genera
    qualify row_number() over (partition by r.taxon_key order by r.depth) = 1
),

levels as (
    select * from group_level union all select * from up_level
),

members as (
    -- Every genus under the level's clade, with how close it is to the page's genus:
    -- the depth (from the page's genus) of their lowest common ancestor.
    select
        v.taxon_key,
        v.level,
        v.clade_no as level_clade_no,
        v.clade_name as level_clade_name,
        v.genera as level_genera,
        m.taxon_key as member_key,
        m.depth as member_depth  -- depth of the level's clade above the member
    from levels as v
    inner join lineage as m on m.clade_no = v.clade_no
),

closeness as (
    select
        mb.taxon_key,
        mb.level,
        mb.member_key,
        min(a.depth) as common_depth
    from members as mb
    inner join lineage as a on a.taxon_key = mb.taxon_key
    inner join lineage as b on b.taxon_key = mb.member_key and b.clade_no = a.clade_no
    group by all
),

chosen as (
    select
        mb.*,
        case when mb.member_key = mb.taxon_key then 0 else c.common_depth end as common_depth
    from members as mb
    left join closeness as c using (taxon_key, level, member_key)
    qualify row_number() over (
        partition by mb.taxon_key, mb.level
        order by mb.member_key = mb.taxon_key desc, c.common_depth, mb.member_key
    ) <= {{ max_members }}
)

select
    c.taxon_key,
    c.level,
    c.level_clade_name,
    c.level_genera,
    c.member_key,
    g.taxon_name as member_name,
    c.member_key = c.taxon_key as is_self,
    c.common_depth,
    g.first_appearance_max_ma,
    g.last_appearance_min_ma,
    -- Clades from just below the level's clade down to the member's parent.
    (
        select coalesce(list({'clade_no': p.clade_no, 'name': p.clade_name} order by p.depth desc), [])
        from lineage as p
        where p.taxon_key = c.member_key and p.depth < c.member_depth
    ) as path
from chosen as c
inner join genera as g on g.taxon_key = c.member_key
