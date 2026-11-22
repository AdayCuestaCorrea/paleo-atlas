{#
  Kind of a gallery image from lower-cased text (file name or description).
  'excluded' for cladograms, maps, logos, information panels, diagrams of soft
  tissue...; 'reconstruction' when it only says "reconstruction" (a life
  restoration or a skeletal one: fct_taxon_image decides with the other text);
  'other' when nothing matches. Phase 7 (a review of 15 pages): drawings before
  skeletons, "skeletal" before life, casts and replicas as fossils, and a
  comparison that is not about size is not a fossil.
#}
{% macro image_kind(expr) -%}
    case
        when regexp_matches({{ expr }}, 'clad(ogram|e)|phylogen|logo|icon|flag|signature|stamp|\bmaps?\b|mapa|chart|cartoon|chromium|toy|lego|statue|sculpture|escultura|christmas|xmas|navidad|costume|disfraz|plush|peluche|figurine|\bmodel\b|modell?ed|maqueta|growth|graph|\bsigns?\b|information|infotafel|ligament|musculat|muscles?\b')
            then 'excluded'
        when regexp_matches({{ expr }}, '\bskin\b|\bpiel\b') then 'fossil'
        when regexp_matches({{ expr }}, 'size[ _-]?comparison|size chart|scale diagram|comparación de tamaño|tamaño|relative sizes|\bsizes? of\b|\bscale\b') then 'size'
        when regexp_matches({{ expr }}, 'life restoration|life reconstruction|paleo-illustration') then 'life'
        when regexp_matches({{ expr }}, 'skeletal|esquelética') then 'skeleton'
        when regexp_matches({{ expr }}, 'restoration|paleoart|drawing|pencil|painting|illustration|ilustraci|\blife\b') then 'life'
        when regexp_matches({{ expr }}, '\bcasts?\b|replica|réplica|fossils? reconstruction') then 'fossil'
        when regexp_matches({{ expr }}, 'skeleton|esqueleto|\bmount|montaje') then 'skeleton'
        when regexp_matches({{ expr }}, 'skull|crani|cráneo|schädel|crâne') then 'skull'
        when regexp_matches({{ expr }}, 'tooth|teeth|diente|dental') then 'tooth'
        when regexp_matches({{ expr }}, '\bclaw|ungual|garra') then 'claw'
        when regexp_matches({{ expr }}, 'track(way)?s?\b|footprint|ichn|huella') then 'track'
        when regexp_matches({{ expr }}, '\beggs?\b|huevo|\bnest') then 'egg'
        when regexp_matches({{ expr }}, 'reconstruction|reconstrucci') then 'reconstruction'
        when regexp_matches({{ expr }}, 'holotyp|holotipo') then 'holotype'
        when regexp_matches({{ expr }}, 'locality|formation|formación|outcrop|quarry|yacimiento|excavat|stratigraph') then 'site'
        when regexp_matches({{ expr }}, 'comparison|comparación|diagram') then 'other'
        when regexp_matches({{ expr }}, 'fossil|fósil|\bbones?\b|hueso|specimen|ejemplar|vertebr|centrum|femur|fémur|\bjaw|mandib|frill')
            then 'fossil'
        else 'other'
    end
{%- endmacro %}
