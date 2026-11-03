# D10 — Detección de cambios barata antes del pipeline completo

- **Estado:** aceptada (2026-10-31, Fase 1)
- **Relacionadas:** [D4](0004-comandos-independientes-del-orquestador.md) · [ALCANCE §14](../../ALCANCE.md#14-contrato-de-comandos-del-pipeline)

## Contexto
El pipeline corre cada día, pero la mayoría de los días no cambia nada en las páginas anuales. Lanzar la ingesta completa cada día gasta peticiones a fuentes gratuitas (PBDB, Crossref, Commons) y cuota del LLM sin necesidad.

## Decisión
`paleo check` hace **una petición ligera por página anual** (solo el ID de la última revisión, sin contenido) y la compara con la última guardada. Sale con:
- **0:** algo cambió; se ejecuta todo;
- **1:** nada nuevo; solo se reconstruyen el almacén y la web, y se escribe el registro de la ejecución;
- **2:** la comprobación falló; se ejecuta todo, para que el error salga en la ingesta y en el informe, en vez de pasar por «sin cambios».

Los lunes se ejecuta todo siempre (resumen semanal), y también en las ejecuciones manuales. Las fuentes mensuales tienen su propia frescura (`RawStore.is_fresh`).

## Alternativas consideradas
- **Ejecutarlo todo cada día:** más sencillo, pero gasta las cuotas gratuitas y hace más lento el pipeline.
- **Escuchar los cambios de Wikipedia en directo** (EventStreams): necesita un proceso siempre encendido. Está en el backlog.

## Consecuencias
- **A favor:**
  - un día sin cambios cuesta segundos y unas pocas peticiones;
  - el registro de ejecuciones (`runs/`) demuestra que el pipeline corrió aunque no hubiera nada nuevo.
- **En contra:**
  - un cambio en una fuente que no sea la página anual se ve en la siguiente ejecución completa o mensual, no al momento;
  - el código 2 es una lección aprendida: al principio un fallo de red parecía «sin cambios».

## Pruebas
- `check` en [`src/paleo/cli.py`](../../src/paleo/cli.py) y el paso «Anything new?» de [`pipeline.yml`](../../.github/workflows/pipeline.yml).
- `has_new_revision` en [`src/paleo/ingest/wikipedia.py`](../../src/paleo/ingest/wikipedia.py) y sus tests en [`tests/test_ingest_wikipedia.py`](../../tests/test_ingest_wikipedia.py).
