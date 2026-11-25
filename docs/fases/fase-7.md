# Fase 7 — Calidad de las fichas

> Alcance y casillas: [`ALCANCE.md` §7, Fase 7](../../ALCANCE.md#7-fases-y-entregables). Este documento explica el porqué. Las cifras y los ficheros de cada paso están en [`eval/fichas/README.md`](../../eval/fichas/README.md).
>
> **Estado (2026-11-25): pasos 1 a 6 hechos en `fase-3` y `data-fase-3`, sin publicar.** Falta la publicación en `main` y `data`.

## 1. En una frase

Antes de enseñar la web fuera, se midió cuántos errores tienen los textos y se arreglaron por causa, no ficha a ficha. La medida es un conjunto de 15 fichas famosas revisadas a mano frase a frase. Cada arreglo se aplica a las 4.891 fichas, se mide contra esas 15 y se publica la tasa de error en la página de estado.

## 2. El problema

Las fichas las escribe un modelo de 9B en un ordenador propio, a partir de hechos citados de la Wikipedia y de PBDB. Cada frase ya pasaba comprobaciones (números, nombres, copia literal), pero nadie había medido cuántos errores llegaban al lector. La revisión de 15 fichas famosas (*Tyrannosaurus*, *Triceratops*, *Velociraptor*…) encontró errores visibles en todas: 141 hallazgos, 91 en el texto y 50 en los paneles de datos.

Tres restricciones:

1. **No esperar a que los lectores encuentren los errores.** El usuario lo descartó por deshonesto: se arreglan antes de pedir opiniones.
2. **0 €**: el revisor y las reescrituras corren en la GPU propia, por la noche; Groq no tiene cuota para 2.800 fichas.
3. **Medir, no suponer**: cada arreglo se cuenta contra el mismo conjunto y se publica la cifra, también la que no sale bien.

## 3. Conceptos, desde cero

**Conjunto de evaluación fijo.** `eval/fichas/findings.csv` guarda cada problema con su frase exacta, su causa, su gravedad y la versión correcta. `results.csv` guarda, paso a paso, qué fue de cada uno (`fixed`, `partly`, `mitigated`, `open`). La tasa es el porcentaje de frases con un problema abierto, y cada frase cuenta una vez, con su peor gravedad.

**Arreglar por causa.** Casi todos los errores se repiten por unas pocas causas: el rango de PBDB en la cabecera, el modelo que lee mal la fuente, calcos y cambios de sentido en español, errores heredados de la Wikipedia en español. Una regla para cada causa arregla las 4.891 fichas a la vez.

**Revisor de página.** Un segundo modelo (gpt-oss 20B) lee la ficha entera y marca repeticiones, contradicciones, falta de contexto y frases sobre otra cosa. Las repeticiones se quitan sin modelo; las contradicciones y la falta de contexto vuelven al redactor, que reescribe solo esas frases.

## 4. Cómo funciona aquí

1. **Paneles** (sin LLM): la edad de la cabecera sale del cuadro taxonómico de la Wikipedia en inglés (`paleo ranges`), no de PBDB. Los países solo se confirman con hallazgos de esa edad. Los museos y las especies llevan rótulos honestos.
2. **Comprobaciones del texto** (`paleo recheck-texts`, sin LLM; corre también al final de cada escritura en el pipeline diario):
   - edades que el cuadro descarta y pisos en la parte equivocada de su periodo;
   - alineación inglés–español de clados, periodos y sentidos;
   - reglas fijas en `fix_es`: espécimen, maza caudal, nombres de los pisos según la tabla ICS en español, etc.;
   - textos escritos con hechos antiguos (`stale_texts`).

   La frase que falla se quita; si caen demasiadas, el texto pasa a revisión.
3. **Revisor y reescrituras** (`paleo review pages`, `paleo review rewrite`, en la GPU con `paleo-gpu start`/`stop`): dos rondas como máximo por ficha. La reescritura solo sustituye la ficha si la nueva pasa todas las comprobaciones en los dos idiomas.
4. **Arreglos a mano** de los hallazgos que quedaban en las 15 fichas, con su corrección registrada y los hechos de la ficha.
5. **Transparencia**: la sección «¿Cuánto fiarse?» de la página de estado calcula la tasa en cada build (`status.trust`) y cada ficha tiene el enlace «¿Ves un error?».

## 5. Por qué así

| Decisión | Alternativa | Por qué |
|---|---|---|
| 15 fichas famosas revisadas a mano | Una muestra aleatoria | Son las que más se van a abrir, y en ellas un error se nota más; una muestra aleatoria queda para después |
| Arreglar por causa | Corregir ficha a ficha | 141 hallazgos en 15 fichas son ~45.000 en 4.891; solo una regla llega a todas |
| Revisor de página (gpt-oss 20B) | Revisor frase a frase | En el estudio, el de frase se quedó en 5 de 42 errores con cualquier modelo o prompt; el de página encontró 14 de 42 en 1 minuto para las 15 fichas |
| Reescribir solo las frases marcadas | Reescribir la ficha entera | La reescritura entera arregló 14 problemas y metió 8 nuevos, y a *Archaeopteryx* le quitó 13 frases |
| Dos rondas como máximo | Repetir hasta que no haya marcas | Cada reescritura trae sus propios errores; la segunda ronda ya mezcla mejoras y empeoramientos a partes iguales |
| Tasa calculada en cada build | Escribir la cifra en la plantilla | Así no puede desfasarse de `eval/fichas` ni de los textos del día |

## 6. Cómo se comprueba

- `uv run pytest -q`: 339 tests, entre ellos los de cada regla nueva de `fix_es` y de la alineación, el de `stale_texts` y el de `status.trust` con un conjunto mínimo.
- `paleo recheck-texts` dos veces seguidas: la segunda no cambia nada (las reglas son idempotentes).
- Cada paso, contra las 15 fichas: qué hallazgos desaparecen y cuáles quedan, comprobado a mano («se fue el problema», no «cambió la frase»).
- Muestras a mano de las reescrituras: 18 fichas en la primera ronda y 8 en la segunda.

## 7. Resultados reales (2026-11-25)

**Revisión a ciegas de las 15 fichas** (un agente por ficha, todas las frases en los dos idiomas, sin ver las revisiones anteriores): frases con un problema.

| | Inglés (410) | Español (387) |
|---|---|---|
| Grave | 0,5 % | 0,8 % |
| Grave o medio | 12,9 % | 18,9 % |
| Cualquiera | 28,0 % | 43,2 % |

Es la cifra que publica la página de estado. Después se corrigieron a mano los 216 hallazgos de esas 15 fichas, salvo 9 menores (`eval/fichas/review2/open.csv`).

| | |
|---|---|
| Primera revisión (22 nov.) | 91 hallazgos en el texto y 50 en los paneles; de los del texto, 88 arreglados. No era exhaustiva: anotaba lo que el revisor veía |
| Paneles | 50 hallazgos: 30 arreglados, 8 en parte, 7 atenuados y 5 abiertos (DOI y sinónimos de PBDB, una imagen discutida) |
| Revisor automático, primera ronda | 2.827 fichas; 1.524 frases repetidas quitadas; 974 fichas reescritas enteras y 155 por frases |
| Revisor automático, segunda ronda | 1.129 fichas: las que no tenían problemas pasan de 0 a 211; contradicciones, de 969 a 687; falta de contexto, de 653 a 309 |
| Reglas de español | nombres de pisos (289 fichas), «toneladas métricas» (99) y «millones de años atrás» (954) |

**Muestra al azar de 15 fichas** (la misma revisión): grave 6,9 % EN y 6,8 % ES; grave o medio 25,3 % y 30,6 %. Las frases que solo citaban la Wikipedia en español tenían un error grave en el 17,6 % de los casos, frente al 5,1 % del resto. Desde que se quitan cuando la ficha tiene la inglesa (6.112 frases en 1.466 fichas), la misma revisión da un 3,9 % y un 4,6 %.

## 8. Qué salió mal y qué se aprendió

- **El revisor no encuentra lo que la frase dice fielmente mal.** La mayoría de los errores que quedaban eran fieles a su propio hecho: el hecho ya había leído mal la fuente (*Parasaurolophus* «alcanzó la madurez en un año»). Ningún modelo ni prompt de revisión frase a frase pasó de 5 de 42. *Lección: comprobar una frase contra su cita no comprueba la cita contra la fuente.*
- **Reescribir trae errores nuevos.** La reescritura entera arregló 14 problemas y metió 8; la segunda ronda volvió a meter casi tantas repeticiones como quitó. De ahí reescribir solo las frases marcadas y el tope de dos rondas. *Lección: un arreglo automático se mide también por lo que rompe.*
- **El español de una frase sin cambios se rehacía.** Al reescribir solo unas frases, el adaptador volvía a traducir también las que el modelo devolvía iguales, y salieron «escultura eréctil» y «Las fósiles». Ahora la frase idéntica conserva su español.
- **Una regla nueva quitó frases buenas.** La regla de periodos leía «Paleógeno» frente a «Paleoceno» como otro periodo. Se restauraron los archivos y se añadieron los periodos que abarcan a otros (`_WIDER`). *Lección: pasar la regla por todas las fichas y mirar lo que quita antes de guardarlo.*
- **Una regla no idempotente.** «La etapa valanginiana» solo llegaba a «el piso valanginiense» en la segunda pasada, porque la regla de «etapa → piso» corría antes de corregir el nombre. Se detectó porque una segunda pasada cambió 16 fichas más.
- **Una ficha corta caía por un cambio de una palabra.** La comprobación de «quedan al menos 3 frases» se aplicaba aunque no se quitara ninguna; *Palaeospiza*, con 2 frases, salía de la web por corregir «priabonense».
- **La ficha en español de *Stegosaurus* llevaba dos días sin publicarse.** El modelo escribió «estegosaurio» y «allosauro», y la comprobación de nombres científicos la apartó entera. Nadie lo vio hasta medir las 15 fichas otra vez. *Lección: revisar también lo que no se publica.*
- **Dos revisiones distintas no se comparan.** La tasa «después» de la primera revisión salía 0,2 %, pero solo contaba lo que aquella revisión había anotado. La revisión a ciegas, frase a frase, dio un 12,9 % de frases con un problema grave o medio. *Lección: medir el antes y el después con el mismo instrumento; si no, publicar solo la medida honesta.*
- **Las fichas famosas no representan la web.** La muestra al azar tenía el doble de errores medios y diez veces más graves que las 15 famosas, porque sus artículos de Wikipedia son más cortos y menos revisados. *Lección: medir con una muestra al azar, no con los casos que uno conoce mejor.*
- **Un hecho venía de un documental.** La segunda ronda «arregló» *Incisivosaurus* con una teoría que salía de la serie *Prehistoric Park*, citada en la Wikipedia en español.
- **Los temporizadores de systemd se pierden al reiniciar.** La noche 8 no arrancó; desde entonces se usan unidades guardadas, y `paleo-gpu` para parar al terminar la ficha en curso.

## 9. Preguntas de entrevista

- **¿Cómo sabes cuántos errores tiene tu web?** Por un conjunto fijo de 15 fichas revisadas a mano frase a frase, con cada hallazgo registrado; la tasa se calcula en cada build y se publica, con el aviso de lo que no cuenta.
- **¿Por qué no un LLM que revise cada frase?** Se midió: 5 de 42. La mayoría de los errores son fieles a su cita, así que un revisor que compara frase y cita no los ve.
- **¿Cómo evitas que un arreglo automático empeore las cosas?** Lo paso por todas las fichas, miro lo que quita o cambia y lo mido contra el conjunto; la reescritura solo sustituye una ficha si pasa todas las comprobaciones.
- **¿Qué harías con más presupuesto?** Un modelo mayor para extraer los hechos, que es donde nace la mayoría de los errores que quedan, y una muestra aleatoria además de las fichas famosas.

## 10. Límites y lo que queda

- **La tasa se mide en 15 fichas famosas**, que tienen artículos largos y bien revisados en la Wikipedia; las fichas de géneros poco conocidos no están medidas.
- **Quedan 287 fichas con contradicciones que la reescritura no resolvió** y 26 cuya reescritura falló; siguen publicadas con su texto anterior.
- **Los errores de los hechos** (una lectura mala de la fuente) solo se arreglan a mano o con un extractor mejor.
- **Los paneles de PBDB** conservan 5 problemas abiertos que dependen de los datos de PBDB.
- **La tasa publicada es la de antes de los arreglos a mano.** Las 15 fichas ya no la tienen, pero el resto de la web probablemente sí.
- **Pendiente:** la publicación en `main` y `data`.
