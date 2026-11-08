[English](postmortem.md) · **Español**

# Paleo Atlas — postmortem

Del 2026-10-31 (primera versión del alcance) al 2026-11-08 (Fases 1, 2, 3, 5 y 6 publicadas). El detalle de cada fallo está en el apartado «Qué salió mal» de cada [documento de fase](../fases/README.md); aquí va lo que se repite entre fases.

## Qué funcionó

- **El estado en git y el almacén desde cero.** Cada respuesta de una fuente se guarda como JSON versionado y el almacén se reconstruye entero en cada ejecución. Gracias a eso, el historial (SCD tipo 2) sale en SQL de las versiones, cualquier día se puede repetir y fusionar dos ramas de datos se reduce a un script (`scripts/merge_data.py`) que une por clave.
- **Comandos, no código del orquestador.** Actions y los DAGs de Airflow llaman a los mismos comandos `paleo`. La comprobación de paridad dio 0 diferencias en 33 tablas y 97 archivos de la web.
- **Medir antes de decidir.** Spark frente a DuckDB se decidió con un benchmark (mismo job, salida idéntica fila a fila: DuckDB 0,86 s frente a 13,7 s). La deduplicación de noticias, con 47 pares etiquetados (juez LLM F1 1,00 frente a 0,29 de TF-IDF). El modelo de las fichas, con 12 fichas de referencia y 4 configuraciones.
- **Comprobaciones automáticas y una muestra humana.** El LLM nunca publica sin pasar las comprobaciones (cita por frase, cifras, nombres, anti-copia), y cada resultado nuevo (glosario, tamaños) se publica con el acierto de una muestra de 20 revisada a mano: 19 de 20 en los dos casos.
- **Maquetas con datos reales antes de implementar.** La portada, la ficha, la página de estado, las noticias, el comparador y la paleta se eligieron entre 3 o 4 maquetas hechas con los datos de verdad. Así salieron problemas que una maqueta con texto de relleno esconde: una ficha de 6,7 pantallas, imágenes de 960 px en miniaturas o un contraste que no llegaba a AA.
- **La regla de 0 €** obligó a diseñar para las cuotas: caché por contenido (una llamada repetida no gasta cuota), lotes que se pueden reanudar y la GPU local para el volumen. El coste mensual es 0 €.

## Qué no funcionó

- **Datos privados en el primer commit.** El 2026-11-01 se coló en el repo público información privada que no debía estar, y la única forma limpia de quitarla de la historia fue borrar el repo y crearlo de nuevo. Desde entonces, un hook `pre-push` local busca una lista de términos en los archivos y en los mensajes de commit, y nunca se salta.
- **El cron de GitHub no es una hora.** El de las 06:00 UTC no se lanzó; el de las 06:23 se lanza entre 7 y 8,5 h tarde. No importa para una web que cambia una vez al día, pero hubo que añadir un cron de reserva, un test de frescura y la fecha del build en el pie para que un fallo se viera.
- **Los lotes nocturnos dependen del PC.** Un lote se paró en la 7.ª especie por un JSON cortado; otro se cortó a las 06:21 porque el PC se suspendió (227 géneros hechos). Lo primero se arregló con reintentos y saltando el elemento malo; lo segundo sigue pendiente (`systemd-inhibit` en el script del lote).
- **Las comprobaciones demasiado literales escondían los fallos de verdad.** En un lote fallaron 56 de 214 fichas en español, la mayoría por reglas tontas: «Manu» dentro de *manual*, «siglo XIX» como cifra perdida, un clado escrito en español. Con las reglas arregladas se rescataron 43 sin volver a llamar al modelo.
- **Mirar solo lo que cambia.** Las siluetas del comparador se revisaron a ojo en varias vueltas, pero cada vuelta miraba las siluetas que cambiaban. El *Giganotosaurus* salió con la de un *Monolophosaurus* y, después, el *T. rex* con la de «Tyrannosaurus magnus». Los dos los vio el usuario en la web publicada. Al final se hizo una consulta que mira todas: siluetas cuyo nodo no es la ficha ni una de sus especies.
- **Etiquetar con la propuesta del modelo a la vista.** 294 de 300 titulares mantuvieron la etiqueta del LLM: eso es anclaje, no acierto. Hubo que hacer una muestra a ciegas de 50 (74 % del LLM; la persona consigo misma, 84 %) y publicar las dos cifras con su significado.
- **Los LLM pequeños escriben calcos en español** («superdepredador», «Hacia 1875») que ninguna comprobación automática detecta. Se encontraron leyendo, y se corrigieron con reglas en los prompts.
- **La caché del navegador engaña al revisar.** Varias veces un arreglo «no funcionaba» porque Chrome servía el CSS o el JavaScript viejo del servidor local.

## Qué cambiaría

1. **Una lista de comprobación antes del primer push** a un repo público, con el hook de términos instalado desde el primer commit, no después del susto.
2. **Decidir cómo se etiqueta antes de enseñar la propuesta del modelo.** Una muestra a ciegas desde el principio, y la propuesta solo para ir más rápido en el resto.
3. **Convertir en test cada consulta de revisión.** La de las siluetas, la de los extremos de tamaño (los 10 primeros y los 10 últimos encontraron 0 m, 1 mm y un récord de 58 m) o la de los enlaces a Wikipedia de especies con ficha de género se hicieron a mano una vez; como tests de dbt, avisarían solas la próxima vez.
4. **Ensayar con los datos reales y en las condiciones del runner desde el principio.** El ensayo del merge de la Fase 3 destapó dos fallos que el fixture no veía: un PDF en la tabla de Wikipedia que tumbaba la ingesta de imágenes y un modelo que podía agotar la memoria (ahora 0,3 s en vez de ~4 s, con el mismo resultado fila a fila).
5. **Los lotes largos, como servicio con inhibición del reposo** desde el primer día, y los logs fuera de `/tmp` desde el principio (el primero estaba allí, y `/tmp` se borra al apagar el PC, justo lo que hace el lote al acabar).
6. **Menos alcance a la vez.** El alcance pasó por 45 versiones en 9 días. El registro de cambios de `ALCANCE.md` lo hizo manejable, pero empezar la Fase 5 sin cerrar la 1 y la 3 dejó casillas abiertas en tres fases a la vez.
