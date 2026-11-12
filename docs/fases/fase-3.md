# Fase 3 — Enciclopedia, ampliación y Spark

> Alcance y casillas: [`ALCANCE.md` §7, Fase 3](../../ALCANCE.md#fase-3--enciclopedia-ampliación-y-spark). Este documento explica el porqué.
>
> **Estado (2026-11-12): cerrada.** Los ocho hitos están hechos. Los hitos 1–5, 7 y 8 se publicaron con el merge del 2026-11-07, y el hito 6 (fichas narrativas de los géneros) terminó su cola el 2026-11-12, tras ocho lotes nocturnos y un repaso final sin modelo.

## 1. En una frase

Paleo Atlas pasa de ser un registro de las especies nuevas de 2026 a una **enciclopedia de 4.751 géneros**: arcosaurios, reptiles marinos y peces fósiles. Cada ficha tiene mapa, museos, historial hacia atrás desde 1758, árbol de parentesco y, poco a poco, texto narrativo verificado. Por el camino, el mismo job se ha escrito en **Spark y en DuckDB** y se ha medido cuál conviene.

## 2. El problema

Al acabar la Fase 1, la web tenía 82 especies nuevas y unas 200 fichas básicas de taxones conocidos. Para que fuera una enciclopedia de verdad faltaban:

1. **Todos los géneros de los grupos de §4**, no solo los que salen en las noticias del año.
2. **Otros grupos además de los arcosaurios**: reptiles marinos y peces fósiles.
3. **Dónde se encontraron y dónde están los fósiles**: las ocurrencias de PBDB y los especímenes de museo de GBIF. Unir los nombres de GBIF con los de PBDB es un problema de reconciliación con casi un millón de registros, y ahí es donde se plantea Spark.
4. **La historia de cada nombre** antes de 2026, y **su lugar en el árbol de la vida**.
5. **Texto narrativo** para miles de géneros sin gastar dinero. El plan gratuito de Groq da para unas pocas especies al día, no para 2.743 géneros.

Hay una restricción que lo condiciona todo: **la Fase 1 está cumpliendo sus 2 semanas de ejecución autónoma.** Nada de esta fase puede tocar `main`, la rama `data` ni `pipeline.yml`. Todo va en `fase-3` (código) y `data-fase-3` (datos), con merge al cerrar la Fase 1. *(El merge se adelantó al 2026-11-07, por decisión del usuario, para tener la enciclopedia publicada; las 2 semanas de la Fase 1 cuentan desde entonces. `pipeline.yml` sigue sin cambios.)*

## 3. Conceptos, desde cero

**El alcance como datos (seed).** Qué grupos entran no está escrito en el código, sino en una tabla CSV que dbt carga ([`dbt/seeds/scope_clades.csv`](../../dbt/seeds/scope_clades.csv)): un clado de PBDB por fila, con su bloque, su grupo, su prioridad y si está activo. Para ampliar el alcance se edita una fila, no el código.

**Catálogo frente a consulta por nombre.** En la Fase 1, PBDB se consultaba nombre a nombre. Para una enciclopedia hace falta la lista completa, así que se pide «todos los géneros y especies aceptados bajo *Dinosauria*» (`taxon_status=accepted`). Se usa `accepted` y no `valid`, porque PBDB cuenta los sinónimos como válidos y saldría *Manospondylus* como especie de *Tyrannosaurus*.

**Reconciliación de nombres.** GBIF y PBDB no escriben igual los nombres. Se buscan tres tipos de coincidencia, en este orden:
1. **Exacta**;
2. **Sinónimo**: GBIF cambió el nombre a otro que PBDB no usa, pero el nombre original del registro sí es un género de PBDB;
3. **Errata**: una sola letra de distancia (Levenshtein ≤ 1) de un único género de PBDB, con la misma inicial y la misma familia.

Es el problema clásico de *entity resolution*.

**Spark frente a DuckDB.**
- **Spark** reparte el trabajo entre muchas máquinas (o núcleos), con un coste fijo de arranque: la JVM, la sesión y la planificación.
- **DuckDB** es una base de datos analítica que corre dentro del propio proceso, en una sola máquina, sin arranque.

La pregunta no es cuál es mejor, sino **a partir de qué volumen compensa repartir**.

**Cierre transitivo con una CTE recursiva.** PBDB solo dice quién es el padre de cada clado. Para saber todos los ancestros de un género (44 niveles en *Spinosaurus*) se usa `with recursive`: se empieza en el padre y se va subiendo hasta la raíz. El resultado es una tabla «género × ancestro × profundidad».

**Historial «seguido» frente a «reconstruido».**
- Lo **seguido** (`origin = tracked`) lo hemos visto pasar desde que arrancó el proyecto, con fecha exacta.
- Lo **reconstruido** (`origin = backfill`) se deduce después, de fuentes que solo dan el año.

Las dos cosas van en la misma tabla de eventos, pero no se tratan igual.

**LLM local por lotes.** Un modelo de 9.000 millones de parámetros (Qwen 3.5 9B) corre en la GPU de casa con Ollama. Es gratis, pero tarda unos 2 minutos por género, así que trabaja de noche, con hora de parada, y retoma donde lo dejó.

## 4. Cómo funciona aquí

```mermaid
flowchart LR
    seed[(scope_clades)] --> cat[PBDB: catálogo por clado]
    seed --> occ[PBDB: ocurrencias]
    seed --> opi[PBDB: opiniones + referencias]
    seed --> cla[PBDB: clados]
    gbif[GBIF: descarga mensual con DOI] --> job{{job de reconciliación<br/>DuckDB o Spark}}
    cat --> job
    past[Wikipedia: páginas anuales 2009–2025] --> ev
    cat --> pages[int_taxon_pages<br/>una ficha por género]
    opi --> ev[int_backfill_events]
    cla --> lin[int_genus_lineage<br/>CTE recursiva] --> nb[fct_taxon_neighborhood]
    job --> spec[fct_specimens_by_taxon]
    pages & ev & nb & spec & occ --> web[web estática ES/EN]
    gpu[Ollama + GPU<br/>lotes nocturnos] --> txt[derived/texts] --> web
```

**Los hitos:**

| Hito | Qué | Piezas principales |
|---|---|---|
| H1 | Catálogo de PBDB y una ficha por género (3.040 arcosaurios) | `scope_clades`, `ingest_catalog`, `int_catalog_genera`, `int_taxon_pages` |
| H2 | Índices por grupo, época y país; ocurrencias; artículo de Wikipedia **verificado** con Wikidata; siluetas | `int_genus_wikipedia`, `paleo/site/indices.py` |
| H3 | Reptiles marinos (358 géneros) y peces fósiles (1.353) | `paleo/scope.py` (la regla de alcance en un solo sitio), seed `featured_fishes` |
| H4 | Historial hacia atrás: opiniones de PBDB y páginas anuales 2009–2025 | `int_opinion_events`, `int_backfill_events`, `raw/wikipedia_past` |
| H5 | GBIF, el job en DuckDB y en Spark, el benchmark, el mapa y los museos, y el DAG mensual | `paleo/gbif_job/`, `spark/jobs/gbif_reconcile.py`, [`benchmarks/gbif/`](../../benchmarks/gbif/results.md) |
| H6 | Fichas narrativas de los géneros con artículo (2.743), con la GPU local; rescate sin modelo de las fichas que fallaban por pocas frases; comprobación de pisos, periodos y clados en el español | `paleo narrate --scope genera --until HH:MM`, `genus_chunks_for`, `paleo narrate --resalvage`, `--recheck-es`, `--es-missing` |
| H7 | Clasificación completa y parientes sobre un eje de millones de años | `int_genus_lineage`, `fct_taxon_neighborhood`, `paleo/site/taxon_page.py` (sustituye al cladograma de `tree.py`) |
| H8 | La web de una enciclopedia: portada con explorador, ficha nueva y página «Estado de los datos» | `paleo/site/explore.py`, `site/static/home.js`, `paleo/site/taxon_page.py`, `paleo/site/status.py`, `fct_source_freshness` |

**Frecuencia de cada fuente** (todo cabe en el plan gratuito):

| Fuente | Qué se baja | Cada cuánto |
|---|---|---|
| PBDB | Catálogo por clado; ocurrencias, opiniones y clados por bloque | Mensual (`RawStore.is_fresh`, 30 días) |
| GBIF | Una descarga filtrada con DOI (932.494 registros) | Mensual; se reutiliza si tiene menos de 28 días |
| Wikipedia | Páginas anuales antiguas (45) | Mensual; solo se guarda una revisión nueva |
| Wikidata | Artículo y elemento de cada género | Mensual |
| Ollama local | Hechos y textos de los géneros | Lotes nocturnos, cuando el usuario lo autoriza |

## 5. Por qué así

- **Una ficha por género, no por especie.** De la mayoría de las especies fósiles solo se sabe el nombre y un hueso. El género es la unidad que el público reconoce (*Spinosaurus*), y sus especies se listan dentro de la ficha. Las especies nuevas del año conservan su propia ficha y enlazan a la de su género.
- **El alcance se decide al parsear, en un solo sitio** (`paleo/scope.py`). Las páginas de reptiles y de peces incluyen tortugas, lagartos y miles de peces óseos que no entran en §4. Si el filtro estuviera en dbt, la ingesta habría gastado peticiones a PBDB, Crossref y Commons, y cuota de LLM, en taxones que nunca tendrán ficha. Filtrando al parsear, de 259 especies nuevas de las tres páginas solo 114 siguen adelante.
- **El artículo de Wikipedia se verifica, no se adivina.** Un título que coincide con el nombre no basta: el elemento de Wikidata de la polilla *Coloradia* llevaba por error el ID de PBDB del dinosaurio. Se exige que el elemento tenga el ID de PBDB (P842) **y** que su ascendencia (P171) pase por el clado del bloque.
- **DuckDB por defecto, Spark en el DAG mensual.** El benchmark (§7) dice que, con un millón de filas, DuckDB es 15–17 veces más rápido. Aun así, el DAG mensual de Airflow ejecuta la variante de Spark a propósito, para que el job de Spark funcione de verdad en un orquestador. Las huellas demuestran que los dos dan el mismo resultado. Cuesta 13 s al mes.
- **Una sola especificación del job** (`paleo/gbif_job/spec.py`): las reglas de reconciliación se escriben una vez y las dos implementaciones las siguen. Un test con fixture exige extractos idénticos, y con los datos reales se comparan las huellas SHA-256.
- **Lo antiguo no se mezcla con lo del año.** Las páginas anuales de 2009–2025 van a otra carpeta (`raw/wikipedia_past`, `interim/wikipedia_past`). Varios pasos leen *todas* las páginas anuales del almacén intermedio: la lista de nombres para PBDB, los DOIs para Crossref, las especies que redacta el LLM y las fichas `new` y `known`. Mezclarlas habría dado miles de especies «nuevas» para Groq. En carpeta aparte, solo alimentan eventos.
- **Un evento por cambio de estado, no por opinión.** PBDB guarda una opinión por cada autor que usó un nombre, y los autores discrepan durante décadas: *Brontosaurus* es sinónimo de *Apatosaurus* para Riggs en 1903, válido para Romer en 1966 y otra vez sinónimo en 1970. Un evento por opinión daría una línea temporal que va y viene. La regla es la **primera** vez que un nombre recibe cada estado, más la **revalidación** cuando la clasificación actual de PBDB lo vuelve a aceptar (Tschopp y colaboradores, 2015).
- **Lo reconstruido no es noticia.** Los eventos `backfill` no entran en «Última hora» ni en los resúmenes semanales; si entraran, aparecerían semanas de 2015. Sus ~7.600 estudios no se buscan en Crossref, porque serían ~100 MB más en git: salen como `unchecked`, sin distintivo, y la página «Cómo evaluamos las fuentes» lo explica.
- **Árbol de PBDB, no de Open Tree of Life** (decisión del usuario). Open Tree reconoce 631 de 1.000 géneros fósiles, pero solo ~12 % están en su árbol sintético. Si se mezclaran las dos fuentes, el vecindario de un género de Open Tree tendría muy pocos parientes. La clasificación de PBDB cubre el 100 %, y la vista avisa de que es una clasificación, no un análisis filogenético.
- **Solo el vecindario, generado al construir la web.** Dibujar 4.751 géneros no le sirve a nadie. Cada ficha enseña dos niveles: «Grupo» (el clado más bajo con al menos 3 géneros) y «Un nivel más arriba», con hasta 20 géneros, primero los más cercanos. Se genera en el build, así que los enlaces funcionan sin JavaScript.
- **Filas con fechas en vez de cladograma** (decisión del usuario, v30). El primer árbol era un SVG con las líneas del cladograma y el rango de cada género al pasar el ratón, que en el móvil no existe. Ahora es una fila por género sobre un eje de millones de años, con las fechas escritas junto a la barra y las bandas de los periodos. Se pierden las líneas; el parentesco se lee en el orden (los más cercanos primero) y en el clado nombrado.
- **Maquetas con datos reales antes de implementar.** La portada, la ficha y la página de estado se decidieron igual: 3–4 maquetas en HTML con los datos del almacén (no con texto de relleno), la elección y los retoques del usuario, y después el plan. Las maquetas viven fuera del repo. Así los problemas de verdad (una imagen recortada, una etiqueta que no cabe en el móvil) salen antes de escribir el código.
- **Una sola regla de facetas para el explorador y los índices** (`site/explore.py`). El explorador de la portada filtra por periodo, grupo y país en el navegador, y los índices de la enciclopedia son páginas estáticas. Si cada uno tuviera su regla, darían cifras distintas para «Jurásico + España»; con la misma función, dan las mismas. El explorador carga su JSON (132 KB comprimido) solo al llegar a él, y sin JavaScript los filtros enlazan a los índices.
- **El estado del pipeline, a la vista y desde el almacén.** El informe de cada ejecución (`runs/`) ya estaba en git; ahora pasa por dbt como cualquier otra fuente (`stg_pipeline__runs`), y la frescura de cada fuente se compara con su ritmo, que es un seed y no código. La página pública enseña la duración por paso, los tests (los avisos explicados en lenguaje llano), la cobertura y una bitácora de 30 días. Para un perfil de datos, la observabilidad y la calidad son justo lo que suele quedar invisible.
- **El texto de los géneros, con la GPU de casa.** Con la cuota de Groq, 2.743 géneros tardarían meses. Ollama con Qwen 3.5 9B tardaba ~137 s por género; con las fichas más ricas de la v26 (fuentes por secciones y curiosidades) pasó a ~3,4 min, unas 130 fichas por noche.
- **Rescatar en vez de regenerar.** Cada ficha guarda la versión de su prompt, y cambiar el prompt obliga a rehacer todas las fichas ya verificadas. Por eso las mejoras del español fueron en las comprobaciones (que eran demasiado literales) y en el feedback de los reintentos, no en el prompt. Una adaptación que falla por 1–3 frases se publica sin ellas (`_salvage`), y `paleo narrate --resalvage` aplica las reglas nuevas a los fallos guardados sin llamar a ningún modelo. El lote es **reanudable** (caché del LLM por contenido y salto de lo ya hecho), para **a una hora fija** y apaga el PC. Corre bajo `systemd-inhibit`, para que el PC no se suspenda a mitad, y un vigilante lo detiene si la GPU pasa de 85 °C. El wikitext de los géneros (65 MB) se queda en la caché local; cada hecho cita la revisión exacta (`oldid`), así que no hace falta versionarlo.
- **Cerrar con reglas, no con otra noche de GPU** (decisiones del usuario del 2026-11-12, con las cifras medidas antes):
  - Las **417 fichas en español rescatadas** sin la pasada de gramática **no se reescriben**. Los calcos medidos aparecen igual con o sin esa pasada («grupo padre/parental» en el 21–23 % de las fichas, «etapa X-iense» en el 22–26 %), así que reescribirlas habría costado GPU sin cambiar lo que se ve.
  - Los **54 géneros sin ficha en inglés** fallaban por poco: entre 4 y 9 frases malas de 20–38, casi todas copias de la fuente o hechos repetidos, frente a un tope de 3. Otro intento con el mismo prompt habría dado poco. El tope pasa a ser **3 frases o la quinta parte de la ficha**, y así se rescatan 32 sin modelo. Su español se escribe después con la GPU (`--es-missing`, 26 min).
  - **La calidad del español entra en la fase, en versión reducida y sin GPU.** Hay una comprobación nueva entre el inglés y el español: los pisos, la parte del periodo (Inferior/Superior) y los nombres de los clados («sauropodomorfo», no «saurópodo»). También hay sustituciones fijas para el calco más frecuente: «la etapa campaniense» pasa a «el piso campaniense», con su artículo. `paleo narrate --recheck-es` lo aplica a lo ya verificado sin llamar al modelo. «Grupo padre» y los nombres propios traducidos van al backlog: el primero no se arregla sin reformular la frase y los segundos no se pueden medir con fiabilidad.
- **Lecturas opcionales en dbt.** La rama `data` y el fixture del CI aún no tienen opiniones ni clados de PBDB, y DuckDB falla si un patrón de archivos no encuentra nada. Las macros comprueban primero con `glob()` y, si no hay archivos, devuelven una tabla vacía con los mismos tipos. El merge no rompe el pipeline diario.

## 6. Cómo se comprueba

- **Tests (a 2026-11-07: 236 de pytest; en dbt, 135 de datos, 131 en verde y 4 avisos, y 6 unitarios):**
  - Tests unitarios de dbt para las reglas con más lógica: la elección del clado más específico de un género, las opiniones que dan evento y el nivel «grupo» del vecindario.
  - Tests de datos:
    - el linaje no tiene ciclos;
    - cada género aparece en su propio vecindario;
    - un solo `event_id` por evento;
    - `origin` y `reliability_status` solo con sus valores.
- **Paridad de motores:** `tests/test_gbif_job.py` exige que DuckDB y Spark den los mismos extractos con el fixture; con los datos reales se comparan las huellas.
- **CI con el fixture:** cada cambio se prueba también en un directorio vacío, con los datos del fixture del CI (sin opiniones, clados ni páginas antiguas), para asegurar que el pipeline diario sigue en verde tras el merge.
- **Las fuentes del texto no cambian sin querer.** Un script compara el `sources_hash` guardado en cada ficha de hechos con el de sus fuentes actuales. Después de H4 y de H7 dio 0 de 280: ningún hito obligó a rehacer los textos.
- **Antes de aplicar una regla a los datos, se prueba en una copia.** `--recheck-es` se ejecutó primero sobre una copia de `derived/`, y de cada pasada se leyó una muestra de las frases que quitaba. Así salieron tres falsos positivos antes de tocar los datos: rangos como «Middle to Late Eocene», el epíteto *A. tortonica* leído como Tortoniense y el género *Pleiosaurus*, que la sustitución de «pleiosaurio» habría cambiado.
- **Lectura humana:** el primer lote de la GPU se leyó a mano en inglés y en español; de ahí salieron nuevas reglas en los prompts (§8). La web se revisa en el navegador, también con el ancho de móvil.
- **La lógica de la web, en funciones puras con tests:** las facetas del explorador (también su JavaScript, que se prueba con Node desde pytest), las piezas de la ficha (`srcset`, franja del tiempo, historial por décadas) y las de la página de estado (agrupación de pasos, calendario, frescura). Las plantillas solo pintan, y un test exige que la página en español y en inglés tengan la misma estructura.

## 7. Resultados reales (2026-11-03)

| Qué | Resultado |
|---|---|
| Fichas | 4.930: 4.751 géneros (arcosaurios, reptiles marinos y peces), 115 especies nuevas y 64 taxones conocidos |
| Web | 10.330 páginas en ES y EN, generadas en ~4 s, con 0 problemas de enlaces |
| GBIF | 932.494 especímenes; reconciliados 138.388 en 1.739 géneros (exacto 118.371, sinónimo 17.052, errata 2.965) |
| Benchmark, 932.494 filas | DuckDB **0,86 s / 459 MB** · Spark 13,71 s / 1.504 MB · código: 124 frente a 242 líneas |
| Historial | 403 eventos seguidos + 19.354 reconstruidos (1758–2025) en 4.808 fichas |
| Árbol | 4.846 de 4.930 fichas (98 %); mediana del grupo: 27 géneros |
| Primer lote de la GPU | 201 géneros en ~7,5 h (137 s por género, 72 °C de media); verificados EN 90 % y ES 72 % |
| Coste | 0 € |

**Al publicar (2026-11-07):**

| Qué | Resultado |
|---|---|
| Fichas | 4.890: 4.751 géneros, 115 especies nuevas y 24 taxones conocidos (los demás conocidos se integraron en la ficha de su género, con redirección) |
| Web | 10.254 páginas en ES y EN, 330 MB, 0 problemas de enlaces |
| Historial | 19.541 eventos y 8.195 estudios |
| Fichas narrativas | Tras tres lotes nocturnos (3, 4 y 5 nov) y el rescate: 397 verificadas en inglés y 389 en español (362 → 389 con las v32 y v33) |
| Ejecución diaria | ~45 s en GitHub Actions; GitHub lanza el cron de las 06:23 UTC entre 7 y 8,5 h tarde |

**Al cerrar (2026-11-12):**

| Qué | Resultado |
|---|---|
| Lotes de géneros | 8 noches (3–12 nov) más un repaso de 26 min por la tarde; los 2.743 géneros con artículo tienen intento. Media de la GPU: 72 °C (máximo 78 °C) |
| Fichas narrativas verificadas | EN 2.803 · ES 2.784. De géneros: **2.721 en EN y 2.703 en ES de 2.743 (99 % / 99 %)**. Por bloques (EN/ES): arcosaurios 2.089/2.074, reptiles marinos 271/270, peces 361/359; más 82/81 especies nuevas |
| Siguen en revisión | 28 en inglés (22 géneros con más de la quinta parte de sus frases mal, la ficha se queda con el texto de respaldo) y 18 en español |
| Repaso del español sin modelo | 517 fichas solo con sustituciones fijas; 173 pierden 223 frases con un piso, una parte del periodo o un clado cambiados (110 de clado, 85 de piso, 28 de periodo); quedan 0 «etapa X-iense» |
| Coste | 0 € |

## 8. Qué salió mal y qué se aprendió

- **El árbol de GBIF no tiene los clados de §4.** No se puede pedir «Archosauria» a GBIF. Se descargan todos los cordados fósiles, sin mamíferos ni tortugas, y el filtro fino lo hace la reconciliación con PBDB. *Lección:* cada fuente tiene su propia taxonomía; el filtro va donde está la verdad, no donde es más cómodo.
- **Un ID equivocado en Wikidata.** *Coloradia*, una polilla, llevaba el ID de PBDB de un dinosaurio. Con el ID solo, su artículo habría salido en la ficha equivocada. *Lección:* comprobar dos señales independientes (el ID y la ascendencia).
- **`--limit` contaba antes de saltar lo hecho.** El lote nocturno habría repetido siempre los mismos géneros ya terminados. Ahora el límite se aplica después de saltar lo hecho, y lo comprueba un test.
- **El log del lote estaba en `/tmp`**, que se borra al apagar el PC, justo cuando el lote apaga el PC. Ahora los logs van a `~/.local/state/`.
- **Las fichas de los géneros no salían en la web**: el modelo de textos solo contemplaba las especies nuevas. Lo destapó la revisión de la mañana, no un test. Ahora hay cifras de géneros verificados en «Cómo evaluamos las fuentes».
- **El modelo pequeño escribe calcos en español** («superdepredador», «la forma del cuerpo», «Hacia 1875») que las verificaciones automáticas (fidelidad, anti-copia, cita por frase) no detectan. *Lección:* lo automático garantiza que el texto es fiel a las fuentes, pero no que esté bien escrito; hace falta leer una muestra. Se corrigió con reglas nuevas en los prompts y subiendo su versión, lo que reescribe esas fichas en el lote siguiente.
- **Una respuesta JSON cortada** en la extracción de hechos dejaba el género sin ficha. Ahora se vuelve a preguntar en dos mitades.
- **Las opiniones de PBDB van y vienen** (*Brontosaurus*): la primera versión daba eventos contradictorios cada pocos años. Se cambió a «primera vez de cada estado» y se fijó con un test unitario de dbt.
- **Una ventana SQL demasiado ancha** se comía la descripción original de cada género. La partición de «una descripción por nombre» no incluía el tipo de evento, así que un estudio con más prioridad le quitaba el sitio. Lo destapó revisar *Brontosaurus* a mano.
- **El ensayo del merge destapó dos fallos que los tests no veían:**
  - **Un PDF en la columna de imágenes** de la página de 2026 hace fallar la petición a Commons de todo su lote. Con el código de `main`, eso tumba `ingest images` y, con él, la publicación del día. Ahora solo se piden imágenes y, si un lote falla, se repite archivo a archivo.
  - **`fct_taxon_neighborhood` podía agotar la memoria** (12 GiB de disco temporal). Calculaba la cercanía de todos los géneros de niveles que llegan a los 4.787. Ahora solo busca dentro del clado más bajo donde caben los 20 que se muestran. El resultado es idéntico fila a fila (152.596 filas) y tarda 0,3 s en vez de ~4 s.
  
  *Lección:* ensayar con los datos reales y en las condiciones del runner, no solo con el fixture.
- **La revisión a ojo encontró lo que los datos no dicen:**
  - **Fichas duplicadas.** Las especies «conocidas» de la Fase 1 (*T. rex*) convivían con la ficha de su género, que llegó en esta fase, y el buscador daba dos resultados. Se integraron en el género, con redirección de la URL antigua.
  - **Imágenes de la categoría de Commons** (una estatua de Papá Noel, un juguete, una gráfica) adelantaban a las del artículo, porque el orden primaba la variedad de tipos sobre la procedencia.
  
  *Lección:* una regla que parece neutral («una de cada tipo primero») cambia qué fuente gana, y solo se nota al mirar la página.
- **El escape de HTML de Jinja**: concatenar `<em>` con un valor ya escapado lo escapa también, y `Markup.replace` escapa lo que inserta. Las frases del historial se montan ahora en Python, con un test.
- **Las comprobaciones del español eran demasiado literales.** En el lote del 5 nov fallaron 56 de 214 adaptaciones, y la mayoría no por estar mal:
  - la de nombres buscaba subcadenas: exigía «Manu» en una frase que decía *manual*;
  - la de cifras solo veía dígitos, así que «siglo XIX», «los años 90» o «dos» contaban como cifras perdidas;
  - un clado escrito en español («Caenagnátidos») no contaba como el latino.
  
  Con las reglas arregladas, 43 fichas en español se rescataron sin volver a llamar al modelo (y 3 más en un piloto con la GPU). *Lección:* antes de culpar al modelo, leer los fallos uno a uno; una comprobación estricta que falla por motivos tontos esconde los fallos de verdad.
- **El registro de ejecuciones perdía pasos.** `paleo report finish` corre dentro del propio job y pregunta a la API de GitHub por sus pasos; el de la web a veces aún no constaba como terminado, y se descartaba. Lo destapó la maqueta de la página de estado, al no cuadrar las duraciones. Ahora se apunta como parcial, y lo que no se reparte por pasos se enseña como «sin desglose» en vez de esconderlo.
- **El cron de GitHub llega tarde.** Programado a las 06:23 UTC, se lanza entre 7 y 8,5 h después. No importa para una web que cambia una vez al día, pero la página de estado lo dice con las cifras de cada ejecución. *Lección:* el cron de Actions es «como mucho una vez al día», no una hora.
- **El PC se suspendió a mitad de un lote** (2026-11-08, 06:21): el lote se cortó con 227 géneros. Desde la noche siguiente corre bajo `systemd-inhibit --what=sleep:idle`, y ningún lote más se cortó.
- **El vigilante de temperatura no vigilaba.** El driver NVIDIA 620 escribe la temperatura con decimales (`53.61`) y el script solo aceptaba enteros, así que nunca habría parado el lote. Se arregló el 2026-11-10 (`${temp%%.*}`). *Lección:* una salvaguarda que nunca ha saltado hay que probarla a propósito.
- **Lo que la verificación no ve.** El español podía pasar todas las comprobaciones con un piso cambiado (*Halisaurus*: «Cenomaniense» por Santoniense) o con «saurópodo» por *sauropodomorph*, porque solo se miraban cifras y nombres científicos. Lo destapó la muestra de 3 fichas que se leía cada mañana. Medido en las 2.739 fichas, el piso cambiado es raro (4 fichas) y el clado cambiado no tanto (44). *Lección:* medir con grep antes de decidir si un fallo de la muestra es un caso o una pauta.
- **Una sustitución «segura» tocaba un nombre científico.** «pleiosaurio» → «plesiosaurio» también habría cambiado el género *Pleiosaurus*. Lo destapó la muestra de la prueba en una copia, no un test. Ahora la regla solo toca el nombre común en español, y un test lo fija.
- **La caché del navegador engaña al revisar.** Tras reconstruir la web, el navegador seguía sirviendo el CSS y el JavaScript viejos, y un arreglo parecía no funcionar. Ahora la revisión fuerza la recarga de los estáticos.

## 9. Preguntas de entrevista

**¿Por qué no usas Spark si lo tienes?**
Porque lo he medido. Con un millón de filas, DuckDB tarda 0,86 s y Spark 13,7 s, de los que unos 7,5 s son de arranque. Spark compensa cuando los datos no caben en una máquina o ya viven en un clúster: decenas o cientos de millones de filas, o un *lakehouse*. Lo tengo escrito, probado y orquestado, con paridad demostrada; elegir el motor es una decisión con datos, no de moda.

**¿Cómo reconcilias nombres entre fuentes?**
En tres pasadas, de más a menos segura: exacta, sinónimo (el nombre original del registro, antes de que GBIF lo cambiara) y errata (una sola letra, con la misma inicial y la misma familia, y solo si hay un único candidato). Cada coincidencia guarda cómo se hizo, y las coordenadas que GBIF marca como dudosas no van al mapa. Lo que no casa va a un extracto `unmatched` para revisarlo.

**¿Cómo modelas el historial?**
Con dos orígenes en una misma tabla de hechos. Lo seguido sale de un SCD tipo 2 calculado en SQL sobre las versiones crudas versionadas en git. Lo reconstruido sale de las opiniones de PBDB y de las páginas antiguas, con precisión de año. La columna `origin` decide qué es noticia y qué es historia.

**¿Cómo evitas que un cambio en una fuente dispare un gasto de LLM?**
Cada ficha guarda un hash de sus fuentes públicas y las versiones de sus prompts. Solo se rehace si cambia alguno de los dos. Antes de cerrar un hito compruebo que el hash de las 280 fichas no ha cambiado. Además, todo lo que alimenta al LLM se filtra por alcance al parsear.

**¿Por qué un LLM local y no una API?**
Por coste y por cuota: 2.743 géneros con el plan gratuito de Groq tardarían meses. Con la GPU de casa son unas 10 noches, a coste 0. Lo que exige: lotes reanudables, una hora de parada, un vigilante de temperatura y apagado automático. Las mismas verificaciones de fidelidad sirven para los dos proveedores.

**¿Cómo sabes que el pipeline va bien?**
Hay una página pública que lo cuenta: la duración por paso de cada ejecución, los tests de dbt (los de datos aparte de los unitarios, y cada aviso explicado con su cifra real), la frescura de cada fuente frente a su ritmo y una bitácora de 30 días. Sale del propio registro de ejecuciones, que pasa por dbt como cualquier otra fuente, así que la misma página que lo enseña también está probada. Un error de dbt detiene la publicación; un aviso se publica y se ve.

**¿Cómo calculas los ancestros de 4.751 géneros?**
Con una CTE recursiva sobre los enlaces padre-hijo de PBDB: unas 4.750 × 40 filas en milisegundos con DuckDB. Un test de datos comprueba que ninguna cadena llega al límite de recursión, lo que delataría un ciclo.

## 10. Límites y lo que queda

- **22 géneros sin ficha en inglés** (más de la quinta parte de sus frases fallan) y 18 fichas en español en revisión: se quedan con el texto de respaldo hasta que cambien sus hechos o el prompt.
- **Calcos del español que no se arreglan con reglas:** «grupo padre/parental» (593 fichas) y nombres propios traducidos («El ermitaño Cowles Case»), en el backlog. Las 417 fichas rescatadas sin la pasada de gramática se quedan así (decisión del usuario).
- **Unos 2.000 géneros sin artículo en Wikipedia** se quedan con el texto de respaldo (§11.4): no hay fuente suficiente para una ficha narrativa.
- **Databricks Free Edition** (opcional): el mismo job de Spark en un entorno gestionado.
- **El benchmark con 5 y 10 veces el volumen** quedó descartado: confirmaría lo que ya se sabe. Spark se lucirá mejor en un proyecto aparte, con un volumen que lo justifique.
- **Estudios antiguos sin comprobar:** cruzarlos cada mes con Retraction Watch, sin guardar un registro por DOI (backlog).
- **Open Tree of Life** podría volver como señal («este género está en el árbol sintético, con N estudios»), no como topología (backlog).
- **Merge** de `fase-3` y `data-fase-3` a `main` y `data`: hecho el 2026-11-07, adelantado por decisión del usuario (antes de que la Fase 1 cumpliera sus 2 semanas autónomas, que cuentan desde entonces), con la lista de abajo.

### Lista de comprobación del merge (ensayada el 2026-11-03)

El ensayo se hizo en clones desechables, sin push. Se ejecutaron los pasos de `pipeline.yml` sobre `main` + `fase-3` y `data` + `data-fase-3`, y después se simuló un commit diario de Actions en `data` antes del merge.

1. **Código:** `git checkout main && git merge fase-3`. Hoy es avance rápido, porque `main` no ha cambiado desde que salió `fase-3`.
2. **Datos:** en el checkout de `data`, `git merge origin/data-fase-3`. Si Actions ya ha hecho commits diarios, habrá conflictos previsibles. `uv run python ../scripts/merge_data.py` los resuelve:
   - en los `_checked.json`, conserva todas las claves con su fecha más reciente;
   - en los archivos añadidos el mismo día en las dos ramas, que solo se diferencian en `fetched_at`, se queda con uno;
   - en `runs/`, hace la unión de las ejecuciones.
   
   En el ensayo resolvió 9 de 9 conflictos. Lo que no sepa resolver lo deja para revisarlo a mano.
3. **`pipeline.yml` y `ci.yml` no necesitan cambios:** las ingestas nuevas van dentro de los comandos de siempre. `paleo parse wikipedia` también parsea las páginas antiguas, en ~12 s.
4. **Primera ejecución tras el merge** (manual): todo en verde. Tiempos: ingesta ~1,5 min, parseo 12 s, dbt 9 s, web 9 s y su comprobación 55 s. La web pesa 337 MB y tiene 10.342 archivos, lejos del límite de 1 GB de GitHub Pages; la sección «Parientes» es ~60 % de cada ficha. dbt necesita entre 3 y 4 GB de RAM, y el runner tiene 16.
5. **Al día siguiente, el paso de Groq** reescribe las 82 especies nuevas, porque los prompts subieron de versión (unos 2 días de cuota gratuita). Mientras tanto se publican las versiones anteriores, que siguen verificadas.
6. **Mantener las ramas al día mientras tanto:** cada vez que `main` o `data` reciban algo (un hotfix, los commits diarios de Actions), se fusionan en `fase-3` y `data-fase-3` (con `merge_data.py` para los datos). Así el merge final sigue siendo un avance rápido. El 2026-11-03 se hizo así tras el hotfix de Commons en `main` (`d9781bc2`) y el commit de datos de esa ejecución: los dos merges resolvieron sus conflictos (1 en el código y 9 en los datos) y quedaron en verde.
7. **Qué vigilar:** que no haya avisos `Commons batch … failed` repetidos a diario, que la duración de dbt no suba y que la rama `data` (~180 MB de crudo, 29 MB comprimidos en git) crezca solo con las descargas mensuales.
