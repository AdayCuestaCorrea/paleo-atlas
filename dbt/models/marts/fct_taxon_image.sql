-- Gallery of each taxon page (ALCANCE.md §11.1): freely licensed images other
-- than the main one, with a kind guessed from the file name, description and
-- Commons categories. At most 12 per taxon: first the images of the Wikipedia
-- article (chosen by its editors), one of each kind first; then images of the
-- Commons category, only to fill the gaps (it also holds statues, toys and charts).
with candidates as (
    select
        f.taxon_key,
        f.file_name,
        f.found_in,
        f.position,
        i.mime_type,
        i.width,
        i.url,
        i.thumb_url,
        i.description_url,
        coalesce(i.author, i.credit) as author,
        a.label as license,
        a.license_url,
        lower(f.file_name) as name_text,
        lower(coalesce(i.description, '') || ' ' || coalesce(i.categories, '')) as description_text,
        i.description,
        lower(t.taxon_name) as taxon_name,
        lower(coalesce(t.genus_name, split_part(t.taxon_name, ' ', 1))) as genus
    from {{ ref('stg_commons__taxon_files') }} as f
    inner join {{ ref('stg_commons__images') }} as i
        on i.file_name = f.file_name and i.found_on_commons
    inner join {{ ref('license_allowlist') }} as a
        on a.license_id = i.license_id and a.allowed
    inner join {{ ref('dim_taxon') }} as t on t.taxon_key = f.taxon_key
    left join {{ ref('int_image_best_per_taxon') }} as hero
        on hero.taxon_key = f.taxon_key and hero.image_ref = f.file_name
    where hero.taxon_key is null  -- the main image is shown above, not again
      and not exists (
          select 1 from {{ ref('image_exclusions') }} as x
          where x.taxon_key = f.taxon_key
            and replace(x.file_name, ' ', '_') = replace(f.file_name, ' ', '_')
      )
      and i.mime_type in ('image/jpeg', 'image/png', 'image/svg+xml', 'image/webp', 'image/gif', 'image/tiff')
      and coalesce(i.author, i.credit) is not null
),

classified as (
    select
        *,
        -- The file name says more than the description (which may mention a
        -- holotype, a scale bar...), so it decides first.
        case
            when {{ image_kind('name_text') }} = 'excluded' or {{ image_kind('description_text') }} = 'excluded'
                then 'excluded'
            when {{ image_kind('name_text') }} <> 'other' then {{ image_kind('name_text') }}
            else {{ image_kind('description_text') }}
        end as image_kind
    from candidates
    -- Category files must be about the taxon by their own name: Commons categories
    -- also hold toys, statues, cartoons and charts that merely mention it.
    where found_in = 'article'
       or replace(name_text, '_', ' ') like '%' || genus || '%'
),

ranked as (
    select
        *,
        -- One of each kind first, within the article images and then within the
        -- category ones.
        row_number() over (
            partition by taxon_key, found_in = 'article', image_kind order by position
        ) as kind_rank,
        -- At most a few of each kind on the page (two size charts are enough).
        row_number() over (
            partition by taxon_key, image_kind
            order by case found_in when 'article' then 1 else 2 end, position
        ) as kind_count
    from (
        -- The same drawing as PNG and SVG, or translated ("… size comparison ca.svg"):
        -- one copy.
        select *
        from classified
        where image_kind <> 'excluded' and not (image_kind = 'other' and found_in = 'category')
        qualify row_number() over (
            partition by taxon_key, regexp_replace(
                name_text, '([ _-](ar|ca|ru|de|fr|es|it|ja|zh|pt|uk|pl|nl|hu|cs|fa|he|ko|tr|en))?\.(png|svg|jpe?g|webp|gif|tiff?)$', '')
            order by found_in, position
        ) = 1
    )
    qualify kind_count <= case image_kind when 'size' then 2 when 'life' then 4 else 3 end
)

select
    taxon_key || ':' || file_name as image_key,
    taxon_key,
    row_number() over (
        partition by taxon_key
        order by
            case found_in when 'article' then 1 else 2 end,
            kind_rank,
            -- Among the first of each kind: what a reader wants to see first.
            case image_kind when 'life' then 1 when 'skeleton' then 2 when 'skull' then 3
                when 'size' then 4 when 'fossil' then 5 when 'holotype' then 6 else 7 end,
            position
    ) as image_rank,
    file_name,
    image_kind,
    -- What the picture shows, from Commons (usually English): its first sentence.
    -- Only in the Latin alphabet: the pages are in Spanish and English.
    case
        when regexp_matches(description, '[^\x{0000}-\x{024F}\x{2000}-\x{206F}\x{00B7}]') then null
        when length(split_part(description, '. ', 1)) <= 140 then nullif(split_part(description, '. ', 1), '')
        else regexp_replace(left(description, 140), '\s+\S*$', '') || '…'
    end as caption,
    author,
    license,
    license_url,
    description_url as page_url,
    coalesce(thumb_url, url) as thumb_url,
    -- Commons never scales up: a 1600 px thumbnail only exists for wider originals.
    case
        when width > 1600 and thumb_url like '%/800px-%' then replace(thumb_url, '/800px-', '/1600px-')
        when mime_type = 'image/tiff' then coalesce(thumb_url, url)
        else url
    end as large_url
from ranked
qualify image_rank <= 12
