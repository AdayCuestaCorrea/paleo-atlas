{#
  Read the narrative pipeline output (paleo facts / paleo write):
  $PALEO_DATA_DIR/derived/facts/<taxon_key>.json and
  $PALEO_DATA_DIR/derived/texts/<taxon_key>.<lang>.json (verified texts only;
  failed ones live in derived/texts_review and are never published), and
  $PALEO_DATA_DIR/derived/study_titles/es.json (paleo titles), and
  $PALEO_DATA_DIR/derived/news/labels.json (paleo news classify; optional).
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
    {%- elif kind == 'news_labels' -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/derived/news/labels.json" -%}
    {%- set found = 0 -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
    read_json(
        '{{ path }}',
        format = 'array',
        columns = {
            key: 'VARCHAR', category: 'VARCHAR', taxa: 'VARCHAR[]', input_hash: 'VARCHAR',
            generator: 'VARCHAR', prompt_version: 'VARCHAR', classified_at: 'TIMESTAMPTZ'
        }
    )
    {%- else -%}
    (select cast(null as varchar) as key, cast(null as varchar) as category,
            cast(null as varchar[]) as taxa, cast(null as varchar) as input_hash,
            cast(null as varchar) as generator, cast(null as varchar) as prompt_version,
            cast(null as timestamptz) as classified_at limit 0)
    {%- endif -%}
    {%- else -%}
    {{ exceptions.raise_compiler_error("Unknown narrative kind: " ~ kind) }}
    {%- endif -%}
{%- endmacro %}
