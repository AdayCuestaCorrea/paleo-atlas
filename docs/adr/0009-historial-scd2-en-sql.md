# D9 — Historial con SCD tipo 2 en SQL desde las versiones crudas

- **Estado:** aceptada (2026-10-31, Fase 1); revisada el 2026-11-03 (historial hacia atrás, Fase 3)
- **Relacionadas:** [D3](0003-el-estado-vive-en-git.md) · [ALCANCE §9](../../ALCANCE.md#9-historial-de-cambios-por-taxón)

## Contexto
Cada ficha tiene una línea temporal con todo lo que ha cambiado sobre el taxón: el estatus, los autores, la edad, el estudio. Lo que no se captura el día en que cambia no se puede reconstruir después. Y el almacén se reconstruye desde cero en cada ejecución (D3).

## Decisión
El historial se calcula **en SQL, como un SCD tipo 2** (*slowly changing dimension*: una fila por versión, con `valid_from` y `valid_to`), sobre **todas las versiones crudas** guardadas en git. Una versión nueva empieza solo cuando cambia algún campo, y cada cambio es un evento `entry_changed`.

## Alternativas consideradas
- **`dbt snapshots`:** guardan el estado *entre* ejecuciones en la propia base de datos. Con un almacén que se reconstruye cada día en un runner vacío, el historial se perdería en cada ejecución de Actions.
- **Una tabla de historial mantenida aparte:** otro estado mutable fuera de git, justo lo que D3 evita.

## Consecuencias
- **A favor:**
  - el historial es reproducible: reconstruir desde cero da exactamente el mismo;
  - se puede recalcular con reglas nuevas sobre todo el pasado.
- **En contra:**
  - cada ejecución lee todas las versiones (barato con DuckDB);
  - hay que guardar las versiones desde el día 1, porque no se recuperan después.

## Revisión (2026-11-03, Fase 3)
El historial anterior a 2026 se **reconstruye** con las opiniones taxonómicas de PBDB y las páginas anuales de 2009–2025, con precisión de año. Va en la misma tabla de eventos con `origin = backfill`, para que no entre en «Última hora». Lo seguido desde el día 1 lleva `origin = tracked`.

## Pruebas
- [`int_new_taxa_history.sql`](../../dbt/models/intermediate/int_new_taxa_history.sql) y su test unitario `new_taxa_history_starts_a_version_only_when_a_field_changes` ([`_intermediate__models.yml`](../../dbt/models/intermediate/_intermediate__models.yml)).
- Historial hacia atrás: [`int_opinion_events.sql`](../../dbt/models/intermediate/int_opinion_events.sql), con el test unitario de *Brontosaurus*.
