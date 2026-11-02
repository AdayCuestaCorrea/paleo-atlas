{#
  Read every version written by paleo.store.RawStore for one source/kind:
  $PALEO_DATA_DIR/raw/<source>/<kind>/<key>/<YYYY-MM-DD>.json
  The payload stays JSON; staging models extract what they need.
#}
{% macro read_raw_store(source, kind) -%}
    read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/raw/{{ source }}/{{ kind }}/*/*.json',
        format = 'auto',
        columns = {
            key: 'VARCHAR', source: 'VARCHAR', kind: 'VARCHAR',
            version_date: 'DATE', fetched_at: 'TIMESTAMPTZ', payload: 'JSON'
        }
    )
{%- endmacro %}

{#
  Decode the common HTML entities. Crossref sometimes escapes them twice
  ("&amp;amp;"), so strip_html applies this twice.
#}
{% macro unescape_html(expr) -%}
    replace(replace(replace(replace(replace(replace(
        {{ expr }}, '&amp;', '&'), '&lt;', '<'), '&gt;', '>'), '&quot;', '"'), '&#39;', chr(39)), '&nbsp;', ' ')
{%- endmacro %}

{# Strip HTML tags, decode entities and collapse whitespace (Commons and Crossref use HTML). #}
{% macro strip_html(expr) -%}
    nullif(trim(regexp_replace(regexp_replace(
        {{ unescape_html(unescape_html(expr)) }}, '<[^>]*>', '', 'g'), '\s+', ' ', 'g')), '')
{%- endmacro %}

{# "Tyrannosaurus rex" -> "tyrannosaurus-rex": stable key for a taxon page. #}
{% macro taxon_key(expr) -%}
    lower(regexp_replace(trim({{ expr }}), '[^A-Za-z0-9]+', '-', 'g'))
{%- endmacro %}

{#
  Pipeline run log written by paleo.report: $PALEO_DATA_DIR/runs/<YYYY-MM-DD>.json,
  a JSON array with one item per run (also the runs that found nothing new).
#}
{% macro read_runs() -%}
    read_json(
        '{{ env_var("PALEO_DATA_DIR", "../data") }}/runs/*.json',
        format = 'array',
        columns = {
            started_at: 'TIMESTAMPTZ', finished_at: 'TIMESTAMPTZ', trigger: 'VARCHAR',
            changed: 'BOOLEAN', status: 'VARCHAR'
        }
    )
{%- endmacro %}

{#
  Parquet files that may not exist yet (the GBIF extract before the first monthly run):
  the files when there are some, otherwise an empty relation with the given columns,
  so the daily build never fails for lack of them.
#}
{% macro read_optional_parquet(pattern, empty_columns) -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/" ~ pattern -%}
    {%- set found = 0 -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
        read_parquet('{{ path }}', union_by_name = true)
    {%- else -%}
        (select {% for name, type in empty_columns.items() %}cast(null as {{ type }}) as {{ name }}{% if not loop.last %}, {% endif %}{% endfor %} limit 0)
    {%- endif -%}
{%- endmacro %}

{# read_raw_store for a source that may have no versions yet (GBIF before its first run). #}
{% macro read_optional_raw_store(source, kind) -%}
    {%- set path = env_var("PALEO_DATA_DIR", "../data") ~ "/raw/" ~ source ~ "/" ~ kind ~ "/*/*.json" -%}
    {%- set found = 0 -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')").columns[0].values()[0] -%}
    {%- endif -%}
    {%- if found > 0 -%}
        {{ read_raw_store(source, kind) }}
    {%- else -%}
        (select cast(null as varchar) as key, cast(null as varchar) as source,
                cast(null as varchar) as kind, cast(null as date) as version_date,
                cast(null as timestamptz) as fetched_at, cast(null as json) as payload limit 0)
    {%- endif -%}
{%- endmacro %}
