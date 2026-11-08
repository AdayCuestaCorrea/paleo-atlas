# Documentos de fase

Un documento por fase terminada que explica **por qué** se hizo así, no solo **qué** se hizo:

- los conceptos, desde cero;
- cómo funciona en este repositorio;
- cómo se comprueba;
- qué salió mal;
- cómo defenderlo en una entrevista.

| Documento | Para qué sirve |
|---|---|
| [`ALCANCE.md`](../../ALCANCE.md) | **Fuente de verdad** de qué se hace, con fases, casillas, decisiones y registro de cambios |
| `docs/fases/fase-N.md` (este directorio) | La explicación de cada fase: porqué, conceptos, funcionamiento, comprobación y lecciones |
| [`docs/adr/`](../adr/README.md) | Una página por decisión de arquitectura (D1–D10), en formato breve |

Si algo de aquí contradice a `ALCANCE.md`, manda `ALCANCE.md` y este documento está desfasado.

Cada documento se escribe al cerrar su fase. Va en español primero y en inglés después, como `ALCANCE.md` y `SCOPE.md`.

| Fase | Documento | Estado |
|---|---|---|
| 1 — MVP (arcosaurios, bilingüe) | [fase-1.md](fase-1.md) | Implementada; esperando 2 semanas de ejecución autónoma |
| 2 — Airflow | [fase-2.md](fase-2.md) | Implementada |
| 3 — Enciclopedia, ampliación y Spark | [fase-3.md](fase-3.md) | En curso: hitos 1–5 y 7 hechos; el 6 (textos de los géneros con la GPU) avanza por lotes |
| 4 — Portfolio | [fase-4.md](fase-4.md) | Hecha (2026-11-08) |
| 5 — IA y noticias | [fase-5.md](fase-5.md) | Hecha (noticias y glosario publicados el 2026-11-08; enlace a fichas corregido en la v41) |
| 6 — Comparador de tamaños (el 3D pasó al backlog) | [fase-6.md](fase-6.md) | Hecha y publicada (2026-11-08) |
