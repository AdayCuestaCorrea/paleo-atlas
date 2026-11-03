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
  $PALEO_DATA_DIR/interim/<folder>/<page>/<revid>/<kind>.jsonl: `wikipedia` for the
  pages of the year, `wikipedia_past` for past years (history only, Phase 3 H4).
  A folder with no files yet gives an empty relation with the same columns.
#}
{% macro read_wikipedia_interim(kind, folder='wikipedia') -%}
    {%- set reference_type = "STRUCT(template VARCHAR, doi VARCHAR, title VARCHAR, venue VARCHAR, year INTEGER, url VARCHAR, authors VARCHAR[], ref_name VARCHAR)[]" -%}
    {%- if kind == 'new_taxa' -%}
        {%- set columns = {
            'page_title': 'VARCHAR', 'revid': 'BIGINT', 'section_path': 'VARCHAR[]',
            'table_index': 'INTEGER', 'row_index': 'INTEGER',
            'name': 'VARCHAR', 'name_link': 'VARCHAR', 'novelty': 'VARCHAR', 'status': 'VARCHAR',
            'authors': 'VARCHAR', 'age': 'VARCHAR', 'age_links': 'VARCHAR[]',
            'type_locality': 'VARCHAR', 'type_locality_links': 'VARCHAR[]',
            'countries': 'VARCHAR[]', 'regions': 'VARCHAR[]', 'notes': 'VARCHAR', 'note_links': 'VARCHAR[]',
            'images': 'VARCHAR[]', 'references': reference_type, 'parse_warnings': 'VARCHAR[]',
            'revision_timestamp': 'TIMESTAMPTZ', 'taxon_group': 'VARCHAR'
        } -%}
    {%- elif kind == 'research' -%}
        {%- set columns = {
            'page_title': 'VARCHAR', 'revid': 'BIGINT', 'research_id': 'VARCHAR',
            'section_path': 'VARCHAR[]', 'text': 'VARCHAR',
            'links': 'VARCHAR[]', 'italic_links': 'VARCHAR[]', 'italic_names': 'VARCHAR[]',
            'references': reference_type, 'parse_warnings': 'VARCHAR[]',
            'revision_timestamp': 'TIMESTAMPTZ', 'taxon_group': 'VARCHAR'
        } -%}
    {%- else -%}
        {{ exceptions.raise_compiler_error("Unknown Wikipedia interim kind: " ~ kind) }}
    {%- endif -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/interim/" ~ folder ~ "/*/*/" ~ kind ~ ".jsonl" -%}
    {%- set found = 1 -%}
    {%- if execute and folder != 'wikipedia' -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
    read_json(
        '{{ path }}',
        format = 'newline_delimited',
        columns = { {% for name, type in columns.items() %}"{{ name }}": '{{ type }}'{% if not loop.last %}, {% endif %}{% endfor %} }
    )
    {%- else -%}
    (select {% for name, type in columns.items() %}cast(null as {{ type }}) as "{{ name }}"{% if not loop.last %}, {% endif %}{% endfor %} limit 0)
    {%- endif -%}
{%- endmacro %}
