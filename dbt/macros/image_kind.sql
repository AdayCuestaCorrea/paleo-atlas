{#
  Kind of a gallery image from lower-cased text (file name or description).
  'excluded' for cladograms, maps, logos...; 'other' when nothing matches.
#}
{% macro image_kind(expr) -%}
    case
        when regexp_matches({{ expr }}, 'clad(ogram|e)|phylogen|logo|icon|flag|signature|stamp|\bmaps?\b|mapa|chart|cartoon|chromium|toy|lego')
            then 'excluded'
        when regexp_matches({{ expr }}, 'size[ _-]?comparison|size chart|scale diagram|comparación de tamaño|tamaño') then 'size'
        when regexp_matches({{ expr }}, 'skeletal|skeleton|esqueleto|\bmount|montaje') then 'skeleton'
        when regexp_matches({{ expr }}, 'skull|crani|cráneo|schädel|crâne') then 'skull'
        when regexp_matches({{ expr }}, 'tooth|teeth|diente|dental') then 'tooth'
        when regexp_matches({{ expr }}, '\bclaw|ungual|garra') then 'claw'
        when regexp_matches({{ expr }}, 'track(way)?s?\b|footprint|ichn|huella') then 'track'
        when regexp_matches({{ expr }}, '\beggs?\b|huevo|\bnest') then 'egg'
        when regexp_matches({{ expr }}, 'restoration|reconstruction|\blife\b|paleoart|reconstrucci|illustration|ilustraci') then 'life'
        when regexp_matches({{ expr }}, 'holotyp|holotipo') then 'holotype'
        when regexp_matches({{ expr }}, 'locality|formation|formación|outcrop|quarry|yacimiento|excavat|stratigraph') then 'site'
        when regexp_matches({{ expr }}, 'fossil|fósil|\bbones?\b|hueso|specimen|ejemplar|vertebr|centrum|femur|fémur|\bjaw|mandib|frill|museum|museo')
            then 'fossil'
        else 'other'
    end
{%- endmacro %}
