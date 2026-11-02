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
  The group of each row (and whether it is in the scope of §4) is decided in Python,
  by paleo.scope, when the page is parsed: the interim files carry `taxon_group`.
#}

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
            revision_timestamp: 'TIMESTAMPTZ', taxon_group: 'VARCHAR'
        {%- endset -%}
    {%- elif kind == 'research' -%}
        {%- set columns -%}
            page_title: 'VARCHAR', revid: 'BIGINT', research_id: 'VARCHAR',
            section_path: 'VARCHAR[]', text: 'VARCHAR',
            links: 'VARCHAR[]', italic_links: 'VARCHAR[]', italic_names: 'VARCHAR[]',
            "references": '{{ reference_type }}', parse_warnings: 'VARCHAR[]',
            revision_timestamp: 'TIMESTAMPTZ', taxon_group: 'VARCHAR'
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
