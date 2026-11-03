# D8 — Bilingüe desde el principio

- **Estado:** aceptada (2026-10-31, Fase 1)
- **Relacionadas:** [D7](0007-fichas-narrativas-propias-verificadas.md) · [ALCANCE §11](../../ALCANCE.md#11-la-web-idiomas-páginas-y-ficha)

## Contexto
El público es hispanohablante y de habla inglesa, y casi todas las fuentes están en inglés. Añadir un segundo idioma al final suele obligar a reescribir plantillas, URLs y datos.

## Decisión
- **Los datos no tienen idioma:** el almacén guarda claves, nombres científicos y cifras.
- **Solo se duplican los textos y las plantillas:**
  - los textos de la interfaz, en `i18n/es.toml` y `i18n/en.toml`;
  - las plantillas que son prosa, como `assess.es` y `assess.en`;
  - las fichas narrativas, en dos versiones verificadas.
- Las URLs van por idioma (`/es/taxones/…`, `/en/taxa/…`) y cada página enlaza a la otra con `hreflang`.

## Alternativas consideradas
- **Solo inglés, y español después:** habría que rehacer las URLs y las plantillas, y los textos en español irían siempre por detrás.
- **Traducción automática en el navegador:** no controla los términos científicos («Cretácico Superior», «gola») ni se puede verificar.

## Consecuencias
- **A favor:**
  - añadir una página nueva cuesta lo mismo en los dos idiomas;
  - los términos (periodos, países, rangos) se traducen en un solo sitio (`paleo/site/terms.py`).
- **En contra:**
  - cada texto de la interfaz se escribe dos veces;
  - las fichas narrativas cuestan el doble de LLM y el español necesita su propia revisión (D7).

## Pruebas
- `test_both_languages_have_the_same_interface_strings` en [`tests/test_site.py`](../../tests/test_site.py): las dos tablas de textos tienen las mismas claves.
- `paleo site --check` comprueba que cada página tiene su alternativa en el otro idioma.
