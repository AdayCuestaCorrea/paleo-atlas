# Decisiones de arquitectura (ADR)

Un **ADR** (*Architecture Decision Record*) es una página corta que guarda **una** decisión de arquitectura:
- el problema que había;
- qué se decidió;
- qué alternativas se descartaron y por qué;
- qué cuesta la decisión.

Sirve para que dentro de un año (o en una entrevista) se pueda explicar el porqué sin depender de la memoria.

Las decisiones son las D1–D10 de [`ALCANCE.md` §6](../../ALCANCE.md#6-arquitectura). Si un ADR contradice a `ALCANCE.md`, manda `ALCANCE.md`. Cuando una decisión se matiza más tarde, se añade una sección «Revisión» con la fecha; no se reescribe la historia.

**Formato:** estado · contexto · decisión · alternativas consideradas · consecuencias · pruebas (enlaces al código, a los tests y a las cifras reales).

| ADR | Decisión | Estado |
|---|---|---|
| [D1](0001-sin-spark-en-la-capa-diaria.md) | Sin Spark en la capa diaria | Aceptada |
| [D2](0002-duckdb-en-vez-de-base-de-datos-alojada.md) | DuckDB en vez de una base de datos alojada | Aceptada |
| [D3](0003-el-estado-vive-en-git.md) | El estado vive en git; el almacén se reconstruye entero | Aceptada y revisada |
| [D4](0004-comandos-independientes-del-orquestador.md) | Comandos independientes del orquestador | Aceptada, demostrada en la Fase 2 |
| [D5](0005-spark-solo-para-gbif-y-medido.md) | Spark solo para GBIF, en local y medido contra DuckDB | Aceptada y revisada |
| [D6](0006-imagenes-solo-con-licencias-permitidas.md) | Imágenes y 3D solo con licencias permitidas | Aceptada |
| [D7](0007-fichas-narrativas-propias-verificadas.md) | Fichas narrativas propias: hechos con fuente, LLM y verificaciones | Aceptada y revisada |
| [D8](0008-bilingue-desde-el-principio.md) | Bilingüe desde el principio | Aceptada |
| [D9](0009-historial-scd2-en-sql.md) | Historial con SCD tipo 2 en SQL desde las versiones crudas | Aceptada y revisada |
| [D10](0010-deteccion-de-cambios-barata.md) | Detección de cambios barata antes del pipeline completo | Aceptada |

Restricciones comunes a todas:
- **0 €** (§18);
- **repositorio público**;
- **un solo desarrollador**;
- una web estática en GitHub Pages que se actualiza sola cada día.
