**Español (canónico)** · [English](SCOPE.md)

# ALCANCE — Paleo Atlas

> **Fuente de verdad del proyecto.** Si algo no está aquí, no está en el alcance.
> Cualquier cambio de alcance se apunta en el [Registro de cambios](#25-registro-de-cambios) con fecha y motivo.
> Las ideas nuevas van primero al [Backlog](#24-backlog-de-ideas); solo entran en el alcance cuando se mueven con una entrada en el registro.
> Las casillas `[ ]` se marcan `[x]` al terminar.

**Creado:** 2026-10-31 · **Versión:** 7 · **Estado:** Fase 0 cerrada · Fase 1 empieza el 2026-11-02

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
| dbt | 2 | — | dbt-duckdb: staging → intermediate → marts + **snapshots (SCD2)** para el historial (Fase 1) |
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

El alcance se define en un fichero de datos (`dbt/seeds/scope_clades.csv`), no en el código. **Ampliar = añadir filas al seed + entrada en el registro de cambios.**

| Bloque | Grupos | Ejemplos famosos | Página de Wikipedia anual (verificar nombre exacto) | Fase |
|---|---|---|---|---|
| Arcosaurios | Dinosauria (incl. aves fósiles), Pterosauria, Crocodylomorpha y afines | *Spinosaurus*, *T. rex*, *Quetzalcoatlus*, *Sarcosuchus* | «AAAA in archosaur paleontology» | 1 |
| Reptiles marinos | Ichthyosauromorpha, Sauropterygia (plesiosaurios, pliosaurios, notosaurios, placodontos), Mosasauridae | *Mosasaurus*, *Liopleurodon*, *Ophthalmosaurus* | «AAAA in reptile paleontology» | 3 |
| Peces fósiles | Placodermi, Chondrichthyes fósiles (tiburones), otros peces fósiles destacados | *Dunkleosteus* (placodermo, **pez, no reptil**), *Otodus megalodon* | «AAAA in paleoichthyology» | 3 |

Notas:
- Los mosasaurios son escamosos (parientes de lagartos y serpientes), no arcosaurios. Por eso van en «reptiles marinos» y no en el bloque 1.
- Fuera por ahora (backlog): sinápsidos y mamíferos fósiles (*Dimetrodon*, mamut), invertebrados (trilobites, ammonites), plantas.

---

## 5. Fuentes de datos

> Antes de usar cada fuente: comprobar licencia y condiciones de uso actuales y apuntarlo aquí (columna «Verificado»).

| # | Fuente | Qué aporta | Acceso | Frecuencia | Licencia (a verificar) | Verificado |
|---|---|---|---|---|---|---|
| F1 | Wikipedia — páginas anuales de §4 (año en curso + años anteriores para histórico) | Taxones nuevos: nombre, estatus, autores, edad, unidad geológica, localidad, referencia | API de MediaWiki; nunca scraping del HTML | Diaria (detección de cambios) | Texto CC BY-SA 4.0 (+ GFDL): se usan los hechos, no se copia el texto | [x] 2026-11-01 |
| F2 | PBDB — API `data1.2` | Taxonomía, sinonimias, **opiniones taxonómicas con año y referencia** (historial), rango temporal, ocurrencias | API REST | Diaria (taxones nuevos) + mensual (completo) | CC BY 4.0 (citar PBDB) | [x] 2026-11-01 |
| F3 | GBIF — API de descargas (filtro en servidor) | Especímenes fósiles (`basisOfRecord = FOSSIL_SPECIMEN`) de los grupos de §4: coordenadas, institución, país | API pública gratuita (cuenta de GBIF) | Mensual | Cada descarga tiene DOI y hay que citarla; licencias por registro | [ ] |
| F4 | PhyloPic — API v2 | Siluetas por taxón (si no hay, se usa la del género o el clado) | API REST | Diaria (solo taxones sin imagen) | Por imagen. **Solo PDM, CC0, CC BY 3.0/4.0, CC BY-SA 3.0** (excluidas CC BY-NC y CC BY-NC-SA) | [x] 2026-11-01 |
| F5 | Wikimedia Commons — API | Reconstrucciones y fotos de fósiles | API de MediaWiki | Diaria (solo taxones sin imagen) | Por archivo; Commons no admite licencias solo NC ni ND | [x] 2026-11-01 |
| F6 | Crossref — API REST | Metadatos de cada estudio: tipo (artículo / preprint), revista, ISSN, **retracciones y correcciones** | API pública | Por cada estudio nuevo + revisión mensual | Metadatos de uso libre; los resúmenes (abstracts) pueden tener derechos | [x] 2026-11-01 |
| F7 | ZooBank | Registro oficial del nombre (obligatorio en publicaciones electrónicas según el ICZN) | API / búsqueda pública | Por cada taxón nuevo | A verificar | [ ] |
| F8 | DOAJ | Si la revista de acceso abierto está en el directorio | API pública | Por cada revista nueva | A verificar | [ ] |
| F9 | *(Fase 5)* RSS de medios ES/EN | Noticias: titular, enlace, fecha | RSS | Diaria | Solo titular + enlace + resumen propio | [ ] |
| F10 | *(Fase 6)* Fuentes de modelos 3D (§13): Smithsonian 3D, MorphoSource, Sketchfab, colecciones de museos | Modelos 3D | API o embebido oficial | Curación manual | Por modelo; mismas licencias permitidas que F4 | [ ] |
| F11 | *(Fase 3)* Open Tree of Life — API | Árbol de parentesco sintético (topología), con identificadores cruzados a otras bases | API pública | Mensual | A verificar | [ ] |
| F12 | *(Fase 6)* Conjuntos de datos de tamaño corporal publicados (p. ej. en Dryad) + seed curado a mano | Longitud y masa estimadas, con rango y cita | Descarga + curación | Puntual | Dryad publica en CC0; resto, a verificar por conjunto | [ ] |

### Resultado de la comprobación de licencias (2026-11-01)

| Fuente | Qué dice | Qué hacemos |
|---|---|---|
| **F1 Wikipedia** | Texto bajo CC BY-SA 4.0 (y GFDL). Reutilizar o modificar el texto obliga a atribuir, a indicar los cambios y a publicar con la misma licencia. Las imágenes tienen su propia licencia, archivo por archivo | Solo extraemos hechos (§12.1); el test anti-copia lo garantiza. Citamos el artículo como fuente en la ficha. No usamos imágenes de Wikipedia salvo a través de Commons (F5) |
| **F2 PBDB** | Toda la base de datos bajo **CC BY 4.0** desde 2013; solo exige atribución | Atribución a PBDB en cada ficha y en «Fuentes y licencias». Mientras no encontremos la fórmula de cita oficial de su web, usamos la cita general del proyecto |
| **F4 PhyloPic** | Cuatro grupos de licencias: dominio público (PDM, CC0), atribución (CC BY 3.0/4.0), CompartirIgual (CC BY-SA 3.0) y **no comercial (CC BY-NC 3.0, CC BY-NC-SA 3.0)**, que aún llevan algunas imágenes antiguas. Con CC BY hay que citar al autor con el texto de la página de la imagen y enlazar la licencia | Lista blanca de licencias: PDM, CC0, CC BY 3.0/4.0, CC BY-SA 3.0. **Las NC se descartan** (§19). Comprobar en la Fase 1 qué campos de licencia y autor devuelve la API v2 |
| **F5 Wikimedia Commons** | Licencia por archivo. Commons **no acepta** archivos solo con licencia NC ni con ND. La API (`prop=imageinfo&iiprop=extmetadata`) devuelve `LicenseShortName`, `LicenseUrl`, `Artist`, `Credit`, `AttributionRequired`, `UsageTerms` | Lista blanca por `LicenseShortName` (el campo más fiable). Archivos con varias licencias: revisión manual, porque la API avisa de que esos valores no son fiables |
| **F6 Crossref** | «Casi ningún metadato tiene derechos de autor; se puede usar para cualquier fin». Los resúmenes (abstracts) sí pueden tenerlos. Las retracciones salen en el campo `update-to`, con `source` = `publisher` o `retraction-watch`; filtro `update-type:retraction` | Usamos los metadatos libremente. De los abstracts solo extraemos hechos, nunca se publican. Peticiones con `mailto=` para entrar en el pool «educado» |

**Pendientes de comprobar más adelante:** F3 GBIF (Fase 3), F7 ZooBank, F8 DOAJ, F9 RSS (Fase 5), F10 3D (Fase 6), F11 Open Tree of Life (Fase 3), F12 tamaños (Fase 6).

Fuentes de esta comprobación: [Reusing Wikipedia content](https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content) · [PBDB pasa a CC BY (Creative Commons, 2013)](https://creativecommons.org/2013/12/19/paleobiology-database-now-cc-by/) · [PhyloPic: Usage of Images](https://www.phylopic.org/articles/image-usage) · [Commons:Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing) · [Extension:CommonsMetadata](https://www.mediawiki.org/wiki/Extension:CommonsMetadata) · [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) · [Crossref: Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/) · [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy) · [API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette)

**Reglas comunes de acceso:**
- `User-Agent` con el formato `paleo-atlas-bot/<versión> (<URL del repo>; <correo>) <librería>/<versión>`: Wikimedia exige un User-Agent descriptivo con contacto, que contenga «bot» si es automático, y bloquea sin aviso los genéricos.
- Wikimedia: peticiones **en serie** (nunca en paralelo), agrupar títulos en una sola petición (`titles=A|B|C`), `maxlag`, gzip, GET para lecturas, caché de lo ya descargado.
- Crossref: parámetro `mailto=`.
- Respetar los límites de peticiones; reintentos con backoff exponencial.
- Guardar la respuesta cruda **tal cual** antes de transformar nada.

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
- **D3.** El estado vive en git: respuestas crudas versionadas en la rama `data`; el almacén DuckDB se **reconstruye entero** en cada ejecución → idempotente y auditable.
- **D4.** Comandos independientes del orquestador: Airflow y GitHub Actions solo los llaman.
- **D5.** Spark solo para GBIF, en local, y medido contra DuckDB.
- **D6.** Imágenes y 3D solo con licencias permitidas (§19); nunca de prensa.
- **D7.** Fichas narrativas propias: hechos con fuente → redacción nueva con LLM → verificaciones automáticas. La plantilla es el respaldo si algo falla (§12.1).
- **D8.** Bilingüe desde el principio: los datos no dependen del idioma; solo los textos y las plantillas se duplican.
- **D9.** Historial con snapshots de dbt desde el día 1: lo que no se captura, no se puede reconstruir después.
- **D10.** Detección de cambios barata antes de ejecutar el pipeline completo.

---

## 7. Fases y entregables

Cada fase tiene **criterio de terminado**. No se empieza una fase sin terminar la anterior.

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
- [ ] `ingest wikipedia`: página del año en curso vía API, guardado en crudo
- [ ] Parser de la tabla de taxones (wikitext irregular → filas), con fixtures
- [ ] `ingest pbdb`: datos de cada taxón nuevo
- [ ] `ingest images`: PhyloPic → Commons → silueta del género o clado, con licencia y autor
- [ ] `ingest studies`: Crossref + ZooBank para cada estudio (§10)
- [ ] dbt-duckdb: staging, intermediate y marts de §8
- [ ] **dbt snapshots** de taxón y estudio desde la primera ejecución (§9)
- [ ] Elegir LLM con plan gratuito (A18)
- [ ] Extracción de hechos con fuente (Wikipedia ES/EN, PBDB, metadatos de estudios) para las especies nuevas
- [ ] Redacción narrativa ES + EN a partir de los hechos (§12.1)
- [ ] Verificaciones: fidelidad, anti-copia, cita por frase (§16) + revisión manual de una muestra
- [ ] Tests dbt y pytest de §16
- [ ] Web ES + EN: portada con selector de idioma, «Última hora», ficha de taxón con historial, recap semanal, «Cómo evaluamos las fuentes», «Fuentes y licencias»
- [ ] CI: tests en cada push/PR
- [ ] Ejecución programada diaria con detección de cambios + recap semanal (§15)
- [ ] Informe de ejecución por cada run
- [ ] Web publicada en GitHub Pages

**Terminado cuando:** la web pública muestra las especies de arcosaurios de 2026 en los dos idiomas, con ficha narrativa verificada, imagen (o la del grupo), señales de fiabilidad e historial, y se ha actualizado sola **2 semanas seguidas** sin intervención.

### Fase 2 — Airflow
- [ ] `docker compose` con Airflow
- [ ] DAG diario y DAG semanal (recap), que llaman a los mismos comandos que Actions
- [ ] DAG mensual (provisional hasta la Fase 3)
- [ ] Capturas para el README (DAG, ejecución correcta, reintento)

**Terminado cuando:** los DAGs producen exactamente el mismo resultado que los workflows de Actions.

### Fase 3 — Enciclopedia, ampliación y Spark
- [ ] Ingesta completa desde PBDB de todos los grupos de §4 (no solo taxones nuevos)
- [ ] Ampliación del seed de alcance: reptiles marinos y peces fósiles (§4)
- [ ] Reconstruir el historial hacia atrás: opiniones taxonómicas de PBDB + páginas anuales de Wikipedia de años anteriores (§9)
- [ ] Descarga filtrada de GBIF (F3) y su DOI en la página de fuentes
- [ ] Job PySpark local: reconciliación de nombres con PBDB (sinónimos, erratas, rango) + agregados
- [ ] Mismo trabajo en DuckDB → **benchmark** (tiempo, memoria, complejidad del código)
- [ ] *Opcional:* mismo job en Databricks Free Edition (verificar cuotas y acceso a datos externos)
- [ ] Web: fichas de enciclopedia con mapa de hallazgos, museos y línea temporal
- [ ] Índices por grupo, época y país
- [ ] Familia y clasificación completa en cada ficha (PBDB)
- [ ] Fichas narrativas para toda la enciclopedia (§12.1), por lotes dentro del plan gratuito del LLM
- [ ] Árbol de parentesco con escala temporal (§11.2): topología de Open Tree of Life (F11) o, si falta, clasificación de PBDB; rangos temporales de PBDB
- [ ] DAG mensual real en Airflow

**Terminado cuando:** la enciclopedia de los tres bloques de §4 está publicada y el benchmark está documentado con cifras reales.

### Fase 4 — Portfolio
- [ ] README bilingüe completo (§20)
- [ ] ADRs D1–D10
- [ ] Interview pack: one-pager, vídeo de 2 min, postmortem
- [ ] Entrada en `cv.md` vía modo `add` de career-ops, con métricas reales de §17
- [ ] Enlace en LinkedIn y en el perfil de GitHub

**Terminado cuando:** el proyecto aparece en el CV con URL y métricas verificables.

### Fase 5 — IA y noticias
- [ ] Ingesta RSS (F9)
- [ ] Clasificación de noticias (especie nueva / revisión / fósil nuevo / ruido): baseline clásico vs LLM, con métricas
- [ ] Extracción del taxón mencionado y enlace a su ficha
- [ ] Deduplicación de la misma noticia entre medios (embeddings)
- [ ] Glosario bilingüe con explicaciones emergentes en las fichas (§12)

**Terminado cuando:** las métricas de clasificación de noticias están publicadas en el README y el glosario está revisado y en las fichas.

### Fase 6 — Extras
- [ ] Modelos 3D curados (§13)
- [ ] Comparador de tamaños (§11.3)

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
| Imagen | URL, tipo (silueta / reconstrucción / fósil), licencia, autor, nivel (especie / género / clado) |
| Modelo 3D | URL, tipo (escaneo / reconstrucción), año, autor, licencia (§13) |
| Tamaño corporal | Longitud y/o masa estimada (mín.–máx.), método, cita (§11.3) |
| Objeto de referencia | Humano, elefante, autobús, avión…: medidas con fuente (§11.3) |
| Hecho | Afirmación atómica sobre un taxón, con fuente, cita y fragmento de origen (§12.1) |
| Texto de ficha | Secciones redactadas por idioma, frases enlazadas a sus hechos, estado de verificación |
| Término del glosario | Término, definición ES, definición EN, estado de revisión (§12) |

### Capas (nombres orientativos)
- **seeds:** `scope_clades`, `trusted_journals`, `contested_topics`, `models_3d`, `glossary`, `body_sizes`, `reference_objects`
- **staging:** `stg_wikipedia__new_taxa`, `stg_wikipedia__articles`, `stg_pbdb__taxa`, `stg_pbdb__opinions`, `stg_pbdb__occurrences`, `stg_gbif__fossil_specimens`, `stg_phylopic__images`, `stg_commons__images`, `stg_crossref__works`, `stg_zoobank__names`, `stg_otol__tree`, `stg_body_sizes`
- **snapshots:** `snap_taxon`, `snap_study`
- **intermediate:** `int_taxon_name_resolution`, `int_taxon_enriched`, `int_image_best_per_taxon`, `int_study_reliability`, `int_taxon_events`, `int_taxon_facts`
- **marts:** `dim_taxon`, `dim_taxon_tree` (padre-hijo + rango temporal), `dim_study`, `dim_institution`, `dim_geologic_interval`, `fct_taxon_event`, `fct_taxon_text` (texto verificado por idioma), `fct_specimens_by_taxon`, `fct_weekly_recap`, `fct_run_summary`

---

## 9. Historial de cambios por taxón

Cada ficha tiene una **línea temporal** con todo lo que se sabe del taxón. Cuando una novedad afecta a un taxón ya conocido (por ejemplo, un estudio nuevo sobre *Spinosaurus*), la entrada en «Última hora» enlaza a esa línea temporal.

**Tipos de evento:** descripción original · reasignación de género o nueva combinación · sinonimia · *nomen dubium* · espécimen nuevo · nueva hipótesis (ecología, aspecto, tamaño) · corrección o retracción del estudio.

**De dónde sale:**
| Origen | Cubre | Fase |
|---|---|---|
| Snapshots de dbt sobre nuestras propias ingestas (SCD tipo 2) | Todo cambio desde que arranca el proyecto | 1 |
| Opiniones taxonómicas de PBDB (cada opinión trae año y referencia) | Historia taxonómica completa hacia atrás | 3 |
| Páginas anuales de Wikipedia de años anteriores | Descripciones de años pasados | 3 |
| Noticias clasificadas | Hipótesis nuevas y debates | 5 |

**Debates abiertos:** cuando haya estudios que se contradicen (p. ej., si *Spinosaurus* era cazador acuático o vadeador), el evento se marca **«En debate»** y enlaza a los estudios de cada postura. Se curan a mano en el seed `contested_topics`.

---

## 10. Verificación de estudios

No juzgamos la ciencia: **mostramos señales verificables** y explicamos qué significan.

| Señal | Cómo se comprueba | Distintivo en la web |
|---|---|---|
| Revisado por pares | Crossref: tipo `journal-article` en revista con ISSN | 🟢 Revisado por pares |
| Preprint | Crossref: tipo `posted-content`, o servidor de preprints (bioRxiv, PaleorXiv…) | 🟡 Preprint (sin revisar todavía) |
| Retractado o corregido | Crossref (incluye los datos de Retraction Watch) | 🔴 Retractado / 🟠 Corregido |
| Nombre registrado | ZooBank | ✔ Registrado en ZooBank |
| Revista de acceso abierto en DOAJ | DOAJ | Señal secundaria |
| Revista en la lista de confianza | Seed `trusted_journals` (curado a mano: Nature, Science, JVP, Cretaceous Research, PeerJ, Papers in Palaeontology, Acta Palaeontologica Polonica…) | Señal secundaria |
| Recogido en PBDB | PBDB | Señal secundaria |

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

### 11.1 Contenido de la ficha
| Campo | Fuente | Si falta |
|---|---|---|
| Nombre científico y significado | F1 / PBDB | Ocultar el significado |
| Imagen 2D + autor + licencia | F4 / F5 | Silueta del género o clado, con aviso «imagen aproximada» |
| Modelo 3D *(Fase 6)* | F10 | Ocultar |
| Familia y clasificación (familia → orden → clase) | PBDB | El nivel más bajo conocido |
| Grupo (clado) y bloque | PBDB / seed | Clado de F1 |
| Época y edad (Ma) | PBDB / F1 | «Desconocida» |
| Lugar del hallazgo | F1 / PBDB | Ocultar |
| Tamaño (rango + cita) y botón «Comparar» *(Fase 6)* | F12 / seed `body_sizes` (§11.3). **No se inventa** | Ocultar |
| Árbol de parentesco *(Fase 3)* | §11.2 | Solo la clasificación en texto |
| **Texto narrativo** por secciones: Descripción, Descubrimiento, Paleobiología, Clasificación, Época y hábitat, Debates; cada frase con su cita | §12.1 | Texto de la plantilla (§11.4) |
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
- **Honestidad:** la topología sale de Open Tree of Life (síntesis de muchos estudios) o, si falta, de la clasificación de PBDB, que es una clasificación y no un análisis filogenético. Se indica el origen en la propia vista, y que la ubicación de muchos animales está en debate.

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
5. **Revisión manual** de una muestra; se publica el % que pasa cada verificación (§17).

**Reglas:**
- Si una ficha no pasa las verificaciones, se publica el texto de respaldo (§11.4) y se marca para revisión.
- Se generan **una vez por cambio** de los hechos (no en cada visita) y se guardan en el repo → caben en un plan gratuito.
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
| `paleo check` | ¿Ha cambiado alguna fuente desde la última ejecución? (código de salida) | Sí |
| `paleo ingest wikipedia --year AAAA` | Descarga y guarda en crudo | Sí |
| `paleo ingest pbdb` | Datos PBDB de los taxones pendientes | Sí |
| `paleo ingest images` | Imagen para taxones sin imagen | Sí |
| `paleo ingest studies` | Crossref + ZooBank + DOAJ | Sí |
| `paleo gbif extract` *(Fase 3)* | Descarga filtrada + job Spark/DuckDB | Sí |
| `paleo build` | `dbt snapshot` + `dbt build` | Sí (reconstrucción completa; los snapshots acumulan historia) |
| `paleo site` | Genera la web ES + EN | Sí |
| `paleo recap --week AAAA-Www` | Genera el recap de esa semana | Sí |
| `paleo report` | Informe de ejecución | Sí |

Requisitos: códigos de salida fiables (0 = OK), logs estructurados, sin estado oculto fuera de git y de `data/`.

---

## 15. Orquestación y frescura

Con una web estática no hay tiempo real al minuto, pero sí **en horas**, gratis:

| Qué | Dónde | Cuándo |
|---|---|---|
| Tests (pytest + dbt) | GitHub Actions | Cada push y PR |
| Detección de cambios + pipeline si hay novedades | GitHub Actions (cron) | Diario (o cada 6 h si se ve útil, A6) |
| Recap semanal | GitHub Actions (cron) | Lunes por la mañana, hora de Canarias (A6) |
| Pipeline mensual (GBIF, revisión de retracciones) | Local (Spark en mi máquina) | Mensual |
| Demostración | Airflow en Docker (local) | Bajo demanda |

- Detección barata: comparar el número de revisión de las páginas de Wikipedia y el contenido de RSS/PBDB con lo guardado. Si no hay cambios, no se ejecuta nada más.
- Fallo del pipeline → aviso por correo de GitHub; la web anterior se queda publicada (nunca se publica una web rota).
- Los cron de GitHub no son puntuales (pueden retrasarse).
- **A verificar:** GitHub desactiva los workflows programados de repos públicos tras 60 días sin actividad. Comprobar si los commits del pipeline cuentan como actividad.

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
- Fichas narrativas: fidelidad (nombres, números y fechas presentes en los hechos), anti-copia (ninguna secuencia de N o más palabras igual a la fuente; N a fijar en la Fase 1), al menos una cita por frase, todo hecho con fragmento de origen.
- Paridad de idiomas: toda página en ES existe en EN y viceversa.

### Tests de Python
- Parser de las tablas de Wikipedia con casos reales guardados (fixtures).
- Reconciliación de nombres con casos conocidos (sinónimos, erratas).
- Verificadores de fidelidad y anti-copia, con casos buenos y malos guardados (Fase 1).

### Informe de ejecución (por cada run)
Fuentes con cambios, taxones nuevos / actualizados, eventos nuevos, % con correspondencia PBDB, % con imagen por nivel, avisos y errores de tests, duración por paso.

---

## 17. Métricas del proyecto (para CV y entrevistas)

Se rellenan con datos reales; **nunca se estiman en el CV**.

| Métrica | Valor | Fecha |
|---|---|---|
| Taxones nuevos de 2026 recogidos / total de las páginas de Wikipedia | — | — |
| Taxones en la enciclopedia por bloque | — | — |
| Eventos en el historial | — | — |
| % con correspondencia en PBDB | — | — |
| % con imagen (especie / género / clado) | — | — |
| % de estudios revisados por pares / preprints / retractados | — | — |
| Retraso medio publicación → web (horas) | — | — |
| Semanas seguidas sin intervención manual | — | — |
| Nº de tests (pytest + dbt) | — | — |
| Duración del pipeline diario | — | — |
| Coste mensual | 0 € | — |
| GBIF: especímenes fósiles procesados | — | — |
| Benchmark Spark vs DuckDB: tiempo, memoria | — | — |
| Clasificador de noticias: precisión / recall (baseline vs LLM) | — | — |
| Fichas narrativas que pasan fidelidad / anti-copia / cita por frase (%) | — | — |
| Hechos extraídos que pasan la comprobación (%) | — | — |

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
| LLM (desde la Fase 1) | Plan gratuito (A18); si se agota, las fichas esperan con el texto de respaldo |
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
| A15 | Explicador conversacional | **Descartado**; se queda el glosario (§12.2) | 2026-11-01 |

### Abiertas
| # | Decisión | Opciones | Cuándo |
|---|---|---|---|
| A18 | LLM para fichas (plan gratuito, ES + EN, cuota suficiente) | A comparar | Fase 1, antes de la semana 3 |
| A6 | Frecuencia de detección y hora del recap | Diario / cada 6 h; lunes 06:00 Canarias | Fase 1 |
| A7 | Semanas de tolerancia al retraso de PBDB (N) | 4, 8, 12 | Fase 1 |
| A8 | Versión de Airflow | 2.x, 3.x | Fase 2 |
| A11 | Dónde se guarda el extracto de GBIF | Rama `data`, GitHub Releases | Fase 3 |
| A14 | ¿Hacer la Fase 6? | Sí / no / solo 3D / solo comparador | Después de Fase 5 |
| A16 | Lista inicial de revistas de confianza | Seed `trusted_journals` | Fase 1 |

---

## 23. Calendario

A ratos y fines de semana, **sin frenar candidaturas**. Fechas orientativas; las Fases 5 y 6 se fechan al terminar la 4.

| Semana | Fechas | Fase |
|---|---|---|
| 1 | 2026-11-02 → 11-08 | Fase 1 (ingesta Wikipedia, parser, dbt staging) |
| 2 | 11-09 → 11-15 | Fase 1 (PBDB, imágenes, estudios, snapshots) |
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
| Buscador en la web | Hay buscadores para webs estáticas que funcionan sin servidor |
| Mapa paleogeográfico (dónde estaban los continentes en esa época) | Existen servicios de reconstrucción de placas; a investigar |
| Newsletter semanal por correo con el recap | Necesita un servicio de envío gratuito |
| Más grupos: sinápsidos y mamíferos, invertebrados, plantas | Ampliar el seed de §4 |
| API pública de datos de Paleo Atlas | Revisar las licencias de redistribución |

---

## 25. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
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
│   ├── ingest/             ← F1–F12
│   ├── enrich/             ← reconciliación de nombres, imágenes, fiabilidad
│   └── site/               ← generador de web (ES + EN)
├── spark/jobs/             ← job de GBIF (Fase 3)
├── dbt/
│   ├── models/{staging,intermediate,marts}/
│   ├── snapshots/          ← historial (§9)
│   ├── tests/  seeds/  macros/
├── airflow/dags/
├── .github/workflows/
├── site/{templates,static}/
├── benchmarks/             ← Spark vs DuckDB
├── tests/                  ← pytest
├── docs/
│   ├── adr/
│   └── interview-pack/
└── data/                   ← local, ignorado por git (lo versionado va a la rama `data`)
```
