# D5 — Spark solo para GBIF, en local y medido contra DuckDB

- **Estado:** aceptada (2026-10-31); revisada el 2026-11-02 (DAG mensual)
- **Relacionadas:** [D1](0001-sin-spark-en-la-capa-diaria.md) · [ALCANCE §6](../../ALCANCE.md#6-arquitectura) · [Documento de la Fase 3](../fases/fase-3.md)

## Contexto
GBIF tiene los especímenes de museo: 932.494 registros fósiles de cordados en la descarga filtrada, con nombres que no siempre coinciden con los de PBDB. Es el único job del proyecto cercano al tamaño en que Spark se plantea, y Spark es una habilidad que conviene demostrar. Pero demostrarlo no justifica usarlo donde no toca (D1).

## Decisión
- El job de reconciliación de GBIF (exacto → sinónimo → errata, y agregados por género, institución y país) se escribe **en Spark y en DuckDB**, sobre **una sola especificación** (`paleo/gbif_job/spec.py`).
- Se mide con datos reales. El motor por defecto es el que gane: **DuckDB**.
- Spark corre en local (`local[*]`) y en Docker dentro de Airflow. No hay clúster de pago (A9). Databricks Free Edition es opcional.

## Alternativas consideradas
- **Solo Spark:** 16 veces más lento y el doble de código para este volumen.
- **Solo DuckDB:** el resultado sería el mismo, pero no habría medida ni demostración de Spark.
- **Clúster gestionado** (EMR, Dataproc): rompe los 0 €.

## Consecuencias
- **A favor:**
  - la elección del motor tiene datos detrás: tiempo, memoria y líneas de código;
  - los dos motores dan extractos idénticos, comprobados con huellas SHA-256.
- **En contra:** hay dos implementaciones que mantener. El test de paridad con el fixture lo hace barato.

## Revisión (2026-11-02)
El DAG mensual de Airflow ejecuta **a propósito** la variante de Spark, en una imagen con Java, para que el job funcione de verdad dentro del orquestador. Cuesta ~13 s una vez al mes. `paleo gbif reconcile` usa DuckDB por defecto.

## Pruebas
- [`benchmarks/gbif/results.md`](../../benchmarks/gbif/results.md), con 932.494 filas:
  - **DuckDB:** 0,86 s y 459 MB;
  - **Spark:** 13,71 s y 1.504 MB, de los que ~7,5 s son coste fijo;
  - **código:** 124 líneas frente a 242.
- [`tests/test_gbif_job.py`](../../tests/test_gbif_job.py): los mismos extractos con los dos motores.
