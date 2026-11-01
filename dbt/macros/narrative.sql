{#
  Read the narrative pipeline output (paleo facts / paleo write):
  $PALEO_DATA_DIR/derived/facts/<taxon_key>.json and
  $PALEO_DATA_DIR/derived/texts/<taxon_key>.<lang>.json (verified texts only;
  failed ones live in derived/texts_review and are never published), and
  $PALEO_DATA_DIR/derived/study_titles/es.json (paleo titles).
#}
{% macro read_narrative(kind) -%}
    {%- if kind == 'texts' -%}
    read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/derived/texts/*.json',
        format = 'auto',
        columns = {
            taxon: 'VARCHAR', taxon_key: 'VARCHAR', lang: 'VARCHAR', status: 'VARCHAR',
            generator: 'VARCHAR', prompt_version: 'VARCHAR', facts_hash: 'VARCHAR',
            generated_at: 'TIMESTAMPTZ', word_count: 'INTEGER', problems: 'VARCHAR[]',
            sections: 'JSON'
        }
    )
    {%- elif kind == 'facts' -%}
    read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/derived/facts/*.json',
        format = 'auto',
        columns = {
            taxon: 'VARCHAR', taxon_key: 'VARCHAR', generator: 'VARCHAR',
            prompt_version: 'VARCHAR', sources_hash: 'VARCHAR', generated_at: 'TIMESTAMPTZ',
            citations: 'JSON', facts: 'JSON', rejected: 'JSON'
        }
    )
    {%- elif kind == 'study_titles' -%}
    read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/derived/study_titles/*.json',
        format = 'array',
        columns = {
            doi: 'VARCHAR', title: 'VARCHAR', title_es: 'VARCHAR', generator: 'VARCHAR',
            prompt_version: 'VARCHAR', translated_at: 'TIMESTAMPTZ'
        }
    )
    {%- else -%}
    {{ exceptions.raise_compiler_error("Unknown narrative kind: " ~ kind) }}
    {%- endif -%}
{%- endmacro %}
