# D2 — DuckDB en vez de una base de datos alojada

- **Estado:** aceptada (2026-10-31, Fase 1)
- **Relacionadas:** [D1](0001-sin-spark-en-la-capa-diaria.md), [D3](0003-el-estado-vive-en-git.md) · [ALCANCE §6](../../ALCANCE.md#6-arquitectura)

## Contexto
Hace falta un almacén analítico donde dbt construya staging, intermediate y marts, y del que la web lea. Restricciones: 0 €, sin servidores que mantener, y que funcione igual en el portátil, en GitHub Actions y en Airflow.

## Decisión
**DuckDB** en un archivo local (`data/warehouse.duckdb`), con **dbt-duckdb**. El archivo no se versiona: se reconstruye entero en cada ejecución (D3).

## Alternativas consideradas
- **Postgres alojado** (Supabase, Neon…): los planes gratuitos tienen límites de tamaño y de inactividad. Además hay credenciales que custodiar, red en cada consulta y un estado que vive fuera del repositorio.
- **BigQuery o Snowflake:** muy demandados, pero con facturación por consulta y una cuenta con tarjeta. Rompen la regla de 0 € al primer descuido.
- **SQLite:** gratis y local, pero orientado a transacciones y no a análisis, y sin adaptador maduro de dbt para este uso.

## Consecuencias
- **A favor:**
  - `paleo build` (todo dbt: 51 modelos y 138 tests) tarda **segundos** con datos reales;
  - el mismo SQL corre en CI, en Actions y en Airflow sin configurar nada;
  - DuckDB lee JSON y Parquet directamente del almacén crudo.
- **En contra:**
  - un solo escritor a la vez (no importa: un pipeline, `max_active_runs=1`);
  - el SQL usa dialecto de DuckDB (`qualify`, listas, `struct`), que habría que adaptar si se migra.
- **Cuándo cambiaría:** con varios escritores concurrentes o consultas en vivo desde la web, aunque la web es estática.

## Pruebas
- Modelos en [`dbt/models/`](../../dbt/models/); lecturas tipadas del crudo en [`dbt/macros/raw_store.sql`](../../dbt/macros/raw_store.sql).
- El almacén, fuera de git: [`.gitignore`](../../.gitignore) y la salvaguarda del commit en [`pipeline.yml`](../../.github/workflows/pipeline.yml).
