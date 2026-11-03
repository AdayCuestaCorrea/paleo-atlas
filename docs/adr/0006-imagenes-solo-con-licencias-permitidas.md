# D6 — Imágenes y 3D solo con licencias permitidas

- **Estado:** aceptada (2026-10-31, Fase 1)
- **Relacionadas:** [D7](0007-fichas-narrativas-propias-verificadas.md) · [ALCANCE §19](../../ALCANCE.md#19-licencias-atribución-y-ética)

## Contexto
Una ficha sin imagen pierde mucho, y las mejores reconstrucciones suelen salir en prensa con copyright. El repositorio y la web son públicos: una imagen sin permiso es un riesgo legal y ético, y el contenido propio se publica con CC BY-NC-SA 4.0.

## Decisión
- Solo se usan imágenes cuya licencia esté en una **lista de licencias permitidas** (seed `license_allowlist`): dominio público, CC0, CC BY y CC BY-SA.
- Nunca imágenes de prensa ni licencias NC (CC BY-NC), aunque estén «libres». Cada imagen lleva autor, licencia y enlace a su página de origen.
- Si no hay imagen permitida del taxón, se baja de nivel: género, después clado y por último grupo, con siluetas de PhyloPic.

## Alternativas consideradas
- **Imágenes de prensa con «uso justo»:** no aplica en todos los países y no se puede defender en un repo público.
- **Generar ilustraciones con IA:** sin base científica verificable, y confundiría con paleoarte real.
- **Aceptar NC:** choca con la licencia del contenido propio y con un uso futuro no previsto.

## Consecuencias
- **A favor:**
  - todas las fichas tienen imagen;
  - cada imagen es redistribuible y está atribuida.
- **En contra:**
  - menos imágenes espectaculares;
  - parte de las siluetas de PhyloPic son NC y se descartan, y entonces la ficha cae a la del género o el clado (hay una idea en el backlog).

## Pruebas
- [`dbt/seeds/license_allowlist.csv`](../../dbt/seeds/license_allowlist.csv).
- Tests de `fct_taxon_image` en [`_marts__models.yml`](../../dbt/models/marts/_marts__models.yml): `author` y `license` no nulos.
- Tests de `int_image_best_per_taxon` en [`_intermediate__models.yml`](../../dbt/models/intermediate/_intermediate__models.yml): `license_allowed` solo puede ser `true`.
