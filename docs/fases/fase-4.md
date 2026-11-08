# Fase 4 — Portfolio

> Alcance y casillas: [`ALCANCE.md` §7, Fase 4](../../ALCANCE.md#7-fases-y-entregables), [§17](../../ALCANCE.md#17-métricas-del-proyecto-para-cv-y-entrevistas) y [§20](../../ALCANCE.md#20-documentación-y-material-de-portfolio). Este documento explica el porqué.
>
> **Estado (2026-11-08): hecha.** README bilingüe y ADRs adelantados (2026-11-07 y 2026-11-03); interview pack, cifras de §17, entrada del CV, perfil de GitHub y proyecto en LinkedIn (ES y EN, publicado por el usuario) el 2026-11-08. `SCOPE.md` pasa a ser un resumen en inglés. El vídeo de demostración se descartó en la v35.

## 1. En una frase

Que cualquiera que llegue al proyecto (por el CV, LinkedIn o GitHub) entienda en un minuto **qué es**, y pueda **comprobar cada cifra** que se le cuenta en el repo o en la web pública.

## 2. El problema

Un proyecto de portfolio se lee en tres tiempos: unos segundos en el CV, un minuto en el README o en la web, y una conversación de entrevista. Cada uno necesita un formato distinto, pero las cifras tienen que ser **las mismas en todos** y tienen que poder comprobarse. Si el CV dice 207 tests y el README 302, el lector no sabe a cuál creer, y la cifra buena pierde valor.

Además, este proyecto cambia cada día: crecen las fichas narrativas y los tests, entran fuentes nuevas. Una cifra escrita de memoria se queda vieja en una semana.

## 3. Conceptos, desde cero

- **One-pager:** una página con el producto, la arquitectura, las cifras y cómo se evalúa la calidad. Es lo que se manda antes de una entrevista.
- **Postmortem:** qué funcionó, qué no y qué se cambiaría. En la industria se escribe tras un incidente, sin buscar culpables. Aquí se escribe sobre el proyecto entero, con lo que se repite entre fases.
- **Historia STAR:** una forma de contar un logro en entrevista: **S**ituación, **T**area, **A**cción y **R**esultado, con el resultado medido.
- **ADR (Architecture Decision Record):** una página por decisión, con contexto, alternativas y consecuencias. Responde a «¿por qué no usaste X?».
- **Cifra verificable:** una cifra con fecha y origen (una consulta al almacén, un `dbt ls`, un informe de ejecución) que otra persona puede repetir.

## 4. Cómo funciona aquí

| Pieza | Dónde | Para quién |
|---|---|---|
| README bilingüe | [`README.md`](../../README.md) / [`README.es.md`](../../README.es.md) | Quien llega al repo: qué es, capturas, arquitectura, cifras, cómo ejecutarlo |
| ADRs D1–D10 | [`docs/adr/`](../adr/README.md) | Las preguntas de «¿por qué no…?» |
| One-pager, postmortem e historias STAR (ES y EN) | [`docs/interview-pack/`](../interview-pack/one-pager.es.md) | Antes y durante una entrevista |
| Documentos de fase | [`docs/fases/`](README.md) | Estudiar y defender cada parte a fondo |
| Cifras con fecha | [`ALCANCE.md` §17](../../ALCANCE.md#17-métricas-del-proyecto-para-cv-y-entrevistas) | La única tabla de la que copian todos los demás |
| Página «Estado de los datos» | [web](https://adaycuestacorrea.github.io/paleo-atlas/es/estado.html) | Prueba en vivo: cada ejecución, sus tests y la frescura de cada fuente |
| CV y resumen de pruebas | Fuera del repo (privados) | Candidaturas |
| Perfil de GitHub | [`AdayCuestaCorrea/AdayCuestaCorrea`](https://github.com/AdayCuestaCorrea/AdayCuestaCorrea) | Quien abre el perfil desde el CV |

El orden importa: **primero se mide** (§17), luego se ponen al día el README y el one-pager con esas cifras, se publican en `main` y, solo entonces, el CV y los perfiles copian lo publicado.

## 5. Por qué así

- **Una sola tabla de cifras con fecha.** Cada documento copia de §17 en vez de medir por su cuenta. Así, cuando una cifra cambia, se sabe qué hay que tocar.
- **El CV solo cuenta lo publicado.** Una cifra del CV que el lector no encuentra en el README o en la web no es verificable. Por eso la entrada del CV se escribió después de pasar `fase-3` a `main`.
- **Sin vídeo** (v35). La demo es la propia web, que es pública y cambia cada día; un vídeo se quedaría viejo y es poco probable que alguien lo vea.
- **El postmortem es transversal.** Los fallos concretos ya están en cada documento de fase; el postmortem recoge los patrones que se repiten (mirar solo lo que cambia, comprobaciones demasiado literales, anclaje al etiquetar).
- **Las historias STAR salen de §20**, que proponía ocho. Se eligieron las cinco con un resultado medido: Spark frente a DuckDB, la reconciliación de nombres, el LLM que cita cada frase, medir un clasificador sin engañarse y la regla de 0 €.
- **Nada de la búsqueda de empleo en el repo.** El CV y su resumen viven fuera, y un hook `pre-push` busca una lista de términos antes de cada push.

## 6. Cómo se comprueba

Las cifras de §17 se midieron el 2026-11-08 con:

- `uv run pytest -q --collect-only` → 302 tests;
- `dbt ls --resource-type test|unit_test|model|seed` → 188 tests de datos, 8 unitarios, 66 modelos, 13 seeds; el informe de la ejecución de Actions de ese día da lo mismo (192 pasan, 4 avisos);
- consultas al almacén (`fct_taxon_text`, `dim_glossary_term`, `fct_news`, `fct_taxon_size`, `dim_taxon`, `dim_study`, `stg_narrative__fact_counts`);
- `data/runs/*.json` para las duraciones y las ejecuciones programadas, y `data/site_report.json` para las páginas.

Antes de cada commit, una búsqueda de los términos prohibidos en los archivos nuevos (además del hook).

## 7. Resultados reales (2026-11-08)

| | |
|---|---|
| Cifras de §17 puestas al día | 23 filas, 16 de ellas medidas ese día (3 nuevas: modelos dbt, fuentes y comparador) |
| Interview pack | One-pager, postmortem y 5 historias STAR, en español y en inglés |
| README | Cifras corregidas: tests (291 → 302 de pytest; 189 → 196 de dbt), duración (~4 → ~3 min), siluetas propias (190 → 187) |
| CV | Entrada de Paleo Atlas sustituida («en desarrollo», 207 tests y 53 modelos → las cifras publicadas) y tres herramientas añadidas a las habilidades |
| GitHub | README de perfil creado; bio, ubicación y web del perfil; descripción en el repo del TFM |
| LinkedIn | Proyecto en ES y EN, publicado por el usuario con los textos preparados y sus propias capturas |

## 8. Qué salió mal y qué se aprendió

- **Las cifras se quedan viejas en todas partes a la vez.** El README del día anterior ya tenía 291 tests en vez de 302, «~4 minutos» en vez de ~3 y 190 siluetas propias en vez de 187 (la v44 cambió cuáles cuentan). El CV seguía con 207 tests, 53 modelos y «en desarrollo». *Lección: medir con una orden, no copiar de la última vez, y tener un solo sitio (§17) del que copien los demás.*
- **El modo que añade al CV no actualiza.** La herramienta del CV evita duplicados: si la entrada ya existe, no hace nada. Para poner al día una entrada hubo que sustituirla a mano, con una copia del archivo antes.
- **Un falso positivo del filtro de términos.** Una palabra inglesa corriente contenía uno de los términos prohibidos. Se cambió la palabra; el filtro no se toca para un caso así.
- **El token de GitHub no podía editar el perfil.** Tenía permiso para repos, pero no `user`, que es el que hace falta para la bio. El repo del perfil se pudo crear enseguida; la bio, después de que el usuario ampliara el token (`gh auth refresh -s user`).

## 9. Preguntas de entrevista

- **¿Cómo sé que tus cifras son ciertas?** Cada una tiene fecha y una orden que la repite (§6), y muchas se ven en vivo en la página «Estado de los datos».
- **¿Qué cambiarías si empezaras de nuevo?** Está en el [postmortem](../interview-pack/postmortem.es.md): el hook de términos desde el primer commit, decidir cómo se etiqueta antes de enseñar la propuesta del modelo y convertir en tests las consultas de revisión.
- **¿Por qué tanto documento para un proyecto personal?** Porque el proyecto se hizo en pocos días y con muchas decisiones; sin ADRs ni documentos de fase, no se podría defender una semana después.
- **¿Qué parte es tuya y cuál de la IA?** Las decisiones, la revisión y la medición son mías; el código se escribió con un asistente de IA, y cada cifra se comprobó con datos.

## 10. Límites y lo que queda

- **Las cifras seguirán cambiando.** Las fichas narrativas crecen con cada lote nocturno; §17, el README y el one-pager se ponen al día al cerrar cada fase, y el CV después.
- **Las capturas del README** se rehacen con `scripts/screenshots.py` cuando cambia la web.
