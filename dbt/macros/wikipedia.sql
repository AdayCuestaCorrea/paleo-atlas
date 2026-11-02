{# Shared helpers for the Wikipedia staging models. #}

{% macro wikipedia_block(page_title) -%}
    case
        when {{ page_title }} ilike '%archosaur paleontology%' then 'archosaurs'
        when {{ page_title }} ilike '%reptile paleontology%' then 'marine_reptiles'
        when {{ page_title }} ilike '%paleoichthyology%' then 'fossil_fishes'
        else 'unknown'
    end
{%- endmacro %}

{#
  Group of a row from the section it is in. Sections can be nested
  ("Lepidosauromorphs > Squamates"), so every level is looked at. For the marine
  reptile and fish pages this is only a candidate: wikipedia_in_scope decides.
#}
{% macro wikipedia_group(section_path) -%}
    case
        when lower({{ section_path }}[1]) = 'pseudosuchians' then 'pseudosuchians'
        when lower({{ section_path }}[1]) = 'non-avian dinosaurs' then 'non_avian_dinosaurs'
        when lower({{ section_path }}[1]) = 'birds' then 'birds'
        when lower({{ section_path }}[1]) = 'pterosaurs' then 'pterosaurs'
        when lower({{ section_path }}[1]) = 'other archosaurs' then 'other_archosaurs'
        when lower({{ section_path }}[1]) = 'general research' then 'general'
        when list_has_any(list_transform({{ section_path }}, lambda s: lower(s)),
             ['ichthyosauromorphs', 'ichthyosauromorph research']) then 'ichthyosaurs'
        when list_has_any(list_transform({{ section_path }}, lambda s: lower(s)),
             ['sauropterygians', 'sauropterygian research']) then 'sauropterygians'
        when list_has_any(list_transform({{ section_path }}, lambda s: lower(s)),
             ['squamates', 'squamate research']) then 'squamates'
        when list_has_any(list_transform({{ section_path }}, lambda s: lower(s)),
             ['placoderms', 'placoderm research']) then 'placoderms'
        when list_has_any(list_transform({{ section_path }}, lambda s: lower(s)),
             ['cartilaginous fishes', 'cartilaginous fish research']) then 'cartilaginous_fishes'
        when list_has_any(list_transform({{ section_path }}, lambda s: lower(s)),
             ['ray-finned fishes', 'ray-finned fish research', 'lobe-finned fishes',
              'lobe-finned fish research', 'jawless vertebrates', 'jawless vertebrate research',
              'other fishes', 'other fish research']) then 'bony_fishes'
        else 'other'
    end
{%- endmacro %}

{#
  Final group of a row, or null when it is outside the scope of ALCANCE.md §4.
  Archosaur page: every section. Marine reptiles: ichthyosaurs, sauropterygians and,
  among the squamates, the mosasaurs (named in the text). Fishes: placoderms,
  cartilaginous fishes and the genera of the featured_fishes seed (`featured`: a SQL
  condition, since a new taxon is matched by its genus and a study by its text).
#}
{% macro wikipedia_in_scope(block, group, featured, text) -%}
    case
        when {{ block }} = 'archosaurs' then {{ group }}
        when {{ group }} in ('ichthyosaurs', 'sauropterygians', 'placoderms', 'cartilaginous_fishes')
            then {{ group }}
        when {{ group }} = 'squamates' and {{ text }} ilike '%mosasaur%' then 'mosasaurs'
        when {{ group }} = 'bony_fishes' and {{ featured }} then 'other_fishes'
    end
{%- endmacro %}

{% macro latest_revision_only(revid, page_title) -%}
    qualify {{ revid }} = max({{ revid }}) over (partition by {{ page_title }})
{%- endmacro %}

{#
  Read the JSONL files written by `paleo parse wikipedia`, with explicit column
  types so empty lists never change the inferred schema. Files live in
  $PALEO_DATA_DIR/interim/wikipedia/<page>/<revid>/<kind>.jsonl.
#}
{% macro read_wikipedia_interim(kind) -%}
    {%- set reference_type -%}
        STRUCT(template VARCHAR, doi VARCHAR, title VARCHAR, venue VARCHAR, year INTEGER, url VARCHAR, authors VARCHAR[], ref_name VARCHAR)[]
    {%- endset -%}
    {%- if kind == 'new_taxa' -%}
        {%- set columns -%}
            page_title: 'VARCHAR', revid: 'BIGINT', section_path: 'VARCHAR[]',
            table_index: 'INTEGER', row_index: 'INTEGER',
            name: 'VARCHAR', name_link: 'VARCHAR', novelty: 'VARCHAR', status: 'VARCHAR',
            authors: 'VARCHAR', age: 'VARCHAR', age_links: 'VARCHAR[]',
            type_locality: 'VARCHAR', type_locality_links: 'VARCHAR[]',
            countries: 'VARCHAR[]', regions: 'VARCHAR[]', notes: 'VARCHAR', note_links: 'VARCHAR[]',
            images: 'VARCHAR[]', "references": '{{ reference_type }}', parse_warnings: 'VARCHAR[]',
            revision_timestamp: 'TIMESTAMPTZ'
        {%- endset -%}
    {%- elif kind == 'research' -%}
        {%- set columns -%}
            page_title: 'VARCHAR', revid: 'BIGINT', research_id: 'VARCHAR',
            section_path: 'VARCHAR[]', text: 'VARCHAR',
            links: 'VARCHAR[]', italic_links: 'VARCHAR[]', italic_names: 'VARCHAR[]',
            "references": '{{ reference_type }}', parse_warnings: 'VARCHAR[]',
            revision_timestamp: 'TIMESTAMPTZ'
        {%- endset -%}
    {%- else -%}
        {{ exceptions.raise_compiler_error("Unknown Wikipedia interim kind: " ~ kind) }}
    {%- endif -%}
    read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/interim/wikipedia/*/*/{{ kind }}.jsonl',
        format = 'newline_delimited',
        columns = { {{ columns }} }
    )
{%- endmacro %}
