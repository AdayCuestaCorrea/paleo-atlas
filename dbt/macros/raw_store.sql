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
