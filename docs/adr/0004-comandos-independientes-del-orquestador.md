# D4 — Comandos independientes del orquestador

- **Estado:** aceptada (2026-10-31); demostrada en la Fase 2 (2026-11-02)
- **Relacionadas:** [D3](0003-el-estado-vive-en-git.md), [D10](0010-deteccion-de-cambios-barata.md) · [ALCANCE §14](../../ALCANCE.md#14-contrato-de-comandos-del-pipeline) · [Documento de la Fase 2](../fases/fase-2.md)

## Contexto
El pipeline publica con GitHub Actions (gratis, junto al repo), pero Airflow es el orquestador que más piden las ofertas, y hay que poder ejecutarlo todo en local. Si la lógica viviera en el YAML de Actions o en los DAGs, habría dos pipelines que divergen.

## Decisión
Toda la lógica está en una CLI, `paleo` (`ingest`, `parse`, `facts`, `write`, `build`, `site`, `check`, `report`…), con un contrato fijo de entradas, salidas y códigos de salida. Actions y Airflow **solo llaman a esos comandos**, en el mismo orden.

## Alternativas consideradas
- **Lógica en operadores de Airflow** (PythonOperator con el código dentro): ata el pipeline a Airflow y deja Actions sin nada que llamar.
- **Scripts sueltos por paso:** sin contrato común, cada orquestador acaba con su variante.

## Consecuencias
- **A favor:**
  - cambiar de orquestador no toca `src/paleo/`, `dbt/` ni `pipeline.yml` (la Fase 2 lo demostró);
  - cada paso se puede probar en local con un comando.
- **En contra:**
  - hay que mantener dos descripciones del orden de los pasos (el YAML y la lista del DAG). Un test lo vigila;
  - el orquestador hereda suposiciones implícitas: en la Fase 2, `dbt` no estaba en el PATH de Airflow.

## Pruebas
- [`airflow/dags/paleo_steps.py`](../../airflow/dags/paleo_steps.py), la lista única de pasos, y [`tests/test_airflow_steps.py`](../../tests/test_airflow_steps.py), que la compara con `pipeline.yml`.
- Paridad: **0 diferencias** en 33 tablas y 97 archivos de la web entre el CI y el DAG `paleo_ci_parity` ([Fase 2, §7](../fases/fase-2.md#7-resultados-reales-2026-11-02)).
