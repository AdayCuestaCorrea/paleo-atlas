**Español (canónico)** · [English](SCOPE.md)

# ALCANCE — Paleo Atlas

> **Fuente de verdad del proyecto.** Si algo no está aquí, no está en el alcance.
> Cualquier cambio de alcance se apunta en el [Registro de cambios](#25-registro-de-cambios) con fecha y motivo.
> Las ideas nuevas van primero al [Backlog](#24-backlog-de-ideas); solo entran en el alcance cuando se mueven con una entrada en el registro.
> Las casillas `[ ]` se marcan `[x]` al terminar.

**Creado:** 2026-10-31 · **Versión:** 20 · **Estado:** Fase 1 esperando sus 2 semanas autónomas (y ver lanzarse el cron); Fase 2 (Airflow) hecha; Fase 3 en curso en la rama `fase-3` (merge a `main` al cerrar la Fase 1)

---

## Índice

1. [Visión](#1-visión)
2. [Objetivo profesional y trazabilidad con ofertas](#2-objetivo-profesional-y-trazabilidad-con-ofertas)
3. [Dentro y fuera del alcance](#3-dentro-y-fuera-del-alcance)
4. [Alcance taxonómico](#4-alcance-taxonómico)
5. [Fuentes de datos](#5-fuentes-de-datos)
6. [Arquitectura](#6-arquitectura)
7. [Fases y entregables](#7-fases-y-entregables)
8. [Modelo de datos (dbt)](#8-modelo-de-datos-dbt)
9. [Historial de cambios por taxón](#9-historial-de-cambios-por-taxón)
10. [Verificación de estudios](#10-verificación-de-estudios)
11. [La web: idiomas, páginas y ficha](#11-la-web-idiomas-páginas-y-ficha)
12. [IA: fichas narrativas y glosario](#12-ia-fichas-narrativas-y-glosario)
13. [Modelos 3D](#13-modelos-3d)
14. [Contrato de comandos del pipeline](#14-contrato-de-comandos-del-pipeline)
15. [Orquestación y frescura](#15-orquestación-y-frescura)
16. [Calidad de datos y observabilidad](#16-calidad-de-datos-y-observabilidad)
17. [Métricas del proyecto (para CV y entrevistas)](#17-métricas-del-proyecto-para-cv-y-entrevistas)
18. [Costes: 0 €](#18-costes-0-)
19. [Licencias, atribución y ética](#19-licencias-atribución-y-ética)
20. [Documentación y material de portfolio](#20-documentación-y-material-de-portfolio)
21. [Riesgos y mitigaciones](#21-riesgos-y-mitigaciones)
22. [Decisiones](#22-decisiones)
23. [Calendario](#23-calendario)
24. [Backlog de ideas](#24-backlog-de-ideas)
25. [Registro de cambios](#25-registro-de-cambios)
26. [Estructura del repositorio](#26-estructura-del-repositorio)

---

## 1. Visión

Una **enciclopedia paleontológica visual y viva, en español e inglés**, que se actualiza sola:

- **Última hora:** lo publicado hoy aparece en la web en horas (ver §15).
- **Recap semanal:** resumen de todo lo que pasó en la semana, archivado.
- **Enciclopedia:** una ficha por taxón con imagen 2D (y 3D si existe un modelo fiable), datos clave, **historial de todo lo que se ha descubierto o cambiado sobre él**, mapa de hallazgos y museos que guardan especímenes.
- **Parentesco visual:** familia y clasificación de cada animal, y un **árbol de parentesco** con sus «hermanos», ordenados en el tiempo geológico.
- **Comparador de tamaños:** *T. rex* frente a *Ankylosaurus*, un elefante o un avión, a escala.
- **Para todos los públicos:** glosario y explicaciones para quien no sabe qué es un holotipo o el Cretácico.
- **Con rigor visible:** cada estudio muestra señales de fiabilidad (revisado por pares, preprint, retractado…).

Público:
- **Lectores:** aficionados a la paleontología, en español o inglés.
- **Reclutadores y entrevistadores técnicos** (Data Engineer / Data Scientist / AI Engineer): el proyecto es, ante todo, una pieza de portfolio.

**Principio rector:** cada herramienta tiene que estar justificada por el problema, no por el CV. Si una decisión no se defiende en una entrevista técnica, no entra.

---

## 2. Objetivo profesional y trazabilidad con ofertas

Demostrar, con un sistema que funciona en público, las habilidades que piden las ofertas de Data Engineer / Data Scientist evaluadas en mi búsqueda de empleo (19 ofertas a 2026-10-31; el detalle por empresa se queda en privado).

| Habilidad | Ofertas donde aparece (de 19) | Imprescindible en | Componente que la demuestra |
|---|---|---|---|
| Spark / PySpark | 4 | 2 | Job de GBIF en PySpark local + benchmark contra DuckDB (Fase 3) |
| Databricks | 3 | — | *Opcional:* mismo job en Databricks Free Edition (Fase 3) |
| Airflow | 3 | 1 | DAGs en Docker que llaman a los mismos comandos (Fase 2) |
| dbt | 2 | — | dbt-duckdb: staging → intermediate → marts, **historial SCD2 calculado desde las versiones crudas**, tests de datos y tests unitarios de dbt (Fase 1) |
| CI/CD | 4 | — | GitHub Actions: tests en cada push + ejecución programada (Fase 1) |
| Calidad de datos | transversal | — | Tests dbt + pytest + informe de ejecución (Fase 1) |
| LLM / IA generativa | perfil AI Engineer | — | Fichas narrativas: extracción de hechos con fuente → redacción → verificación de fidelidad y anti-copia (Fases 1 y 3); glosario (Fase 5) |
| NLP / ML | perfil DS | — | Clasificación y deduplicación de noticias con evaluación (Fase 5) |

**No cubre (a propósito):**
- **AWS:** descartado por la regla de 0 € (§18). Es un hueco real (lo pide alguna oferta); si hace falta, se cubre aparte.
- Power BI, Kubernetes, MLflow, Kafka: no tienen sentido en este problema.

**Nota de honestidad sobre Spark:** la API de descargas de GBIF filtra en el servidor, así que el volumen que llega es manejable con DuckDB. Spark se usa en modo local y se **mide** contra DuckDB sobre el mismo trabajo. Si gana DuckDB, se documenta así. Lo que se enseña en una entrevista es la comparación con cifras, no «usé Spark».

---

## 3. Dentro y fuera del alcance

### Dentro
- Los grupos de §4, por fases.
- Web **bilingüe** (español e inglés) con selector de idioma.
- Detección diaria de novedades + recap semanal.
- Historial de cambios por taxón.
- **Fichas básicas para los taxones ya conocidos** que aparecen en los estudios del año (datos de PBDB, imagen e historial de estudios; texto narrativo en la Fase 3). Decisión del 2026-11-02.
- Señales de fiabilidad de cada estudio.
- Enciclopedia con datos de PBDB y GBIF; Spark local + benchmark.
- Imágenes 2D con licencia libre; modelos 3D curados cuando existan y sean fiables.
- Familia y clasificación en cada ficha; árbol de parentesco con escala temporal (Fase 3).
- Comparador de tamaños con objetos y animales actuales, solo con tamaños que tengan fuente (Fase 6).
- **Fichas narrativas propias** en ES + EN, cada frase con su cita (§12.1): especies nuevas en la Fase 1, toda la enciclopedia en la Fase 3.
- IA: glosario y clasificación de noticias (Fase 5).
- Airflow en Docker; GitHub Actions para la ejecución programada.
- README bilingüe, ADRs, interview pack.

### Fuera (no se hace salvo cambio registrado)
- Cualquier servicio con coste (AWS, bases de datos alojadas de pago, APIs de pago).
- Grupos no listados en §4 (van al backlog).
- App móvil, cuentas de usuario, comentarios.
- Chat o explicador conversacional (descartado el 2026-11-01: el glosario cubre esa necesidad).
- Tiempo real al minuto (necesita un servidor siempre encendido; ver backlog).
- Spark en la capa diaria/semanal.
- Scraping de webs de noticias; imágenes de prensa.
- Imágenes o modelos 3D con licencia no comercial (NC) o sin licencia clara (§19).
- Copiar o adaptar prosa de Wikipedia o de artículos: solo se extraen hechos (§12.1, §19).
- Afirmar en CV o entrevistas nada que el proyecto no haga de verdad.

---

## 4. Alcance taxonómico

El alcance se define en un fichero de datos (`dbt/seeds/scope_clades.csv`, *hecho*), no en el código: una fila por clado de PBDB con su bloque, su grupo, su prioridad (gana el clado más específico) y si está activo. Lo leen dbt y `paleo ingest pbdb`. **Ampliar = añadir o activar filas del seed + entrada en el registro de cambios.** Las aves necesitan dos filas porque PBDB separa Aves (*Confuciusornis*…) de Avialae (*Archaeopteryx*, *Hesperornis*…). La enciclopedia tiene **una ficha por género** (decisión del usuario, 2026-11-02), con sus especies aceptadas dentro; los géneros con especies vivas y los icnotaxones (huellas, huevos) no entran.

| Bloque | Grupos | Ejemplos famosos | Página de Wikipedia anual (verificar nombre exacto) | Fase |
|---|---|---|---|---|
| Arcosaurios | Dinosauria (incl. aves fósiles), Pterosauria, Crocodylomorpha y afines | *Spinosaurus*, *T. rex*, *Quetzalcoatlus*, *Sarcosuchus* | «AAAA in archosaur paleontology» | 1 |
| Reptiles marinos | Ichthyosauromorpha, Sauropterygia (plesiosaurios, pliosaurios, notosaurios, placodontos), Mosasauridae | *Mosasaurus*, *Liopleurodon*, *Ophthalmosaurus* | «AAAA in reptile paleontology» | 3 |
| Peces fósiles | Placodermi, Chondrichthyes fósiles (tiburones), otros peces fósiles destacados | *Dunkleosteus* (placodermo, **pez, no reptil**), *Otodus megalodon* | «AAAA in paleoichthyology» | 3 |

Notas:
- Los mosasaurios son escamosos (parientes de lagartos y serpientes), no arcosaurios. Por eso van en «reptiles marinos» y no en el bloque 1.
- **Peces destacados** (seed `featured_fishes.csv`, editable, con el motivo de cada uno): 29 géneros famosos fuera de Placodermi y Chondrichthyes, como *Leedsichthys*, *Xiphactinus*, *Tiktaalik*, *Coelacanthus*, *Arandaspis* o *Saurichthys*. De las páginas anuales de reptiles y peces solo entran ictiosaurios, sauropterigios, mosasaurios (entre los escamosos, si el texto los nombra), placodermos, condrictios y los géneros destacados; tortugas, lagartos y la mayoría de peces óseos quedan fuera.
- Los homónimos entre bloques (*Paracorax*: cormorán fósil y tiburón) tienen una sola ficha, la del bloque anterior; un test de dbt los avisa.
- Fuera por ahora (backlog): sinápsidos y mamíferos fósiles (*Dimetrodon*, mamut), invertebrados (trilobites, ammonites), plantas.

---

## 5. Fuentes de datos

> Antes de usar cada fuente: comprobar licencia y condiciones de uso actuales y apuntarlo aquí (columna «Verificado»).

| # | Fuente | Qué aporta | Acceso | Frecuencia | Licencia (a verificar) | Verificado |
|---|---|---|---|---|---|---|
| F1 | Wikipedia — páginas anuales de §4 (año en curso + años anteriores para histórico) | Taxones nuevos: nombre, estatus, autores, edad, unidad geológica, localidad, referencia | API de MediaWiki; nunca scraping del HTML | Diaria (detección de cambios) | Texto CC BY-SA 4.0 (+ GFDL): se usan los hechos, no se copia el texto | [x] 2026-11-01 |
| F2 | PBDB — API `data1.2` | Taxonomía, sinonimias, **opiniones taxonómicas con año y referencia** (historial), rango temporal, ocurrencias | API REST | Semanal por nombre (caché de 7 días; los nombres nuevos, al momento); catálogo de la enciclopedia mensual, una descarga por clado del seed `scope_clades` | CC BY 4.0 (citar PBDB) | [x] 2026-11-01 |
| F3 | GBIF — API de descargas (filtro en servidor) | Especímenes fósiles (`basisOfRecord = FOSSIL_SPECIMEN`) de los grupos de §4: coordenadas, institución, país | API pública gratuita (cuenta de GBIF) | Mensual | Cada descarga tiene DOI y hay que citarla; licencias por registro (CC0, CC BY, CC BY-NC) | [x] 2026-11-02 |
| F4 | PhyloPic — API v2 | Siluetas por taxón (si no hay, se usa la del género o el clado) | API REST | Semanal (todas las búsquedas; respeta la caché de 7 días) | Por imagen. Lista blanca común con F5 (`license_allowlist`): dominio público, CC0, CC BY y CC BY-SA 2.0–4.0; **nunca NC ni ND** | [x] 2026-11-01 |
| F5 | Wikimedia Commons — API | Reconstrucciones y fotos de fósiles | API de MediaWiki | Semanal (caché de 7 días) | Por archivo; Commons no admite licencias solo NC ni ND | [x] 2026-11-01 |
| F6 | Crossref — API REST | Metadatos de cada estudio: tipo (artículo / preprint), revista, ISSN, **retracciones y correcciones** | API pública | Por cada estudio nuevo + revisión mensual | Metadatos de uso libre; los resúmenes (abstracts) pueden tener derechos | [x] 2026-11-01 |
| F7 | ZooBank | Registro oficial del nombre (obligatorio en publicaciones electrónicas según el ICZN) | API / búsqueda pública | Por cada taxón nuevo | **API no disponible** (404 en todas las rutas el 2026-11-02; también informado el 28-08-2026). Se reintenta en la Fase 3; mientras, no se muestra el distintivo | [ ] |
| F8 | DOAJ | Si la revista de acceso abierto está en el directorio | API pública (sin clave), por ISSN | Mensual (caché de 30 días) | Metadatos de revistas **CC0** | [x] 2026-11-02 |
| F13 | Wikidata — SPARQL | Verificación de los artículos de Wikipedia de cada género (ID de PBDB P842 y ascendencia P171 hasta la raíz del bloque) y título del artículo en español | Servicio de consultas público, 100 elementos por consulta | Mensual, escalonado (como mucho 600 géneros por ejecución) | Datos **CC0** | [x] 2026-11-02 |
| F9 | *(Fase 5)* RSS de medios ES/EN | Noticias: titular, enlace, fecha | RSS | Diaria | Solo titular + enlace + resumen propio | [ ] |
| F10 | *(Fase 6)* Fuentes de modelos 3D (§13): Smithsonian 3D, MorphoSource, Sketchfab, colecciones de museos | Modelos 3D | API o embebido oficial | Curación manual | Por modelo; mismas licencias permitidas que F4 | [ ] |
| F11 | *(Fase 3)* Open Tree of Life — API | Árbol de parentesco sintético (topología), con identificadores cruzados a otras bases | API pública | — | — | Descartada por ahora (2026-11-03): reconoce 631 de 1.000 géneros fósiles, pero solo ~12 % están en su árbol sintético |
| F12 | *(Fase 6)* Conjuntos de datos de tamaño corporal publicados (p. ej. en Dryad) + seed curado a mano | Longitud y masa estimadas, con rango y cita | Descarga + curación | Puntual | Dryad publica en CC0; resto, a verificar por conjunto | [ ] |

### Resultado de la comprobación de licencias (2026-11-01)

| Fuente | Qué dice | Qué hacemos |
|---|---|---|
| **F1 Wikipedia** | Texto bajo CC BY-SA 4.0 (y GFDL). Reutilizar o modificar el texto obliga a atribuir, a indicar los cambios y a publicar con la misma licencia. Las imágenes tienen su propia licencia, archivo por archivo | Solo extraemos hechos (§12.1); el test anti-copia lo garantiza. Citamos el artículo como fuente en la ficha. No usamos imágenes de Wikipedia salvo a través de Commons (F5) |
| **F2 PBDB** | Toda la base de datos bajo **CC BY 4.0** desde 2013; solo exige atribución | Atribución a PBDB en cada ficha y en «Fuentes y licencias». Mientras no encontremos la fórmula de cita oficial de su web, usamos la cita general del proyecto |
| **F4 PhyloPic** | Cuatro grupos de licencias: dominio público (PDM, CC0), atribución (CC BY 3.0/4.0), CompartirIgual (CC BY-SA 3.0) y **no comercial (CC BY-NC 3.0, CC BY-NC-SA 3.0)**, que aún llevan algunas imágenes antiguas. Con CC BY hay que citar al autor con el texto de la página de la imagen y enlazar la licencia | Lista blanca de licencias: PDM, CC0, CC BY 3.0/4.0, CC BY-SA 3.0. **Las NC se descartan** (§19). Comprobar en la Fase 1 qué campos de licencia y autor devuelve la API v2 |
| **F5 Wikimedia Commons** | Licencia por archivo. Commons **no acepta** archivos solo con licencia NC ni con ND. La API (`prop=imageinfo&iiprop=extmetadata`) devuelve `LicenseShortName`, `LicenseUrl`, `Artist`, `Credit`, `AttributionRequired`, `UsageTerms` | Lista blanca por `LicenseShortName` (el campo más fiable). Archivos con varias licencias: revisión manual, porque la API avisa de que esos valores no son fiables |
| **F3 GBIF** | Cada descarga tiene un DOI que **hay que citar** («GBIF.org (fecha) GBIF Occurrence Download https://doi.org/…»). Cada registro conserva la licencia de su conjunto de datos: CC0, CC BY 4.0 o CC BY-NC 4.0; la descarga entera toma la más restrictiva (CC BY-NC 4.0). La API de descargas exige una cuenta gratuita | Se publican solo **agregados** (recuentos por género, institución y país, y zonas de 0,5°), nunca registros sueltos, y se cita el DOI en cada ficha con datos de GBIF y en «Fuentes y licencias». La descarga cruda se queda en la caché local (A11). Credenciales solo en `.env`, nunca en el crudo ni en los logs |
| **F6 Crossref** | «Casi ningún metadato tiene derechos de autor; se puede usar para cualquier fin». Los resúmenes (abstracts) sí pueden tenerlos. Las retracciones y correcciones de un estudio salen en su campo `updated-by` (el aviso de retracción lleva `update-to` apuntando al original), con `source` = `publisher` o `retraction-watch` | Usamos los metadatos libremente. De los abstracts solo extraemos hechos, nunca se publican. Peticiones con `mailto=` para entrar en el pool «educado» |

**Pendientes de comprobar más adelante:** F7 ZooBank, F9 RSS (Fase 5), F10 3D (Fase 6), F11 Open Tree of Life (Fase 3), F12 tamaños (Fase 6).

Fuentes de esta comprobación: [Reusing Wikipedia content](https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content) · [PBDB pasa a CC BY (Creative Commons, 2013)](https://creativecommons.org/2013/12/19/paleobiology-database-now-cc-by/) · [PhyloPic: Usage of Images](https://www.phylopic.org/articles/image-usage) · [Commons:Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing) · [Extension:CommonsMetadata](https://www.mediawiki.org/wiki/Extension:CommonsMetadata) · [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) · [Crossref: Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/) · [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy) · [API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette)

**Reglas comunes de acceso:**
- `User-Agent` con el formato `paleo-atlas-bot/<versión> (<URL del repo>; <correo>) <librería>/<versión>`: Wikimedia exige un User-Agent descriptivo con contacto, que contenga «bot» si es automático, y bloquea sin aviso los genéricos.
- Wikimedia: peticiones **en serie** (nunca en paralelo), agrupar títulos en una sola petición (`titles=A|B|C`), `maxlag`, gzip, GET para lecturas, caché de lo ya descargado.
- Crossref: parámetro `mailto=`.
- DOAJ responde 403 a los User-Agent con «bot»: recibe el mismo User-Agent descriptivo, con proyecto y contacto, sin esa palabra.
- Respetar los límites de peticiones; reintentos con backoff exponencial.
- Guardar la respuesta cruda antes de transformar nada. Se quitan solo los campos volátiles (que cambian en cada consulta sin cambiar el dato) y, en Commons y PhyloPic, se guarda el subconjunto de campos que se usa; los abstracts nunca entran en el crudo.

---

## 6. Arquitectura

```
CAPA DIARIA (DuckDB, GitHub Actions)              CAPA MENSUAL (PySpark local)
────────────────────────────────────              ────────────────────────────
¿Ha cambiado algo? (revisión de Wikipedia,        F3 GBIF: descarga filtrada (con DOI)
 RSS, PBDB) ── no ──► fin                           → reconciliar nombres con PBDB
     │ sí                                           → agregar por taxón / institución / país
F1 F2 F4 F5 F6 F7 ─► raw JSON (rama `data`)         → extracto Parquet
     │                                              ↕ mismo trabajo en DuckDB → benchmark
     └────────► dbt (DuckDB): staging → intermediate → marts ◄──┘
                     + snapshots (historial, §9)
                                 │
                 Generador de web estática (ES + EN)
                                 │
                           GitHub Pages
```

**Decisiones de arquitectura (cada una tendrá su ADR, ver §20):**
- **D1.** Sin Spark en la capa diaria: el volumen no lo justifica.
- **D2.** DuckDB en vez de base de datos alojada: coste cero, sin mantenimiento.
- **D3.** El estado vive en git: respuestas crudas versionadas en la rama `data`; el almacén DuckDB se **reconstruye entero** en cada ejecución → idempotente y auditable. La rama `data` guarda el crudo versionado y los derivados públicos (hechos, textos y títulos traducidos); **nunca** abstracts ni citas privadas, que solo viven en la caché local.
- **D4.** Comandos independientes del orquestador: Airflow y GitHub Actions solo los llaman.
- **D5.** Spark solo para GBIF, en local, y medido contra DuckDB.
- **D6.** Imágenes y 3D solo con licencias permitidas (§19); nunca de prensa.
- **D7.** Fichas narrativas propias: hechos con fuente → redacción nueva con LLM → verificaciones automáticas. La plantilla es el respaldo si algo falla (§12.1).
- **D8.** Bilingüe desde el principio: los datos no dependen del idioma; solo los textos y las plantillas se duplican.
- **D9.** Historial desde el día 1, **calculado en SQL (SCD tipo 2) a partir de las versiones crudas** versionadas en git. Se descartan los `dbt snapshots`: guardan estado entre ejecuciones y chocan con D3 (el almacén se reconstruye desde cero en cada ejecución, así que en CI/Actions se perdería el historial). Lo que no se captura, no se puede reconstruir después.
- **D10.** Detección de cambios barata antes de ejecutar el pipeline completo.

---

## 7. Fases y entregables

Cada fase tiene **criterio de terminado**. No se empieza una fase sin terminar la anterior. *Excepción (v14):* la Fase 2 se hace mientras la Fase 1 espera sus 2 semanas de ejecución autónoma, sin tocar `pipeline.yml`, `src/paleo/` ni `dbt/` para que esas semanas sigan contando (solo se añaden `airflow/`, scripts, tests y `ci.yml`).

### Fase 0 — Preparación
- [x] Esqueleto de carpetas
- [x] Documento de alcance
- [x] Nombre, licencias, idioma y presupuesto decididos (§22)
- [x] Licencias en el repo (`LICENSE`, `LICENSE-CONTENT.md`)
- [x] Decidir A4 (Python y gestor) y A5 (generador de web)
- [x] Verificar licencias de F1, F2, F4, F5, F6 (§5)
- [x] Crear repo público en GitHub
- [x] Configurar entorno: uv, Python 3.14, ruff, pytest, `.editorconfig`
- [x] Versión en inglés de este documento (`SCOPE.md`)

**Terminado cuando:** repo publicado en GitHub.

### Fase 1 — MVP (arcosaurios, bilingüe)
- [x] `ingest wikipedia`: página del año en curso vía API, guardado en crudo
- [x] Parser de la tabla de taxones (wikitext irregular → filas), con fixtures
- [x] Parser de las secciones de investigación (estudios sobre taxones ya conocidos → futuros eventos «Nuevo estudio» del historial)
- [x] `ingest pbdb`: datos de cada taxón nuevo y de los taxones citados en los estudios (snapshot por nombre, también «no encontrado»)
- [x] `ingest images`: Commons (ficheros de la tabla) → PhyloPic especie → género → clado, con licencia y autor
- [x] `ingest studies`: Crossref para cada estudio (§10), sin guardar abstracts en el crudo público, y DOAJ por ISSN; ZooBank aplazado (API caída)
- [x] dbt-duckdb: staging, intermediate y marts de §8
- [x] **Historial SCD2 desde las versiones crudas** (en lugar de `dbt snapshots`, ver D9), con test unitario de dbt; cada cambio de la fila de Wikipedia es un evento `entry_changed` del historial
- [x] Vínculo estudios ↔ taxones (wikilinks y nombres en cursiva resueltos en PBDB) y fichas básicas de taxones conocidos (datos; la web, en la semana 4)
- [x] Capa LLM intercambiable (Ollama local / Groq) con salida JSON validada, limitador de cuota y caché por contenido
- [x] Elegir LLM con plan gratuito (A18, ver §22)
- [x] Ingesta de artículos de Wikipedia EN/ES de las especies nuevas
- [x] Extracción de hechos con fuente (Wikipedia ES/EN, PBDB, metadatos y abstracts de estudios)
- [x] Redacción narrativa EN a partir de los hechos y adaptación ES alineada frase a frase (§12.1)
- [x] Verificaciones: fidelidad, anti-copia, cita por frase, repeticiones, longitud (§16)
- [x] Fichas de referencia (12, *gold set*) y evaluación de configuraciones (`eval/`); 4 revisadas por el usuario
- [x] Modelos dbt de hechos, citas y textos (`fct_taxon_text`)
- [x] Generar las fichas narrativas de las 82 especies nuevas (82/82 verificadas en EN, 81/82 en ES; Tromerosaurus ES con texto de respaldo)
- [x] Revisión del español (gramática, calcos y fidelidad al inglés) y títulos de los estudios en español (§12.1)
- [x] Lote robusto: una respuesta cortada se reintenta con el doble de tokens; si vuelve a fallar, se salta la especie y el lote sigue
- [x] Tests dbt y pytest de §16 (los de la Fase 1; tamaños, árbol y 3D llegan con sus fases)
- [x] Web ES + EN: portada con selector de idioma, «Última hora», ficha de taxón con historial, recap semanal, «Cómo evaluamos las fuentes», «Fuentes y licencias»
- [x] Ficha: una cita por obra, nombres científicos en cursiva y enlazados, recuadro «Lo último» (§11.1)
- [x] Buscador (pasa del backlog, decisión del usuario): alias en español (abelisáuridos, espinosaurio), periodos, erratas, facetas y `?q=` compartible
- [x] Galería de imágenes con visor ampliado: archivos de los artículos y de la categoría de Commons, tipo de imagen, lista blanca de licencias
- [x] CI: tests en cada push/PR (lint, pytest, parse + dbt build sobre el fixture)
- [ ] Ejecución programada diaria con detección de cambios + recap semanal (§15) *(workflow listo; el cron de las 06:00 no se lanzó el 2026-11-02 → horario movido a 06:23 con reserva a las 10:47)*
- [x] Informe de ejecución por cada run (`paleo report`: registro en `runs/` de la rama `data` y resumen en Actions)
- [x] Web publicada en GitHub Pages
- [x] Documento de fase ([`docs/fases/fase-1.md`](docs/fases/fase-1.md))

**Terminado cuando:** la web pública muestra las especies de arcosaurios de 2026 en los dos idiomas, con ficha narrativa verificada, imagen (o la del grupo), señales de fiabilidad e historial, y se ha actualizado sola **2 semanas seguidas** sin intervención.

### Fase 2 — Airflow
- [x] `docker compose` con Airflow 3.3.2 (LocalExecutor; `paleo` en su propio venv dentro de la imagen)
- [x] DAG diario y DAG semanal (recap), que llaman a los mismos comandos que Actions (`airflow/dags/paleo_steps.py`, una lista de pasos comprobada contra `pipeline.yml` por un test)
- [x] DAG mensual (provisional hasta la Fase 3: todas las fuentes otra vez, sin frescura)
- [x] Capturas para el README (DAG, ejecución correcta, reintento real con Wikipedia bloqueada)
- [x] Paridad con Actions: huella (hash por tabla del almacén y por archivo de la web) del DAG `paleo_ci_parity` igual a la que sube el CI para el mismo commit (`scripts/parity.py`); la ejecución diaria del DAG da los mismos totales que la de Actions del mismo día
- [x] Job de CI que carga los DAGs con Airflow 3.3.2 (sin errores de importación)
- [x] Documento de fase ([`docs/fases/fase-2.md`](docs/fases/fase-2.md))

Los DAGs no publican: trabajan sobre un clon local de la rama `data` (`airflow/work/`, fuera de git) y hacen commit sin push; Actions sigue siendo el único que publica. El paso narrativo se salta por defecto (`narrative=ollama` para usar el Ollama local; nunca Groq, cuya cuota es de Actions).

**Terminado cuando:** los DAGs producen exactamente el mismo resultado que los workflows de Actions.

### Fase 3 — Enciclopedia, ampliación y Spark
- [ ] Ingesta completa desde PBDB de todos los grupos de §4 (no solo taxones nuevos) *(arcosaurios hechos: 3.040 géneros, una descarga mensual por clado del seed; reptiles marinos y peces al activar sus filas)*
- [x] Ampliación del seed de alcance: reptiles marinos y peces fósiles (§4) *(358 géneros de reptiles marinos y 1.353 de peces; de sus páginas anuales solo entran las secciones del alcance)*
- [x] Reconstruir el historial hacia atrás: opiniones taxonómicas de PBDB + páginas anuales de Wikipedia de años anteriores (§9) *(2026-11-03: 19.354 eventos de 1758 a 2025 en 4.808 fichas; 4.741 de los 4.751 géneros tienen «Historia anterior»)*
- [x] Descarga filtrada de GBIF (F3) y su DOI en la página de fuentes *(fósiles de cordados sin mamíferos ni tortugas: 932.494 registros, DOI [10.15468/dl.8v87yz](https://doi.org/10.15468/dl.8v87yz); `paleo gbif extract` reutiliza una descarga de menos de 28 días)*
- [x] Job PySpark local: reconciliación de nombres con PBDB (sinónimos, erratas, rango) + agregados *(138.388 especímenes en 1.739 géneros: exacto 118.371, sinónimo 17.052, errata 2.965; las coordenadas que GBIF marca como erróneas no van al mapa)*
- [x] Mismo trabajo en DuckDB → **benchmark** (tiempo, memoria, complejidad del código) *(mismo extracto fila a fila; DuckDB 15–17× más rápido y 3–6× menos memoria: [`benchmarks/gbif/results.md`](benchmarks/gbif/results.md))*
- [ ] *Opcional:* mismo job en Databricks Free Edition (verificar cuotas y acceso a datos externos)
- [x] Web: fichas de enciclopedia con mapa de hallazgos, museos y línea temporal *(la línea temporal hacia atrás va agrupada por décadas, debajo de lo seguido desde 2026)*
- [x] Índices por grupo, época y país *(arcosaurios; el país sale de las ocurrencias de PBDB, una descarga mensual por bloque)*
- [x] Familia y clasificación completa en cada ficha (PBDB) *(2026-11-03: los 4.751 géneros, y las especies a través de su género; cadena de PBDB desde la raíz del bloque)*
- [ ] Fichas narrativas para toda la enciclopedia (§12.1), por lotes dentro del plan gratuito del LLM *(en curso: géneros con artículo en Wikipedia, 2.743, en lotes nocturnos con la GPU local, `paleo narrate --scope genera --until HH:MM`, reanudable; primer lote del 2026-11-03: 201 géneros, 181 verificados en EN y 144 en ES)*
- [x] Árbol de parentesco con escala temporal (§11.2): clasificación de PBDB; rangos temporales de PBDB *(2026-11-03: 4.846 de 4.930 fichas, 98 %; grupo mediano de 27 géneros, se dibujan hasta 20. Open Tree of Life descartado por ahora: ver F11)*
- [x] DAG mensual real en Airflow *(2026-11-02, en verde en local: refresco de fuentes → catálogo → descarga de GBIF (reutilizada) → job de Spark en Docker (14 s) → build → web; el extracto solo cambia si cambian sus filas, sea cual sea el motor)*
- [ ] Documento de fase (`docs/fases/fase-3.md`)

**Terminado cuando:** la enciclopedia de los tres bloques de §4 está publicada y el benchmark está documentado con cifras reales.

### Fase 4 — Portfolio
- [ ] README bilingüe completo (§20)
- [ ] ADRs D1–D10
- [ ] Interview pack: one-pager, vídeo de 2 min, postmortem
- [ ] Entrada en `cv.md` vía modo `add` de career-ops, con métricas reales de §17
- [ ] Enlace en LinkedIn y en el perfil de GitHub
- [ ] Documento de fase (`docs/fases/fase-4.md`)

**Terminado cuando:** el proyecto aparece en el CV con URL y métricas verificables.

### Fase 5 — IA y noticias
- [ ] Ingesta RSS (F9)
- [ ] Clasificación de noticias (especie nueva / revisión / fósil nuevo / ruido): baseline clásico vs LLM, con métricas
- [ ] Extracción del taxón mencionado y enlace a su ficha
- [ ] Deduplicación de la misma noticia entre medios (embeddings)
- [ ] Glosario bilingüe con explicaciones emergentes en las fichas (§12)
- [ ] Documento de fase (`docs/fases/fase-5.md`)

**Terminado cuando:** las métricas de clasificación de noticias están publicadas en el README y el glosario está revisado y en las fichas.

### Fase 6 — Extras
- [ ] Modelos 3D curados (§13)
- [ ] Comparador de tamaños (§11.3)
- [ ] Documento de fase (`docs/fases/fase-6.md`)

**Terminado cuando:** cada extra cumple sus reglas de §11.3 y §13 y se ha publicado.

---

## 8. Modelo de datos (dbt)

### Entidades
| Entidad | Descripción |
|---|---|
| Taxón | Nombre aceptado, rango, autores, año, clado, bloque de §4, rango temporal |
| Evento | Algo que le pasa a un taxón: descripción, reasignación, sinonimia, espécimen nuevo, nueva hipótesis, retracción *(Fase 5: noticia)* (§9) |
| Estudio | Publicación científica: DOI, revista, tipo, señales de fiabilidad (§10) |
| Espécimen / ocurrencia | Registro fósil con lugar, edad e institución (PBDB y GBIF) |
| Institución | Museo o colección |
| Imagen | URL, licencia, autor, nivel (especie / género / clado / grupo); el tipo (fósil, diente, reconstrucción…) solo en la galería |
| Modelo 3D | URL, tipo (escaneo / reconstrucción), año, autor, licencia (§13) |
| Tamaño corporal | Longitud y/o masa estimada (mín.–máx.), método, cita (§11.3) |
| Objeto de referencia | Humano, elefante, autobús, avión…: medidas con fuente (§11.3) |
| Hecho | Afirmación atómica sobre un taxón, con fuente, cita y fragmento de origen (§12.1) |
| Texto de ficha | Secciones redactadas por idioma, frases enlazadas a sus hechos, estado de verificación |
| Término del glosario | Término, definición ES, definición EN, estado de revisión (§12) |

### Capas (nombres orientativos; *(hecho)* = existe con ese nombre)
- **seeds:** `license_allowlist`, `trusted_journals`, `group_clades` y `scope_clades` *(hechos; `scope_clades` es el alcance de §4)*; `contested_topics` *(Fase 3)*, `models_3d`, `glossary`, `body_sizes`, `reference_objects`. El título de las páginas anuales sigue en `config.py` y en la macro `wikipedia_block` (se unifica al activar los bloques nuevos)
- **staging:** *(hechos)* `stg_wikipedia__new_taxa`, `stg_wikipedia__research_items`, `stg_pbdb__taxa`, `stg_phylopic__images`, `stg_commons__images`, `stg_commons__taxon_files`, `stg_crossref__works`, `stg_doaj__journals`, `stg_narrative__*` (hechos, citas, textos, títulos), `stg_pipeline__runs`; los artículos de Wikipedia se leen en Python (`paleo facts`), no en dbt. *(Fases siguientes)* `stg_pbdb__opinions`, `stg_pbdb__occurrences`, `stg_gbif__genus_specimens`, `stg_gbif__institutions`, `stg_gbif__downloads` *(los de GBIF, hechos: leen el extracto agregado, no los registros)*, `stg_phylopic__images`, `stg_commons__images`, `stg_crossref__works`, `stg_zoobank__names`, `stg_otol__tree`, `stg_body_sizes`
- **historial (SCD2 desde versiones crudas):** `int_new_taxa_history`; los `stg_*_versions` / `stg_*_revisions` conservan todas las versiones
- **intermediate:** *(hechos)* `int_taxon_pages`, `int_taxon_classification`, `int_research_taxon_links` (resolución de nombres), `int_image_candidates`, `int_image_best_per_taxon`, `int_study_reliability`, `int_taxon_events`
- **marts:** `dim_taxon`, `dim_taxon_tree` (padre-hijo + rango temporal), `dim_study`, `dim_institution`, `dim_geologic_interval`, `fct_taxon_event`, `fct_taxon_text` (texto verificado por idioma), `fct_specimens_by_taxon`. *(Hechos:* `dim_taxon`, `dim_study`, `dim_institution`, `fct_taxon_event`, `fct_taxon_text`, `fct_taxon_image`, `fct_specimens_by_taxon`*.)* El recap semanal se calcula en Python al generar la web y el resumen de ejecución lo escribe `paleo report` en `runs/`

---

## 9. Historial de cambios por taxón

Cada ficha tiene una **línea temporal** con todo lo que se sabe del taxón. Cuando una novedad afecta a un taxón ya conocido (por ejemplo, un estudio nuevo sobre *Spinosaurus*), la entrada en «Última hora» enlaza a esa línea temporal.

**Tipos de evento:** descripción original · reasignación de género o nueva combinación · sinonimia · *nomen dubium* · espécimen nuevo · nueva hipótesis (ecología, aspecto, tamaño) · corrección o retracción del estudio.

**De dónde sale:**
| Origen | Cubre | Fase |
|---|---|---|
| SCD tipo 2 sobre las versiones crudas de nuestras ingestas (evento `entry_changed`: estatus, autores, edad, localidad, estudio…) | Todo cambio desde que arranca el proyecto | 1 |
| Opiniones taxonómicas de PBDB (cada opinión trae año y referencia) | Historia taxonómica completa hacia atrás: descripción, sinonimias, *nomen dubium*, nombres sustituidos, nuevas combinaciones y revalidaciones *(hecho)* | 3 |
| Páginas anuales de Wikipedia de años anteriores (arcosaurios desde 2009, peces desde 2010, reptiles desde 2014) | Descripciones y estudios de años pasados *(hecho)* | 3 |
| Noticias clasificadas | Hipótesis nuevas y debates | 5 |

**Debates abiertos:** cuando haya estudios que se contradicen (p. ej., si *Spinosaurus* era cazador acuático o vadeador), el evento se marca **«En debate»** y enlaza a los estudios de cada postura. Se curan a mano en el seed `contested_topics` *(Fase 3, decisión del usuario del 2026-11-02; hasta entonces los debates se cuentan en la sección «Debates» del texto)*.

---

## 10. Verificación de estudios

No juzgamos la ciencia: **mostramos señales verificables** y explicamos qué significan.

| Señal | Cómo se comprueba | Distintivo en la web |
|---|---|---|
| Revisado por pares | Crossref: tipo `journal-article` en revista con ISSN | 🟢 Revisado por pares |
| Preprint | Crossref: tipo `posted-content`, o servidor de preprints (bioRxiv, PaleorXiv…) | 🟡 Preprint (sin revisar todavía) |
| Retractado o corregido | Crossref (incluye los datos de Retraction Watch) | 🔴 Retractado / 🟠 Corregido |
| Nombre registrado | ZooBank | ✔ Registrado en ZooBank |
| Revista de acceso abierto en DOAJ | DOAJ, por ISSN | Señal secundaria *(hecho)* |
| Revista en la lista de confianza | Seed `trusted_journals` (curado a mano: Nature, Science, JVP, Cretaceous Research, PeerJ, Papers in Palaeontology, Acta Palaeontologica Polonica…) | Señal secundaria |
| Recogido en PBDB *(Fase 3)* | PBDB | Señal secundaria |

**Reglas:**
- La regla que combina las señales es **pública y simple** (sin puntuaciones opacas) y se explica en la página «Cómo evaluamos las fuentes».
- Un estudio retractado no se borra: su evento se queda en el historial con el distintivo rojo.
- Revisión mensual de retracciones de todos los estudios ya publicados.
- Aviso general en el pie de cada página: contenido divulgativo, la ciencia cambia, se enlazan siempre las fuentes originales.

---

## 11. La web: idiomas, páginas y ficha

### Idiomas
- Español e inglés, con rutas `/es/` y `/en/`.
- La portada raíz es un **selector sencillo de idioma** (y recuerda la elección en el navegador).
- Cada página enlaza a su equivalente en el otro idioma.
- Nombres científicos sin traducir; nombres comunes y textos en cada idioma.

### Páginas
1. **Selector de idioma** (raíz).
2. **Portada:** «Última hora» + enlace al último recap.
3. **Recap semanal** (archivo de todas las semanas).
4. **Ficha de taxón.**
5. **Índices:** por grupo, época, país *(Fase 3)*.
6. **Glosario** *(Fase 5)*.
7. **Cómo evaluamos las fuentes.**
8. **Fuentes y licencias.**
9. **Acerca de:** qué es, autoría, enlace al repo.
10. **Buscador** (`/es/buscar.html`, `/en/search.html`): índice JSON por idioma, búsqueda en el navegador sin servidor.

### 11.1 Contenido de la ficha
| Campo | Fuente | Si falta |
|---|---|---|
| Nombre científico y significado *(el significado, Fase 3: hecho «etimología» con cita)* | F1 / PBDB | Ocultar el significado |
| Imagen 2D + autor + licencia, ampliable | F4 / F5 | Silueta del género, del clado o, en último caso, del grupo (seed `group_clades`), con aviso «imagen aproximada» |
| Galería (fósiles, dientes, esqueletos, reconstrucciones…; máx. 12, con autor y licencia) | F5 | Ocultar |
| «Lo último»: los 3 eventos más recientes del historial | §9 | Ocultar |
| Modelo 3D *(Fase 6)* | F10 | Ocultar |
| Familia y clasificación (familia → orden → clase) | PBDB | El nivel más bajo conocido |
| Grupo (clado) y bloque | PBDB / seed | Clado de F1 |
| Época y edad (Ma) | PBDB / F1 | «Desconocida» |
| Lugar del hallazgo | F1 / PBDB | Ocultar |
| Tamaño (rango + cita) y botón «Comparar» *(Fase 6)* | F12 / seed `body_sizes` (§11.3). **No se inventa** | Ocultar |
| Árbol de parentesco *(Fase 3)* | §11.2 | Solo la clasificación en texto |
| **Texto narrativo** por secciones: Descripción, Descubrimiento, Paleobiología, Clasificación, Época y hábitat, Debates; cada frase con su cita (una por obra) y los nombres científicos en cursiva, enlazados a su ficha o a Wikipedia | §12.1 | Texto de la plantilla (§11.4) |
| Línea temporal / historial | §9 | Solo la descripción original |
| Estudios con distintivos | §10 | — |
| Mapa de hallazgos *(Fase 3)* | PBDB + GBIF | Ocultar |
| Museos con especímenes *(Fase 3)* | GBIF | Ocultar |
| Fuentes y fecha de última actualización | Pipeline | Siempre visible |

### 11.2 Árbol de parentesco (Fase 3)
Lo que buscas se llama **cladograma** o, con el eje del tiempo, **árbol filogenético calibrado en el tiempo**.
- **Vista:** el taxón en el centro, su familia y sus «hermanos» (los parientes más cercanos), cada uno con su silueta (F4) y su nombre, y líneas que muestran el parentesco.
- **Eje temporal:** cada rama se dibuja en el intervalo en que vivió el animal (primera y última aparición en PBDB), sobre la escala de periodos (Triásico, Jurásico, Cretácico…). Filtros por época.
- **Navegable:** pulsar un hermano abre su ficha; se puede subir o bajar de nivel (familia → orden). Nunca se dibuja el árbol entero de golpe, solo el vecindario del taxón.
- **Honestidad:** la topología sale de la clasificación de PBDB, que es una clasificación y no un análisis filogenético. Se indica en la propia vista, y que la ubicación de muchos animales está en debate. *(Open Tree of Life se descartó el 2026-11-03: solo ~12 % de los géneros fósiles están en su árbol sintético, y mezclar las dos fuentes daría vecindarios casi vacíos.)*
- **Hecho (2026-11-03):** dos niveles, «Grupo» (el clado más bajo con al menos 3 géneros de la enciclopedia) y «Un nivel más arriba», cada uno con hasta 20 géneros, los más cercanos primero; SVG estático con enlaces, más un filtro por periodo; las especies muestran el árbol de su género. Las siluetas solo se ponen cuando son del propio género (41), no las del clado.

### 11.3 Comparador de tamaños (Fase 6)
- Elegir 2–4 elementos: taxones del atlas y objetos de referencia (persona, elefante africano, autobús, avión comercial…).
- Se dibujan **a escala** con sus siluetas (F4), en una cuadrícula en metros, con altura de una persona como referencia.
- **Solo tamaños con fuente:** cada taxón muestra el rango estimado (mín.–máx.) y la cita. Si no hay tamaño con fuente, el taxón no aparece en el comparador.
- Los objetos de referencia tienen medidas con fuente en el seed `reference_objects`.
- Aviso: los tamaños de los animales extintos son estimaciones y cambian con los estudios (enlaza con el historial de §9).

### 11.4 Texto de respaldo (plantilla)
Solo se usa si la ficha narrativa no existe todavía o no pasa las verificaciones. Plantillas en cada idioma a partir de los campos. Ej.: «Nuevo género de saurópodo del Cretácico Superior de Argentina, descrito por X et al. (2026)».

---

## 12. IA: fichas narrativas y glosario

### 12.1 Fichas narrativas (Fase 1: especies nuevas · Fase 3: toda la enciclopedia)
Prosa propia, no esquemas, en ES + EN, con cada frase citada.

**Proceso:**
1. **Extracción de hechos:** el LLM lee las fuentes (artículos de Wikipedia ES y EN, PBDB, metadatos y resúmenes de los estudios) y saca **hechos atómicos**. Cada hecho guarda su fuente, la cita y el fragmento de origen.
2. **Comprobación de hechos:** cada hecho tiene que estar respaldado por su fragmento de origen; si no, se descarta.
3. **Redacción:** el LLM escribe **prosa nueva** por secciones (Descripción, Descubrimiento, Paleobiología, Clasificación, Época y hábitat, Debates) **solo a partir de los hechos**, en cada idioma, con la cita de cada frase.
4. **Verificaciones automáticas** (§16):
   - **Fidelidad:** cada nombre, número y fecha del texto está en los hechos.
   - **Anti-copia:** ninguna frase reproduce secuencias largas de palabras de la fuente.
   - **Cita por frase:** ninguna frase sin al menos una cita.
5. **Revisión del español:** una pasada más corrige gramática, calcos y errores de traducción frente al inglés; la versión revisada solo se acepta si vuelve a pasar las verificaciones.
6. **Revisión manual** de una muestra; se publica el % que pasa cada verificación (§17).

**Reglas:**
- **Tono:** divulgativo para adultos curiosos y adolescentes (A19), tercera persona, tecnicismos explicados la primera vez (decisión del usuario, 2026-11-01).
- **Longitud:** según los datos, ~120–450 palabras, con un tope duro de 520; nunca se rellena (decisión del usuario). El redactor recibe como mucho 24 hechos, repartidos entre secciones.
- **Español:** se adapta el texto inglés ya verificado, frase a frase y con las mismas citas (más barato y coherente); la guía fija convenciones (Cretácico Superior, pisos en -iense, tildes de los grupos).
- **Lo importante se comprueba con código, no se pide al modelo:** un hecho cuya redacción copia su fuente se rechaza en la extracción, porque el redactor la copiaría después.
- Si una ficha no pasa las verificaciones, se reintenta dos veces con los errores concretos y la forma de corregirlos; si sigue fallando, se publica el texto de respaldo (§11.4) y se marca para revisión.
- Se generan **una vez por cambio** de los hechos o de los prompts (no en cada visita) y se guardan en el repo → caben en un plan gratuito.
- Los clados por encima de la familia pueden escribirse en español («cocodrilomorfos», «neognatas»); los géneros y las especies, nunca.
- Los títulos de los estudios se traducen al español con las mismas comprobaciones (números y nombres científicos intactos); en la web ES se muestra el título traducido y, debajo, el original con el aviso «Artículo en inglés».
- **Reparto de cuota:** Groq para lo nuevo de cada día (~10–15 mil tokens por especie → unas 13 especies al día con 200 000 tokens; lo que no cabe espera al día siguiente); la GPU local para regenerarlo todo tras un cambio de prompt y para las evaluaciones.
- Si se acaba la cuota gratuita del LLM, el pipeline sigue funcionando: las fichas pendientes esperan con el texto de respaldo.
- Los temas en debate (§9) se cuentan como debate, con las posturas y sus estudios; nunca se presenta una hipótesis como hecho.
- Pie de cada ficha: «Texto redactado con ayuda de IA a partir de las fuentes citadas y verificado automáticamente».

### 12.2 Glosario (Fase 5) — coste cero en la web
- 150–300 términos (holotipo, terópodo, Cretácico, Ma, *nomen dubium*…), en ES + EN.
- Primer borrador con LLM, **revisado a mano** antes de publicar (estado de revisión en el seed).
- En las fichas, los términos llevan una explicación emergente al pasar el ratón o al tocarlos; página de glosario completa.

---

## 13. Modelos 3D

Dos tipos, con reglas distintas:

| Tipo | Ejemplos de origen | Fiabilidad | Regla |
|---|---|---|---|
| **Escaneo de fósil real** | Smithsonian 3D, MorphoSource, colecciones de museos | Alta: es el hueso, no una interpretación | Preferido |
| **Reconstrucción en vida** | Sketchfab, paleoartistas | Artística; puede quedar desfasada | Solo con autor y año; aviso automático si es anterior a la última revisión importante del taxón (sale del historial de §9): «Puede no reflejar los últimos estudios» |

- Licencia: mismas licencias permitidas que las imágenes (§19). Si solo permite el visor oficial embebido, se usa ese visor.
- Técnica: visor glTF (`<model-viewer>`) o embebido oficial, **cargado solo al pulsar** para no hacer pesada la ficha.
- Los modelos pesados no se alojan en el repo (límites de tamaño de GitHub Pages): se enlazan o embeben desde el origen.
- Curación manual en el seed `models_3d`. Cobertura esperada: baja (decenas de taxones). La imagen 2D se mantiene siempre.

---

## 14. Contrato de comandos del pipeline

Lo que tiene que existir; la implementación se decide en la Fase 1.

| Comando | Hace | Idempotente |
|---|---|---|
| `paleo check` | ¿Ha cambiado la página de Wikipedia desde la última ejecución? Sale con 0 (sí), 1 (no) o 2 (no se pudo comprobar: el workflow lo trata como «sí») | Sí |
| `paleo ingest wikipedia --year AAAA` | Descarga y guarda en crudo (un fichero por revisión) | Sí |
| `paleo parse wikipedia --year AAAA` | Crudo → `new_taxa.jsonl` + `research.jsonl`; `--force` re-procesa las revisiones ya procesadas sin volver a descargar | Sí |
| `paleo ingest pbdb` | Datos PBDB de los taxones pendientes | Sí |
| `paleo ingest images` | Commons y PhyloPic (taxón, género, clados y grupo) y la galería | Sí |
| `paleo ingest articles` | Artículos de Wikipedia EN/ES de las especies nuevas | Sí |
| `paleo facts` / `write` / `titles` | Hechos, fichas EN + ES y títulos en español (`--provider ollama\|groq`) | Sí (caché por contenido) |
| `paleo eval run` | Evaluación sobre las fichas de referencia | Sí |
| `paleo ingest studies` | Crossref y DOAJ (ZooBank cuando vuelva su API); abstracts solo en la caché local | Sí |
| `paleo gbif extract` *(Fase 3)* | Descarga filtrada de GBIF (espera a que GBIF la prepare; reutiliza una de menos de 28 días) | Sí |
| `paleo gbif reconcile [--engine duckdb\|spark]` *(Fase 3)* | Reconciliación con PBDB y agregados → extracto en `raw/gbif/extract/` | Sí (mismo extracto con los dos motores) |
| `paleo build` | `dbt build` (modelos + tests; el historial sale de las versiones crudas) | Sí (reconstrucción completa) |
| `paleo site` | Genera la web ES + EN | Sí |
| *(recap)* | Lo genera `paleo site` para todas las semanas | Sí |
| `paleo report start` / `finish` / `ran-today` | Registro e informe de la ejecución (§16) | Sí |

Requisitos: códigos de salida fiables (0 = OK), logs legibles, sin estado oculto fuera de git y de `data/`. Sin logs estructurados: Airflow guarda el log de cada tarea y el informe de ejecución (§16) recoge lo que hay que medir (decidido en la Fase 2).

---

## 15. Orquestación y frescura

Con una web estática no hay tiempo real al minuto, pero sí **en horas**, gratis:

| Qué | Dónde | Cuándo |
|---|---|---|
| Tests (pytest + dbt) | GitHub Actions | Cada push y PR |
| Detección de cambios + pipeline si hay novedades | GitHub Actions (cron) | Diario, 06:23 UTC; reserva a las 10:47 UTC si la principal no terminó (A6) |
| Recap semanal | GitHub Actions (cron) | Lunes, en la misma ejecución diaria (A6) |
| Pipeline mensual (GBIF, revisión de retracciones) | Local (Spark en mi máquina) | Mensual |
| Demostración | Airflow en Docker (local): `paleo_daily` (mar–dom), `paleo_weekly` (lunes), `paleo_monthly` y `paleo_ci_parity`; pausados al crearse, sin publicar | Bajo demanda |

- Detección barata: comparar el número de revisión de las páginas de Wikipedia y el contenido de RSS/PBDB con lo guardado. Si no hay cambios, no se ingesta ni se gasta LLM; solo se reconstruyen el almacén y la web (~1–2 min) y se guarda el registro de la ejecución.
- **Registro de ejecuciones** (`runs/<fecha>.json` en la rama `data`): toda ejecución deja constancia, también sin cambios. Lo leen el test de frescura (§16) y el pie de la web («fuentes comprobadas el…»), y da actividad diaria al repositorio (regla de los 60 días).
- Fallo del pipeline → aviso por correo de GitHub; la web anterior se queda publicada (nunca se publica una web rota).
- Los cron de GitHub no son puntuales: en el minuto 0 de cada hora pueden retrasarse o descartarse. Por eso la ejecución va a las 06:23 y hay una reserva a las 10:47 que no hace nada si la principal ya terminó bien. La primera ejecución programada (06:00) no se lanzó el 2026-11-02.
- GitHub desactiva los workflows programados de repos públicos tras 60 días sin actividad. Mitigado: el pipeline hace un commit diario en la rama `data` (registro de ejecuciones). Si aun así se desactivara, el test de frescura y el pie de la web lo delatan.

---

## 16. Calidad de datos y observabilidad

### Tests dbt (mínimos)
- `unique` y `not_null` en claves de todas las dimensiones.
- `relationships` entre hechos y dimensiones.
- `accepted_values` en tipo de evento, tipo de imagen y licencias permitidas.
- **Tolerancia al retraso de PBDB:** un taxón nuevo sin correspondencia en PBDB es *aviso* durante N semanas (A7); después, *error*.
- Frescura: la última detección de cambios no puede tener más de 2 días.
- Ninguna imagen ni modelo 3D sin licencia permitida y autor.
- Todo estudio tiene al menos una señal de fiabilidad calculada.
- Todo tamaño corporal tiene rango, método y cita.
- Todo nodo del árbol tiene origen (Open Tree of Life o PBDB).
- Fichas narrativas: fidelidad (nombres, números y fechas presentes en los hechos), anti-copia (ninguna secuencia de **8** palabras igual a la fuente que contenga al menos 4 palabras «corrientes»: las listas de nombres, números y epítetos no cuentan como prosa), ningún hecho como única cita de dos frases (repetición), al menos una cita por frase, todo hecho con fragmento de origen.
- Paridad de idiomas: toda página en ES existe en EN y viceversa.

### Tests de Python
- Parser de las tablas de Wikipedia con casos reales guardados (fixtures).
- Reconciliación de nombres con casos conocidos (sinónimos, erratas).
- Verificadores de fidelidad y anti-copia, con casos buenos y malos guardados (Fase 1).
- Ingestas (PBDB, Crossref, Commons, PhyloPic) con transporte simulado: idempotencia, frescura, lotes, «no encontrado», abstract eliminado.

### Tests unitarios de dbt
- Historial SCD2: solo se abre una versión nueva cuando cambia un campo.

### CI sin red
- El CI siembra los fixtures crudos (`tests/fixtures/`) y ejecuta el pipeline completo. La variable `as_of` fija «hoy» para que los tests con fechas no cambien de resultado con el paso del tiempo.

### Informe de ejecución (por cada run)
Fuentes con cambios, taxones nuevos / actualizados, eventos nuevos, % con correspondencia PBDB, % con imagen por nivel, avisos y errores de tests, duración por paso.

---

## 17. Métricas del proyecto (para CV y entrevistas)

Se rellenan con datos reales; **nunca se estiman en el CV**.

| Métrica | Valor | Fecha |
|---|---|---|
| Taxones nuevos de 2026 recogidos / total de las páginas de Wikipedia | 82 / 82 (arcosaurios) | 2026-11-02 |
| Taxones en la enciclopedia por bloque | Arcosaurios: 280 (82 nuevos + 198 conocidos) | 2026-11-02 |
| Eventos en el historial | 403 seguidos desde 2026 + 19.354 hacia atrás (PBDB y páginas anuales 2009–2025) | 2026-11-03 |
| Fichas con árbol de parentesco | 4.846 / 4.930 (98 %; clasificación de PBDB) | 2026-11-03 |
| % con correspondencia en PBDB | Nuevos 41 % (PBDB tarda en añadirlos) · conocidos 99 % | 2026-11-02 |
| % con imagen (especie / género / clado) | 100 %: especie 36 % · género 4 % · clado 49 % · grupo 11 % | 2026-11-02 |
| % de estudios revisados por pares / preprints / retractados | 94 % / 0 % / 0 % (5 corregidos; 28 % en revistas DOAJ) | 2026-11-02 |
| Retraso medio publicación → web (horas) | — | — |
| Semanas seguidas sin intervención manual | 0 (empieza a contar con el primer cron) | 2026-11-02 |
| Nº de tests (pytest + dbt) | 165 + 121 (rama `fase-3`) | 2026-11-02 |
| Duración del pipeline diario | ~1 min (ejecución completa sin LLM, 2026-11-02) | 2026-11-02 |
| Coste mensual | 0 € | — |
| GBIF: especímenes fósiles procesados | 932.494 procesados → 138.388 reconciliados con 1.739 géneros, de 78 instituciones | 2026-11-02 |
| Benchmark Spark vs DuckDB: tiempo, memoria | 932.494 filas: DuckDB 0,86 s / 459 MB · Spark 13,7 s / 1,5 GB (local, 16 hilos); código 124 vs 242 líneas | 2026-11-02 |
| Clasificador de noticias: precisión / recall (baseline vs LLM) | — | — |
| Fichas narrativas que pasan fidelidad / anti-copia / cita por frase (%) | Todas las verificaciones: EN 100 % · ES 99 % (82 especies, Groq) · géneros con Qwen 3.5 9B local: EN 90 % · ES 72 % (201 géneros, primer lote) | 2026-11-03 |
| Hechos extraídos que pasan la comprobación (%) | 78 % (1685 de 2158) | 2026-11-02 |

---

## 18. Costes: 0 €

**Regla dura:** el proyecto no puede costar dinero. Nada que pueda generar una factura. Si un servicio pide tarjeta, solo se usa si su plan gratuito tiene un tope que impida cobrar, y se documenta.

| Concepto | Solución gratuita |
|---|---|
| Repo, CI, ejecución programada, web | GitHub (repo público: Actions y Pages gratis) |
| APIs de datos (F1–F8) | Públicas y gratuitas |
| GBIF | API de descargas (gratis) en vez de la copia completa en AWS |
| Spark | Modo local en mi máquina (Docker) |
| Databricks *(opcional)* | Free Edition (verificar límites) |
| LLM (desde la Fase 1) | **Local:** Ollama con Qwen 3.5 9B en la RTX 5070 Ti del autor (sin cuota; `ollama/Modelfile.*`, contexto de 16K). **Groq** plan gratuito: por modelo 30 peticiones/min, 1.000/día, 8.000 tokens/min y 200.000/día (`qwen3.8-27b`, además, 1.000 tokens de respuesta/min: inservible). GitHub Models cerró el 30-07-2026. Si se agota la cuota, las fichas esperan con el texto de respaldo |
| Dominio | `github.io` |

---

## 19. Licencias, atribución y ética

*(Esto no es asesoramiento legal; si el proyecto llega a generar ingresos, conviene consultarlo con un profesional.)*

| Qué | Licencia | Por qué |
|---|---|---|
| **Código** | **AGPL-3.0** | Copyleft también para uso en red: quien monte un servicio con tu código (modificado o no) tiene que publicar su código con la misma licencia y conservar tu autoría. Como titular, puedes dar licencias comerciales aparte más adelante (doble licencia) |
| **Contenido propio** (textos de las fichas, recaps, glosario, diseño de la web) | **CC BY-NC-SA 4.0** | Atribución obligatoria; nadie puede usarlo comercialmente sin tu permiso; las obras derivadas, con la misma licencia |
| **Datos e imágenes de terceros** | La suya, siempre visible | Atribución en cada ficha y en «Fuentes y licencias» |

**Reglas para no entrar en conflicto con las fuentes:**
- **No se copia ni se adapta prosa de Wikipedia** (CC BY-SA no admite que la obra derivada sea NC). Los hechos no tienen derechos de autor: el LLM lee el texto solo para **extraer hechos**, y lo publicado es redacción nueva que pasa el test anti-copia (§12.1).
- Las fichas citan, siempre que se pueda, la fuente primaria (el estudio), no solo Wikipedia.
- **Imágenes y modelos 3D: solo CC0, dominio público, CC BY o CC BY-SA.** Nada NC: si algún día monetizas (anuncios, patrocinios), una imagen NC te obligaría a retirarla.
- Cada imagen y modelo muestra autor y licencia.
- Cada descarga de GBIF se cita con su DOI.
- Los **abstracts de Crossref** (pueden tener derechos de los editores) nunca se guardan en el crudo público: solo en `data/cache/`, local y fuera de git.
- El texto generado con IA se etiqueta como tal.
- Rigor: si un dato no está en una fuente, no se muestra.

**Texto generado con IA:** probablemente no tiene derechos de autor (en la UE y en EE. UU. se exige autoría humana), así que la NC lo protege poco. Lo que sí es tuyo y protegible: la selección y revisión humana, el glosario revisado, el diseño, el código y la marca.

**Lo que ninguna licencia protege es la idea.** Lo que te protege: publicar pronto, el historial de git con fechas (prueba de autoría), el nombre «Paleo Atlas» y tu autoría visible en la web y en el repo.

---

## 20. Documentación y material de portfolio

### README bilingüe
- `README.md` (inglés) y `README.es.md` (español), con enlace al otro idioma en la primera línea.
- Contenido: qué es + enlace a la web + captura · arquitectura · decisiones de diseño (incluido **«Why no Spark in the daily layer»** y **«Spark vs DuckDB: measured»**) · benchmark · calidad de datos y métricas · cómo ejecutarlo en local · fuentes y licencias · limitaciones conocidas.

### Documento de alcance
- `ALCANCE.md` (español) es el **canónico**. `SCOPE.md` (inglés) se actualiza al cerrar cada fase, no en cada cambio, para no mantener dos documentos vivos a la vez.

### Documentos de fase (`docs/fases/`)
Uno por fase, escrito al cerrarla (en español; en inglés junto con `SCOPE.md`). Explica el **porqué**, no el qué: el problema, los conceptos desde cero, cómo funciona en el repo, por qué así (con las alternativas), cómo se comprueba, resultados reales, qué salió mal y preguntas de entrevista con respuesta. Sirve para estudiar y defender el proyecto. Si contradice a este documento, manda este.

### ADRs (`docs/adr/`)
D1–D10 de §6, en formato breve: contexto, decisión, alternativas, consecuencias.

### Interview pack (`docs/interview-pack/`)
- **One-pager:** producto, arquitectura, métricas, plan de evaluación.
- **Demo:** URL pública + vídeo de 2 minutos.
- **Postmortem:** qué funcionó, qué no, qué cambiaría.
- **Historias STAR** candidatas: estado en git, historial con snapshots, retraso de PBDB, reconciliación de nombres, Spark vs DuckDB, señales de fiabilidad, verificación de fidelidad del LLM, regla de 0 €.

---

## 21. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **El alcance crece demasiado** (ya hay 6 fases) | Proyecto sin terminar | Fases con criterio de terminado; ideas al backlog; el CV se actualiza tras la Fase 1, no al final |
| El proyecto quita tiempo a las candidaturas | Búsqueda de empleo frenada | Calendario a ratos (§23); las candidaturas van primero |
| La tabla de Wikipedia cambia de formato | Ingesta rota | Parser con fixtures; la web anterior sigue publicada |
| Taxones nuevos tardan en aparecer en PBDB | Fichas incompletas | Test tolerante al retraso; ficha con lo que haya |
| Sin imagen para especies nuevas | Ficha pobre | Imagen del género o clado, con aviso |
| El LLM inventa datos | Desinformación | Hechos con fragmento de origen + verificación de fidelidad + texto de respaldo + revisión de muestra |
| Paráfrasis demasiado cercana a Wikipedia | Conflicto de licencia | Test anti-copia; redacción solo desde hechos, nunca desde el texto original |
| Se acaba la cuota gratuita del LLM | Fichas sin texto narrativo | Generación por lotes, una vez por cambio; texto de respaldo mientras tanto |
| Licencias mal aplicadas | Problema legal / mala imagen | Verificación previa (§5); tests de licencia; nada NC |
| Tamaños sin fuente o desfasados | Desinformación | Solo tamaños con cita; rango visible; test de §16 |
| Árbol presentado como verdad absoluta | Desinformación | Origen indicado en la vista; aviso de que el parentesco está en debate |
| Modelo 3D desfasado | Desinformación | Preferir escaneos; aviso automático por fecha (§13) |
| GitHub desactiva el cron por inactividad | La web deja de actualizarse | Verificar la regla (§15); aviso en el informe de ejecución |
| El cron de GitHub no se lanza | Lo nuevo no se redacta ni se publica | Hora fuera del minuto 0 y cron de reserva; test de frescura (§16) y fecha de comprobación en el pie de la web |
| Afirmar en CV algo no hecho | Pillada en entrevista | Métricas solo reales (§17); CV vía modo `add` de career-ops |

---

## 22. Decisiones

### Cerradas
| # | Decisión | Resultado | Fecha |
|---|---|---|---|
| A1 | Nombre | **Paleo Atlas** (`paleo-atlas`) | 2026-10-31 |
| A2 | Licencias | Código **AGPL-3.0**; contenido propio **CC BY-NC-SA 4.0** (§19) | 2026-10-31 |
| A3 | Idiomas | Web ES + EN con selector; README bilingüe; `ALCANCE.md` canónico en ES + `SCOPE.md` en EN al cerrar cada fase | 2026-10-31 |
| A9 | Dónde corre Spark | Local (Docker); Databricks Free Edition opcional. GBIF por API de descargas | 2026-10-31 |
| A10 | Presupuesto | **0 €** (§18) | 2026-10-31 |
| A12 | Ampliar grupos | Sí: reptiles marinos y peces fósiles (§4), en la Fase 3 | 2026-10-31 |
| A13 | Fase 5 | Sí | 2026-10-31 |
| A4 | Python y gestor de dependencias | **uv** + **Python 3.14** (gestionado por uv, no el del sistema), fijado en `.python-version`. Comprobado el 2026-11-01: dbt-core 1.12, dbt-duckdb 1.11, DuckDB 2.0, Airflow 3.3 y PySpark 4.3 declaran soporte para 3.14 y las dependencias se resuelven sin conflictos. Herramientas: ruff (lint + formato) y pytest | 2026-11-01 |
| A5 | Generador de web | **Propio en Python con Jinja2** + JavaScript sin framework para lo interactivo | 2026-11-01 |
| A17 | Cómo se redactan las fichas | **Opción A:** fichas narrativas propias desde hechos con cita (§12.1), desde la Fase 1 | 2026-11-01 |
| A7 | Tolerancia al retraso de PBDB | **8 semanas** (variable `pbdb_lag_weeks` de dbt): antes, aviso; después, error | 2026-11-02 |
| A16 | Lista inicial de revistas de confianza | Seed `trusted_journals` (30 revistas); se amplía a mano | 2026-11-02 |
| A18 | LLM para las fichas | Qwen 3.5 9B local para lotes grandes, regeneraciones y evaluaciones (11/12 fichas de referencia verificadas, 46 % de hechos encontrados); Groq `gpt-oss-120b` para la ejecución diaria (12/12 verificadas en EN y ES, 38 % de los hechos en el texto). Descartados: Qwen 3.5 4B (peor y 4× más lento), Groq `qwen3.8-27b` (límite de salida) | 2026-11-02 |
| A6 | Frecuencia de detección y hora del recap | Diario a las 06:23 UTC (reserva a las 10:47); recap los lunes en esa misma ejecución | 2026-11-02 |
| A19 | Tono de las fichas | Divulgativo para adultos curiosos y adolescentes (lo que ya dice el prompt; ajustado el 2026-11-02 para no regenerar) | 2026-11-01 |
| A20 | Longitud de las fichas | Según los datos (~120–450 palabras), sin relleno | 2026-11-01 |
| A15 | Explicador conversacional | **Descartado**; se queda el glosario (§12.2) | 2026-11-01 |
| A11 | Dónde se guarda el extracto de GBIF | La descarga cruda (46 MB) se queda en la caché local, sin versionar: se puede reproducir con su DOI. En la rama `data` va solo el extracto agregado (76 KB) y la ficha de la descarga (clave, DOI, predicado, recuentos y licencia) | 2026-11-02 |
| A8 | Versión de Airflow | **3.3.2** (imagen oficial `python3.14`), LocalExecutor y auth simple solo en local | 2026-11-02 |

### Abiertas
| # | Decisión | Opciones | Cuándo |
|---|---|---|---|
| A14 | ¿Hacer la Fase 6? | Sí / no / solo 3D / solo comparador | Después de Fase 5 |

---

## 23. Calendario

A ratos y fines de semana, **sin frenar candidaturas**. Fechas orientativas; las Fases 5 y 6 se fechan al terminar la 4. Incluir los estudios de la Wikipedia en la Fase 1 puede alargarla unos 3 días.

| Semana | Fechas | Fase |
|---|---|---|
| 1 | 2026-11-02 → 11-08 | Fase 1 (ingesta Wikipedia, parser, dbt staging) |
| 2 | 11-09 → 11-15 | Fase 1 (PBDB, imágenes, estudios, snapshots, vínculo estudios ↔ taxones) |
| 3 | 11-16 → 11-22 | Fase 1 (fichas narrativas: hechos, redacción, verificaciones) |
| 4 | 11-23 → 11-29 | Fase 1 (web ES + EN, Actions; empiezan las 2 semanas de ejecución autónoma) |
| 5 | 11-30 → 12-06 | Fase 2 + **entrada provisional en el CV** |
| 6 | 12-07 → 12-13 | Fase 3 (ingesta completa PBDB, ampliación de grupos, historial hacia atrás) |
| 7 | 12-14 → 12-20 | Fase 3 (GBIF, Spark, benchmark) |
| 8 | 12-21 → 12-27 | Fase 3 (enciclopedia y fichas narrativas por lotes) + Fase 4 |
| 9+ | desde 12-28 | Fase 5, luego Fase 6 |

---

## 24. Backlog de ideas

Ideas que **no** están en el alcance todavía. Para pasar una idea al alcance: fase asignada + entrada en el registro de cambios.

| Idea | Notas |
|---|---|
| Tiempo real al minuto | Escuchar los cambios de Wikipedia en directo (EventStreams); necesita un proceso siempre encendido |
| Feed RSS de la propia web | Fácil con web estática |
| Mapa paleogeográfico (dónde estaban los continentes en esa época) | Existen servicios de reconstrucción de placas; a investigar |
| Newsletter semanal por correo con el recap | Necesita un servicio de envío gratuito |
| Más grupos: sinápsidos y mamíferos, invertebrados, plantas | Ampliar el seed de §4 |
| API pública de datos de Paleo Atlas | Revisar las licencias de redistribución |
| Cola de prioridad cuando un día no cabe en la cuota del LLM | Redactar primero las especies más recientes |
| Segundo proveedor LLM gratuito de reserva | Por si Groq falla o cambia su plan gratuito |
| Open Tree of Life como señal en el árbol | Decir en cada ficha si el género está en el árbol sintético y con cuántos estudios (F11 descartada como topología: 12 % de cobertura) |
| Imagen alternativa cuando la principal de PhyloPic es NC | Pedir otras imágenes del mismo nodo con licencia permitida (hoy se cae al género o clado) |
| Retracciones de los estudios de la «Historia anterior» | Cruzar cada mes los ~7.600 DOIs con el CSV de Retraction Watch (vía Crossref) sin guardar un registro por DOI; hoy salen como `unchecked` |
| Columna «Unit» de las páginas anuales antiguas (≤ 2018) | El parser la ignora con un aviso; los eventos no usan la localidad |

---

## 25. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-03 | v22: Fase 3, hito 7: clasificación completa y árbol de parentesco. Los clados por encima del género se descargan de PBDB una vez al mes por bloque (2.724), con un cierre recursivo en dbt (`int_genus_lineage`) y un mart del vecindario (`fct_taxon_neighborhood`, con test unitario). **Topología solo de PBDB** (decisión del usuario): Open Tree of Life reconoce 631 de 1.000 géneros fósiles, pero solo ~12 % están en su árbol sintético. El árbol es un SVG estático por nivel, con la escala de periodos | Plan de H7 aprobado |
| 2026-11-03 | v21: Fase 3, hito 4: historial hacia atrás. **Opiniones taxonómicas de PBDB** (unas 121.000, una descarga al mes por bloque, más las referencias que se citan): un evento la primera vez que un nombre cambia de estado (sinónimo de X, *nomen dubium*, sustituido por X, trasladado al género X), más la revalidación cuando la clasificación actual de PBDB lo vuelve a aceptar; un «belongs to» repetido nunca es evento (los autores discrepan durante décadas: *Brontosaurus*). **Páginas anuales de años anteriores** (45 páginas, carpeta aparte `wikipedia_past`): solo dan eventos, nunca páginas, textos, búsquedas de PBDB o de Crossref. Lo antiguo se marca `origin = backfill`: no entra en «Última hora» ni en los resúmenes semanales, y sus ~7.600 estudios no se comprueban en Crossref (estado `unchecked`, sin distintivo; cruzarlos con Retraction Watch queda en el backlog). Las fuentes de las fichas narrativas no cambian | Plan de H4 aprobado |
| 2026-11-03 | v20: Fase 3, hito 6 empezado: fichas narrativas de los géneros con artículo en Wikipedia, en lotes nocturnos con la GPU local (los artículos más largos primero). El wikitext de los géneros va a la caché local, no a `data`: cada hecho cita la revisión (`oldid`). Primer lote: 201 géneros en ~7,5 h (137 s por género; GPU a 72 °C de media). Lectura manual: el contenido es fiel; el español arrastra calcos que las verificaciones no ven, de ahí nuevas reglas en los prompts (`write-en-v6`, `adapt-es-v4`, `review-es-v3`), que reescriben esas fichas en el próximo lote. Una respuesta cortada en la extracción se repite en dos mitades | Revisión del primer lote |
| 2026-11-02 | v19: Fase 3, hito 5 (rama `fase-3`). Descarga de GBIF (F3 verificada; A11 cerrada): fósiles de cordados sin mamíferos ni tortugas (932.494 registros, DOI 10.15468/dl.8v87yz), pues el árbol de GBIF no tiene los clados de §4 y el filtro fino lo hace la reconciliación. El mismo job en DuckDB y en PySpark (especificación única; extractos idénticos con datos reales) y el **benchmark**: DuckDB gana a este volumen (0,9 s frente a 13,7 s). Mapa de hallazgos (SVG propio con Natural Earth, PBDB + GBIF; sin las coordenadas que GBIF marca como erróneas) y museos en cada ficha; cita del DOI en «Fuentes y licencias». DAG mensual con la descarga y Spark; la imagen de Airflow lleva Java | Plan de H5 |
| 2026-11-02 | v18: Fase 3, hito 3 (rama `fase-3`). Activados los reptiles marinos y los peces fósiles: páginas anuales de reptiles y paleoictiología (solo las secciones del alcance; mosasaurios entre los escamosos), seed de peces destacados, raíces de bloque en Wikidata, Paleozoico (Ordovícico–Pérmico y sus pisos en español), grupos nuevos, la columna «Location» de las tablas de peces es el país, estudios listados en dos páginas fusionados, homónimos entre bloques. La regla de alcance vive en un solo sitio (`paleo/scope.py`, aplicada al parsear): ninguna ingesta ni el LLM gastan peticiones o cuota en taxones fuera de §4 (de 259 especies nuevas de las tres páginas, 114 en alcance). Robustez: un fallo de Wikidata o de un lote de Commons ya no detiene la ingesta (se reintenta en la siguiente ejecución); el registro fósil usa las épocas de las edades en Ma cuando PBDB no da el nombre del intervalo | Plan de H3 |
| 2026-11-02 | v17: Fase 3, hito 2 (rama `fase-3`). Índices por grupo, época y país; ocurrencias de PBDB (países de 2.780 géneros, base del mapa); artículos de Wikipedia de los géneros **verificados** con Wikidata (P842 + ascendencia P171: el elemento de la polilla *Coloradia* lleva por error el ID de PBDB del dinosaurio) y su imagen principal libre como imagen de la ficha; siluetas de PhyloPic de todos los géneros con un tope diario; índice del buscador compacto (2,2 MB → 0,9 MB); traducción de subpisos («Campaniense superior»); el comprobador detecta fichas huérfanas y webs vacías; nueva fuente F13 (Wikidata) | Plan de H2 |
| 2026-11-02 | v16: empieza la Fase 3 en la rama `fase-3` (datos en `data-fase-3`), con merge a `main` al cerrar la Fase 1. Decisiones: una ficha por género; peces = Placodermi + Chondrichthyes + seed de destacados; narrativas solo para géneros con artículo en Wikipedia, en lotes con la GPU local. Hito 1: seed `scope_clades` (alcance como datos), catálogo de PBDB por clado (`taxon_status=accepted`, sin icnotaxones), 3.040 fichas de género de arcosaurios, enlace especie → género | Decisión del usuario |
| 2026-11-02 | v15: documentos de fase en `docs/fases/` (§20): Fases 1 y 2 escritos; uno más en cada fase como entregable al cerrarla | Petición del usuario |
| 2026-11-02 | v14: Fase 2 (Airflow 3.3.2 en Docker): DAGs diario, semanal, mensual provisional y de paridad con el CI; lista única de pasos comprobada contra `pipeline.yml`; huella del almacén y de la web para demostrar el mismo resultado; job de CI que carga los DAGs; A8 cerrada; sin logs estructurados (§14). Se hace en paralelo a las 2 semanas autónomas de la Fase 1 sin tocar lo que usa Actions | Decisión del usuario |
| 2026-11-02 | v13: revisión completa de la Fase 1. Arreglos: `paleo check` distingue un fallo (salida 2), PBDB deja de consultar nombres que no son taxones, CI en todas las ramas, fichas «conocidas» fuera de §4 (mamíferos) eliminadas. Añadido: silueta del grupo (0 fichas sin imagen), eventos `entry_changed` desde el SCD2, señal DOAJ, crédito de PBDB en cada ficha, texto de respaldo y fuentes en las fichas sin texto, cifras de verificación en «Cómo evaluamos», hreflang absolutos. A Fase 3: «En debate», «Recogido en PBDB» y significado del nombre; A19 ajustada. Documento alineado con el código (§5, §8, §14, §26) | Revisión pedida por el usuario |
| 2026-11-02 | v12: informe de ejecución (`paleo report`) y registro diario en `runs/`; test de frescura; cron a las 06:23 con reserva a las 10:47; la web se reconstruye a diario aunque no haya cambios; el commit a `data` va al final y siempre | El cron de las 06:00 no se lanzó |
| 2026-11-02 | v11: semana 4 (web Jinja2 publicada en GitHub Pages, rama `data`, pipeline diario); 82 fichas generadas; buscador del backlog a la Fase 1; galería con visor; revisión del español y títulos en español; una cita por obra y nombres enlazados; reintentos del lote; A6 y A18 cerradas | Ronda de revisión del usuario y semana 4 |
| 2026-11-01 | v10: pipeline narrativo completo (capa LLM, artículos, hechos, redacción EN + adaptación ES, verificaciones); 12 fichas de referencia y evaluación de 4 configuraciones; A18 provisional, A19 (tono) y A20 (longitud) cerradas; staging de dbt materializado como tablas; modelos de textos | Semana 3 |
| 2026-11-02 | v9: semana 2 terminada (PBDB, Crossref, imágenes, vínculo estudios ↔ taxones, marts); **fichas básicas para taxones conocidos** en la Fase 1; D9 cambia de `dbt snapshots` a SCD2 desde versiones crudas; ZooBank aplazado (API caída); abstracts solo en caché local; A16 cerrada | Decisión del usuario y hallazgos de la semana 2 |
| 2026-11-02 | v8: los ~380 estudios sobre taxones ya conocidos de las páginas anuales entran en la Fase 1 (eventos «Nuevo estudio» del historial; solo título, revista, DOI y distintivos, nunca la prosa de Wikipedia); nuevo comando `paleo parse wikipedia`; semana 1 completada (ingesta, parser, staging dbt, CI) | Decisión del usuario |
| 2026-11-01 | v7: entorno configurado (A4 concretada: Python 3.14); `SCOPE.md` creado; **Fase 0 cerrada**; §2 anonimizado (sin nombres de empresas); orden de F10 y del registro corregido | Cierre de la Fase 0 |
| 2026-11-01 | v6: licencias de F1, F2, F4, F5 y F6 comprobadas; listas blancas de licencias para imágenes; reglas de acceso de Wikimedia y Crossref (§5) | Comprobación de la Fase 0 |
| 2026-11-01 | v5: fichas narrativas propias desde hechos con cita, adelantadas a la Fase 1 (§12.1); verificaciones de fidelidad y anti-copia; A4 y A5 cerradas; nueva decisión A18 (LLM); calendario ampliado una semana | Decisión del usuario (opción A) |
| 2026-11-01 | v4: eliminado el explicador conversacional (antiguo §12.3); propuestas para A4 y A5 | Decisión del usuario |
| 2026-11-01 | v3: familia y clasificación en la ficha; árbol de parentesco con escala temporal (§11.2, Fase 3); comparador de tamaños (§11.3, Fase 6); fuentes F11 (Open Tree of Life) y F12 (tamaños corporales) | Petición del usuario |
| 2026-10-31 | v2: historial por taxón (§9); verificación de estudios (§10); web bilingüe; «Última hora» diaria + recap semanal; IA (resúmenes, glosario, explicador) (§12); modelos 3D (§13); ampliación a reptiles marinos y peces fósiles (§4); AWS sustituido por GBIF vía API + Spark local (regla de 0 €); licencias AGPL-3.0 + CC BY-NC-SA 4.0; nueva Fase 6; backlog | Decisiones del usuario sobre las preguntas de la v1 |
| 2026-10-31 | v1: documento creado | Inicio del proyecto |

---

## 26. Estructura del repositorio

```
paleo-atlas/
├── ALCANCE.md              ← este documento (canónico, ES)
├── SCOPE.md                ← versión EN, al cerrar cada fase
├── README.md / README.es.md
├── LICENSE                 ← AGPL-3.0 (código)
├── LICENSE-CONTENT.md      ← CC BY-NC-SA 4.0 (contenido propio)
├── pyproject.toml / uv.lock / .python-version
├── src/paleo/
│   ├── ingest/             ← F1–F12 (descargas al crudo versionado)
│   ├── parse/              ← wikitext → filas (interim)
│   ├── narrative/          ← hechos, redacción, verificaciones, evaluación, prompts
│   ├── site/               ← generador de web (ES + EN) y comprobador
│   └── cli.py, llm.py, store.py, report.py, names.py…
├── spark/jobs/             ← job de GBIF (Fase 3)
├── dbt/
│   ├── models/{staging,intermediate,marts}/
│   ├── tests/  seeds/  macros/
├── airflow/
│   ├── dags/               ← paleo_steps.py (pasos) + paleo_pipeline.py (DAGs)
│   ├── bin/                ← init-work.sh (clon de `data`), step.py (registro de pasos)
│   ├── tests/              ← carga de los DAGs (job `dags` del CI)
│   ├── Dockerfile, docker-compose.yaml
│   └── work/, logs/        ← locales, fuera de git
├── .github/workflows/
├── site/{templates,static}/
├── benchmarks/             ← Spark vs DuckDB (Fase 3)
├── eval/                   ← fichas de referencia e informes de evaluación
├── ollama/                 ← Modelfiles del LLM local
├── scripts/                ← sembrar los fixtures del CI, huella (fingerprint.py) y paridad Airflow/Actions (parity.py)
├── tests/                  ← pytest (+ fixtures)
├── docs/
│   ├── fases/              ← documento explicativo de cada fase terminada
│   ├── img/                ← capturas (Airflow)
│   ├── adr/
│   └── interview-pack/
└── data/                   ← worktree local de la rama `data` (raw, derived, runs); cache/ e interim/ nunca se versionan
```
