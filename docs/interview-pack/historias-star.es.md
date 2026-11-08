[English](star-stories.md) · **Español**

# Paleo Atlas — historias STAR

Cinco historias para entrevista, con cifras medidas. Cada una se puede contar en unos 2 minutos; los enlaces llevan a la prueba en el repo.

## 1. Spark solo donde se ha medido

- **Situación:** la capa diaria del pipeline usa DuckDB. La descarga de GBIF trae 932.494 especímenes fósiles cuyos nombres hay que reconciliar con 4.787 géneros de PBDB, y es justo el tipo de trabajo que se suele dar a Spark.
- **Tarea:** decidir con datos si Spark merecía entrar en el pipeline, en vez de meterlo porque aparece en las ofertas.
- **Acción:** escribí una especificación única del job (exacto → sinónimo → errata, y agregados por género, institución y país) y dos implementaciones, en SQL de DuckDB y en PySpark. Comprobé que los cuatro extractos eran idénticos fila a fila (mismas huellas SHA-256) y medí tres tamaños, tres repeticiones cada uno en un proceso nuevo, con el pico de memoria de todo el árbol de procesos, JVM incluida.
- **Resultado:** con las 932.494 filas, DuckDB tarda 0,86 s y usa 459 MB; Spark, 13,7 s y 1,5 GB (15–17 veces más lento, 3–6 veces más memoria) y necesita 242 líneas de código frente a 124. La capa diaria se queda en DuckDB, y Spark corre una vez al mes en el DAG de Airflow (14 s en Docker). Está en [`benchmarks/gbif/results.md`](../../benchmarks/gbif/results.md) y en los ADR D1 y D5, que dicen también cuándo cambiaría: si una fuente diaria no cupiera en la memoria de un runner (del orden de decenas de millones de filas). De los 13,7 s de Spark, ~7,5 s son arranque fijo.

## 2. Reconciliar nombres entre dos bases de datos que no se ponen de acuerdo

- **Situación:** GBIF y PBDB no comparten taxonomía. El árbol de GBIF ni siquiera tiene los clados del alcance (no se puede pedir «Archosauria»), y los especímenes llegan con sinónimos, combinaciones antiguas y erratas.
- **Tarea:** llevar cada espécimen a su género de la enciclopedia sin que entren mamíferos, tortugas o animales mal identificados.
- **Acción:** pedí a GBIF todos los cordados fósiles sin mamíferos ni tortugas y dejé el filtro fino a la reconciliación con PBDB, que es donde está la verdad del alcance. Tres pasos en orden: nombre exacto, sinónimo según PBDB y errata a una sola edición de un único género (Levenshtein ≤ 1). Las coordenadas que GBIF marca como erróneas no van al mapa. Para los artículos de Wikipedia de cada género apliqué la misma idea, con dos señales independientes: el ID de PBDB en Wikidata y su ascendencia hasta la raíz del bloque.
- **Resultado:** 138.388 especímenes reconciliados con 1.739 géneros (118.371 exactos, 17.052 por sinónimo y 2.965 por errata), de 78 instituciones, con el DOI de la descarga citado en la web. La doble señal evitó un error real: el elemento de Wikidata de *Coloradia*, una polilla, llevaba el ID de PBDB de un dinosaurio.

## 3. Un LLM que cita cada frase, y comprobaciones que no se pasan de estrictas

- **Situación:** la web publica textos escritos por un LLM sobre ciencia, en dos idiomas, sin nadie que los revise uno a uno, y con la regla de 0 €: un modelo pequeño en la GPU local y el plan gratuito de Groq.
- **Tarea:** que ningún texto publicado diga algo que no esté en sus fuentes.
- **Acción:** separé el trabajo en pasos comprobables: extraer hechos con su fuente, redactar en inglés citando un hecho por frase y adaptar al español frase a frase. Cada frase pasa comprobaciones de cifras, nombres científicos, anti-copia (8 palabras seguidas) y cita; si una ficha falla, la web enseña un texto montado con sus datos. Elegí la configuración con 12 fichas de referencia. Cuando un lote dio 56 fallos de 214 en español, los leí uno a uno: la mayoría eran reglas tontas («Manu» dentro de *manual*, «siglo XIX» como cifra perdida, un clado escrito en español).
- **Resultado:** 598 fichas verificadas en inglés y 582 en español; el 82 % de los 43.764 hechos extraídos pasa la comprobación. Arreglar las reglas rescató 43 fichas en español sin volver a llamar al modelo. Y una lección que cuento: lo automático garantiza la fidelidad, no el estilo; los calcos del español solo salieron leyendo una muestra.

## 4. Medir un clasificador sin engañarse

- **Situación:** las noticias de tres medios con licencia se clasifican con un LLM en cuatro clases y se agrupan cuando dos medios, o dos idiomas, cuentan lo mismo.
- **Tarea:** publicar métricas honestas de las dos cosas.
- **Acción:** se etiquetaron 300 titulares a mano con una herramienta propia, y 294 coincidían con la propuesta del LLM. En vez de publicar un 98 %, lo traté como lo que era, una cota superior por anclaje, e hice una muestra a ciegas de 50 sin la propuesta, repitiendo también las etiquetas humanas. Para la deduplicación comparé un baseline de TF-IDF (umbral por validación cruzada) con un LLM como juez de cada par candidato, sobre 47 pares etiquetados.
- **Resultado:** a ciegas, el LLM coincide con la persona en el 74 %, y la persona consigo misma en el 84 %: ese es el techo de la tarea. Las dos clases que más se confundían eran también las que la persona cambiaba, así que se fusionaron y subió el acuerdo de los dos. En la deduplicación, el juez llegó a F1 1,00 frente a 0,29 del TF-IDF, con 4 llamadas. Las dos cifras se publican en el README con su significado.

## 5. Un pipeline diario que no cuesta nada

- **Situación:** proyecto personal, sin presupuesto: nada que pueda generar una factura.
- **Tarea:** un pipeline diario y fiable, con LLM, sin servicios de pago.
- **Acción:** el estado vive en git (cada respuesta cruda versionada en una rama `data`), el almacén es un DuckDB que se reconstruye desde cero en cada ejecución de GitHub Actions y la web es estática en GitHub Pages. Para el LLM, caché por contenido (una llamada repetida no gasta cuota), limitador de cuota, lotes reanudables y el volumen en la GPU local, con un vigilante de temperatura. Cada fuente va a su ritmo (Wikipedia a diario; PBDB, Commons o GBIF cada semana o cada mes) y antes de todo, una petición ligera por página anual (solo el ID de la última revisión) dice si hay algo nuevo, para no gastar peticiones ni cuota del LLM sin necesidad. Una página pública de estado enseña cada ejecución, sus tests y la frescura de cada fuente.
- **Resultado:** 0 € al mes. Una ejecución completa tarda ~3 minutos en Actions, con 196 tests de dbt: un error para la publicación y un aviso se publica explicado en la página de estado. Las 5 ejecuciones programadas del 4 al 8 de noviembre salieron en verde. Y la limitación queda escrita: el cron gratuito de GitHub se lanza entre 7 y 8,5 h tarde, lo que basta para una web que cambia una vez al día.
