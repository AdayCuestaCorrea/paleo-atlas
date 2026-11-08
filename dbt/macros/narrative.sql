{#
  Read the narrative pipeline output (paleo facts / paleo write):
  $PALEO_DATA_DIR/derived/facts/<taxon_key>.json and
  $PALEO_DATA_DIR/derived/texts/<taxon_key>.<lang>.json (verified texts only;
  failed ones live in derived/texts_review and are never published), and
  $PALEO_DATA_DIR/derived/study_titles/es.json (paleo titles), and
  $PALEO_DATA_DIR/derived/news/labels.json and groups.json (paleo news classify and
  dedup; optional), and $PALEO_DATA_DIR/derived/glossary/<term>.<lang>.json (paleo
  glossary write; optional), and $PALEO_DATA_DIR/derived/sizes/sizes.json (paleo sizes
  extract; optional).
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
    {%- elif kind == 'news_groups' -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/derived/news/groups.json" -%}
    {%- set found = 0 -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
    read_json('{{ path }}', format = 'array',
              columns = {key: 'VARCHAR', "group": 'VARCHAR', method: 'VARCHAR', threshold: 'DOUBLE'})
    {%- else -%}
    (select cast(null as varchar) as key, cast(null as varchar) as "group",
            cast(null as varchar) as method, cast(null as double) as threshold limit 0)
    {%- endif -%}
    {%- elif kind == 'glossary' -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/derived/glossary/*.json" -%}
    {%- set found = 0 -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
    read_json('{{ path }}', format = 'auto', columns = {
        term_id: 'VARCHAR', lang: 'VARCHAR', term: 'VARCHAR', definition: 'VARCHAR',
        status: 'VARCHAR', problems: 'VARCHAR[]',
        source: 'STRUCT(lang VARCHAR, title VARCHAR, revid BIGINT)', generator: 'VARCHAR',
        judge: 'VARCHAR', prompt_version: 'VARCHAR', judge_version: 'VARCHAR',
        generated_at: 'TIMESTAMPTZ'})
    {%- else -%}
    (select cast(null as varchar) as term_id, cast(null as varchar) as lang,
            cast(null as varchar) as term, cast(null as varchar) as definition,
            cast(null as varchar) as status, cast(null as varchar[]) as problems,
            cast(null as STRUCT(lang VARCHAR, title VARCHAR, revid BIGINT)) as source,
            cast(null as varchar) as generator, cast(null as varchar) as judge,
            cast(null as varchar) as prompt_version, cast(null as varchar) as judge_version,
            cast(null as timestamptz) as generated_at limit 0)
    {%- endif -%}
    {%- elif kind == 'sizes' -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/derived/sizes/sizes.json" -%}
    {%- set found = 0 -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
    read_json('{{ path }}', format = 'array', columns = {
        taxon_key: 'VARCHAR', taxon: 'VARCHAR', min_m: 'DOUBLE', max_m: 'DOUBLE',
        qualifier: 'VARCHAR', main_fact_id: 'VARCHAR', span_min_m: 'DOUBLE',
        span_max_m: 'DOUBLE', partial_remains: 'BOOLEAN', only_old_estimates: 'BOOLEAN',
        estimates: 'JSON'})
    {%- else -%}
    (select cast(null as varchar) as taxon_key, cast(null as varchar) as taxon,
            cast(null as double) as min_m, cast(null as double) as max_m,
            cast(null as varchar) as qualifier, cast(null as varchar) as main_fact_id,
            cast(null as double) as span_min_m, cast(null as double) as span_max_m,
            cast(null as boolean) as partial_remains, cast(null as boolean) as only_old_estimates,
            cast(null as json) as estimates limit 0)
    {%- endif -%}
    {%- else -%}
    {{ exceptions.raise_compiler_error("Unknown narrative kind: " ~ kind) }}
    {%- endif -%}
{%- endmacro %}
