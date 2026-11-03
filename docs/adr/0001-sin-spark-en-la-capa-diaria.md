# D1 — Sin Spark en la capa diaria

- **Estado:** aceptada (2026-10-31, Fase 1)
- **Relacionadas:** [D2](0002-duckdb-en-vez-de-base-de-datos-alojada.md), [D5](0005-spark-solo-para-gbif-y-medido.md) · [ALCANCE §6](../../ALCANCE.md#6-arquitectura)

## Contexto
El pipeline diario lee las páginas anuales de Wikipedia, consulta PBDB, Crossref y Commons, reconstruye el almacén y genera la web. Son unos cientos de taxones nuevos al año y unos miles de registros por fuente. Spark es lo que piden muchas ofertas de Data Engineer, y existía la tentación de usarlo «porque sí».

## Decisión
La capa diaria no usa Spark. Python para la ingesta, dbt sobre DuckDB para las transformaciones y un generador propio para la web.

## Alternativas consideradas
- **Spark en todo el pipeline.** Un arranque de ~7,5 s por ejecución (JVM, sesión, planificación), una JVM en el runner de Actions y el doble de código para la misma lógica (ver D5), todo para datos que caben en memoria muchas veces.
- **Pandas en vez de SQL.** Válido para este volumen, pero se pierde lo que da dbt: linaje, tests de datos y documentación de los modelos.

## Consecuencias
- **A favor:**
  - el pipeline diario completo dura **~1 min** en GitHub Actions;
  - una sola dependencia de motor (DuckDB) y nada de Java en el runner.
- **En contra:** Spark tiene que demostrarse en otro sitio. Se hizo en la Fase 3, en el único job con un volumen que se le acerca (D5).
- **Cuándo cambiaría:** si una fuente diaria superara lo que cabe en la memoria de un runner, del orden de decenas de millones de filas.

## Pruebas
- [Benchmark de GBIF](../../benchmarks/gbif/results.md): con 932.494 filas, DuckDB tarda 0,86 s y Spark 13,71 s.
- Duración del pipeline diario: [ALCANCE §17](../../ALCANCE.md#17-métricas-del-proyecto-para-cv-y-entrevistas).
