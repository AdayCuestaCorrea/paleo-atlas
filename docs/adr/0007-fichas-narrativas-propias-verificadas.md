# D7 — Fichas narrativas propias: hechos con fuente, LLM y verificaciones

- **Estado:** aceptada (2026-11-01, A17); revisada el 2026-11-02 (A18, modelos) y el 2026-11-03 (lotes con la GPU local)
- **Relacionadas:** [D6](0006-imagenes-solo-con-licencias-permitidas.md), [D8](0008-bilingue-desde-el-principio.md) · [ALCANCE §12](../../ALCANCE.md#12-ia-fichas-narrativas-y-glosario) · [§16](../../ALCANCE.md#16-calidad-de-datos-y-observabilidad)

## Contexto
Cada ficha necesita un texto divulgativo en dos idiomas. Copiar Wikipedia no es contenido propio, y su licencia CC BY-SA obligaría a todo el sitio. Un LLM que escribe «de memoria» inventa. Todo con 0 €.

## Decisión
Un proceso en tres pasos, donde **ningún modelo juzga a otro**:
1. **Hechos con cita:** el LLM extrae hechos de las fuentes. Cada hecho lleva una cita literal que tiene que aparecer en su fuente.
2. **Redacción nueva:** el LLM escribe el texto en inglés **solo a partir de esos hechos**. Después lo adapta al español y lo revisa.
3. **Verificaciones deterministas** (lógica de cadenas de texto, explicable y reproducible):
   - los números de cada hecho están en su cita;
   - cada frase cita al menos un hecho;
   - los números y los nombres de una frase salen de los hechos que cita;
   - ninguna secuencia de **8 palabras** está copiada de una fuente.

Si algo falla, la ficha muestra un **texto de respaldo** generado con una plantilla a partir de los datos.

## Alternativas consideradas
- **Mostrar el extracto de Wikipedia:** no es contenido propio y arrastra la licencia.
- **LLM sin fuentes:** alucina, y no se puede citar.
- **Un LLM juez:** otro modelo que puede equivocarse, y sus fallos no se pueden explicar.

## Consecuencias
- **A favor:**
  - cada frase publicada enlaza a sus fuentes;
  - el texto es nuevo;
  - un fallo tiene un motivo concreto.
- **En contra:**
  - las verificaciones garantizan la fidelidad, pero no el buen estilo: en español se cuelan calcos que hay que corregir en los prompts después de leer una muestra;
  - cambiar un prompt obliga a reescribir (la versión del prompt forma parte de la clave de frescura).

## Revisión (2026-11-02 y 2026-11-03)
- **Modelos (A18):** Groq `gpt-oss-120b` para la ejecución diaria, con 12 de 12 fichas de referencia verificadas en EN y ES; Qwen 3.5 9B local para lotes grandes.
- **Géneros (Fase 3):** se redactan en lotes nocturnos con la GPU local: reanudables, con hora de parada y caché por contenido. Primer lote: verificados el 90 % en EN y el 72 % en ES.

## Pruebas
- [`src/paleo/narrative/checks.py`](../../src/paleo/narrative/checks.py): las reglas, con `N_GRAM = 8`.
- Prompts versionados en [`src/paleo/narrative/prompts/`](../../src/paleo/narrative/prompts/); el texto de respaldo, en [`src/paleo/site/fallback.py`](../../src/paleo/site/fallback.py).
