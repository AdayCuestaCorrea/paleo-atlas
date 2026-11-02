# Spark frente a DuckDB: el job de reconciliación de GBIF, medido

El mismo trabajo (`paleo.gbif_job.spec`) con dos motores, sobre los mismos datos y en la misma
máquina. Se trata de reconciliar los nombres de los especímenes fósiles de GBIF con los géneros
del catálogo de PBDB (exacto → sinónimo → errata) y agregarlos por género, institución y país.

- **Datos:** la descarga de GBIF
  [`0023284-261023074918325`](https://doi.org/10.15468/dl.8v87yz) (2026-11-02). Contiene
  932.494 especímenes fósiles de cordados, sin mamíferos ni tortugas, y ocupa 46 MB en
  `SIMPLE_PARQUET`. Se cruza con 4.787 géneros de PBDB.
- **Implementaciones:**
  - `src/paleo/gbif_job/duckdb_job.py`, en SQL de DuckDB;
  - `spark/jobs/gbif_reconcile.py`, con la API de DataFrames de PySpark en modo local
    (`local[*]`, tantas particiones de *shuffle* como núcleos y la interfaz web desactivada).
- **Igualdad:** los cuatro extractos (`genus_specimens`, `institutions`, `countries`,
  `unmatched`) son idénticos fila a fila con los datos reales. Sus huellas SHA-256 coinciden.
  Con el fixture pequeño, lo comprueba `tests/test_gbif_job.py`.
- **Máquina:**
  - AMD Ryzen 7 9800X3D (8 núcleos / 16 hilos) y 30,5 GB de RAM;
  - CachyOS, Python 3.14.10, DuckDB 2.0.0, PySpark 4.2.0 y OpenJDK 21.0.12.
- **Método:** `uv run --group spark python benchmarks/gbif/run.py 0023284-261023074918325`.
  - Se usan tres tamaños, el 10, el 50 y el 100 % de la descarga. Las filas se eligen por el
    hash de `gbifid`, así que los dos motores leen las mismas.
  - Cada caso se ejecuta 3 veces, siempre en un proceso nuevo, y se toma la mediana.
  - La memoria es el pico de RSS de todo el árbol de procesos (Python más la JVM de Spark),
    muestreado en `/proc` cada 0,2 s.
  - Las cifras completas están en [`results.json`](results.json).

## Resultados

| Filas | Motor | Tiempo (mediana) | Repeticiones | Memoria máx. | Filas/s |
|---:|---|---:|---|---:|---:|
| 93.004 | DuckDB | **0,48 s** | 0,49 · 0,48 · 0,48 | **212 MB** | 194.000 |
| 93.004 | Spark | 8,20 s | 8,20 · 8,19 · 8,70 | 1.387 MB | 11.300 |
| 466.042 | DuckDB | **0,68 s** | 0,68 · 0,67 · 0,68 | **286 MB** | 685.000 |
| 466.042 | Spark | 10,20 s | 10,20 · 10,21 · 10,20 | 1.735 MB | 45.700 |
| 932.494 | DuckDB | **0,86 s** | 0,86 · 0,86 · 0,84 | **459 MB** | 1.084.000 |
| 932.494 | Spark | 13,71 s | 13,71 · 13,71 · 13,20 | 1.504 MB | 68.000 |

Líneas de código, sin contar los comentarios ni los docstrings: **DuckDB 124** y
**Spark 242**.

## Lectura

- **DuckDB es de 15 a 17 veces más rápido y usa de 3 a 6 veces menos memoria con todos los
  tamaños.** Con menos de un millón de filas que caben en la RAM de un portátil, no hay nada
  que repartir: el job entero de DuckDB dura menos que el arranque de Spark.
- **Casi todo el tiempo de Spark es coste fijo.** Al extrapolar las tres medidas a 0 filas
  quedan unos 7,5 s, que se van en arrancar la JVM, crear la sesión y planificar unas 120
  etapas.
- **El coste marginal también favorece a DuckDB.** Pasar de 93.000 a 932.000 filas suma unos
  5,5 s a Spark y unos 0,4 s a DuckDB, así que la diferencia no se cierra al crecer los datos
  en este rango.
- **La memoria de Spark es sobre todo la JVM**, que reserva entre 1,4 y 1,7 GB sin depender
  apenas del tamaño. Que el caso del 50 % gaste más que el del 100 % es ruido del recolector
  de basura.
- **La complejidad es el doble.** El SQL de DuckDB se lee de arriba abajo. En Spark, la misma
  lógica necesita *anti-joins* explícitos, `eqNullSafe` para las claves que pueden ser nulas,
  `sort_array` sobre estructuras para ordenar listas y un `coalesce(1)` para escribir un único
  archivo.

## Conclusión

**Para este volumen, el motor adecuado es DuckDB.** Es el motor por defecto de
`paleo gbif reconcile`. El DAG mensual de Airflow ejecuta a propósito la variante de Spark,
para que el job de Spark funcione de verdad dentro del orquestador (en una imagen con Java y
en una ejecución de verdad). Esa elección cuesta unos 13 s una vez al mes, y las huellas
garantizan que el resultado es el mismo con los dos motores.

Spark tiene sentido cuando los datos no caben en una máquina o ya viven en un clúster o un
*lakehouse*: decenas o cientos de millones de filas, varios nodos, o almacenamiento en
S3/ADLS con Delta. En esos casos, sus 7 s de arranque dejan de importar. Este benchmark mide la
otra cara de la decisión: el precio de usar Spark cuando no hace falta.

Lo que queda abierto:
- **Medir tamaños sintéticos de 5 y 10 veces** (la descarga replicada, bien marcada como
  sintética), para ver si en una sola máquina la diferencia llega a cerrarse;
- **probar con Databricks Free Edition**, que es opcional según ALCANCE §7.
