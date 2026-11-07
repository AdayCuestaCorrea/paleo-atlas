[English](one-pager.md) · **Español**

# Paleo Atlas — resumen en una página

**Una enciclopedia de paleontología en español e inglés que se reconstruye sola cada día a partir de datos científicos abiertos, con coste cero.**
Web: https://adaycuestacorrea.github.io/paleo-atlas/ · Código: https://github.com/AdayCuestaCorrea/paleo-atlas

## El producto

- **4.890 fichas** de arcosaurios (dinosaurios, aves, pterosaurios, cocodrilos), reptiles marinos y peces fósiles, en dos idiomas: más de 10.000 páginas.
- **Al día:** cada día consulta sus fuentes, cada una a su ritmo (Wikipedia a diario; la Paleobiology Database, Crossref, Commons y PhyloPic cada semana o cada mes; GBIF cada mes). Si algo cambió, reconstruye el almacén y vuelve a publicar.
- **Con historia:** 19.541 eventos (descripciones, sinonimias, cambios de género…) desde 1758 y 8.195 estudios; los seguidos desde 2026 llevan sus señales de fiabilidad (revisión por pares, preprint, retracción).
- **Textos que citan cada frase:** un LLM redacta a partir de hechos extraídos con su fuente, y solo se publica lo que pasa las comprobaciones automáticas.
- **Transparente:** una página pública, [«Estado de los datos»](https://adaycuestacorrea.github.io/paleo-atlas/es/estado.html), muestra cada ejecución, los tests y la frescura de cada fuente.

## La arquitectura

```
fuentes abiertas → paleo ingest → crudo versionado en git → dbt + DuckDB → web estática (Jinja2) → GitHub Pages
                                                       ↑ LLM: hechos → texto EN → ES + comprobaciones
                                     GBIF (mensual) → reconciliación de nombres en DuckDB y en PySpark
```

- **El estado vive en git**: cada respuesta de una fuente se guarda como JSON versionado, y el almacén se reconstruye entero en cada ejecución. Cualquier día se puede reproducir, y el historial (SCD tipo 2) sale en SQL de esas versiones.
- **Comandos, no código del orquestador**: GitHub Actions ejecuta a diario los mismos comandos `paleo` que los DAGs de Airflow 3.3, y se ha comprobado que dan el mismo resultado.
- **Spark solo donde se ha medido**: la reconciliación de 932.494 especímenes de GBIF está escrita en DuckDB y en PySpark, con la misma salida. DuckDB es 15–17 veces más rápido a este volumen, así que la capa diaria se queda en DuckDB.

**Stack:** Python 3.14 · dbt · DuckDB · PySpark · Airflow · GitHub Actions · Ollama (Qwen 3.5 9B, GPU local) · Groq · Jinja2 · JavaScript sin frameworks · pytest.

## Las cifras (medidas el 2026-11-07)

| | |
|---|---|
| Tests | 249 de pytest · 157 de dbt en cada ejecución (150 de datos y 7 unitarios) |
| Reconciliación GBIF ↔ PBDB | 138.388 especímenes con su género: exacta, por sinónimo o por errata |
| Benchmark, 932.494 filas | DuckDB 0,86 s y 459 MB · Spark 13,7 s y 1,5 GB |
| Fichas narrativas verificadas | 397 en inglés y 362 en español (crecen cada noche con la GPU local) |
| Coste mensual | 0 € |

## Cómo se evalúa la calidad

- **Datos:** tests de dbt en cada ejecución (claves, relaciones, valores aceptados, frescura, reglas de alcance). Un error detiene la publicación; un aviso se publica y se explica en la página de estado.
- **Textos del LLM:** cada frase debe citar un hecho, conservar sus cifras y nombres científicos y no copiar 8 palabras seguidas de la fuente. Las configuraciones de modelo se compararon con 12 fichas de referencia antes de elegir.
- **Web:** en cada build se comprueban enlaces rotos, la paridad ES/EN y las licencias de cada imagen.
- **Decisiones:** 10 ADRs con contexto, alternativas y consecuencias, y un documento por fase con lo que salió mal y lo aprendido.
