# D3 — El estado vive en git; el almacén se reconstruye entero

- **Estado:** aceptada (2026-10-31); revisada el 2026-11-02 (A11) y el 2026-11-03 (caché del wikitext)
- **Relacionadas:** [D2](0002-duckdb-en-vez-de-base-de-datos-alojada.md), [D9](0009-historial-scd2-en-sql.md) · [ALCANCE §6](../../ALCANCE.md#6-arquitectura)

## Contexto
El pipeline corre en runners de GitHub Actions que nacen vacíos cada día, sin disco persistente ni base de datos gratuita (D2). Aun así necesita recordar qué ha visto (para el historial, D9) y poder auditarlo.

## Decisión
- **Las respuestas crudas de las fuentes se versionan en git**, en la rama `data`. Las guarda `RawStore`, que solo escribe una versión nueva si el contenido cambió (`save_if_changed`). También van ahí los derivados públicos: hechos, textos y títulos traducidos.
- **El almacén DuckDB se reconstruye desde cero** en cada ejecución a partir de ese crudo. Nunca se actualiza en sitio.
- **Lo privado no entra nunca:** abstracts, citas privadas, caché del LLM y wikitext completo de los géneros viven en `cache/`, sin versionar.

## Alternativas consideradas
- **Base de datos persistente con actualizaciones incrementales:** cuesta dinero o mantenimiento (D2), y un error deja el estado corrupto sin forma fácil de volver atrás.
- **Almacenamiento de objetos** (S3, GCS): no hay plan gratuito sin tarjeta, y se pierde el historial con fechas que da git.
- **Cache de Actions:** caduca y no es auditable.

## Consecuencias
- **A favor:**
  - **idempotente:** repetir una ejecución da el mismo resultado;
  - **auditable:** cada dato publicado se puede rastrear hasta la respuesta cruda y su fecha;
  - volver atrás es un `git revert`;
  - el historial sale gratis (D9).
- **En contra:**
  - la rama `data` crece (unos 180 MB de crudo en la Fase 3). Por eso se usa `vocab=com` en PBDB y no se versionan las descargas grandes, que se pueden reproducir: la descarga de GBIF tiene DOI (A11), y el wikitext, `oldid`;
  - hace falta una salvaguarda: el commit de Actions se niega si hay `cache/`, `interim/` o `.duckdb`.

## Pruebas
- [`src/paleo/store.py`](../../src/paleo/store.py) (`save_if_changed`, `is_fresh`) y [`tests/test_store.py`](../../tests/test_store.py).
- La salvaguarda, en el paso «Commit to the data branch» de [`pipeline.yml`](../../.github/workflows/pipeline.yml).
- Huella del almacén y de la web reproducible entre motores y orquestadores ([`scripts/fingerprint.py`](../../scripts/fingerprint.py)).
