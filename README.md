# Paleo Atlas — data branch

This branch holds the data the [Paleo Atlas](https://github.com/AdayCuestaCorrea/paleo-atlas)
pipeline collects and generates. The code lives on `main`; the daily workflow
(`.github/workflows/pipeline.yml`) checks this branch out as `data/`, updates it
and commits the changes here.

| Folder | What | Source and license |
|---|---|---|
| `raw/wikipedia/` | Revisions of the "*Year* in archosaur paleontology" pages (wikitext) | Wikipedia contributors, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); authors are listed in each page's history (`https://en.wikipedia.org/w/index.php?title=<page>&action=history`) |
| `raw/wikipedia_articles/` | Revisions of the articles about each taxon (EN and ES) | Wikipedia contributors, CC BY-SA 4.0, same attribution |
| `raw/pbdb/` | Taxonomy and occurrences | [Paleobiology Database](https://paleobiodb.org), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `raw/crossref/` | Bibliographic metadata of the studies (no abstracts) | [Crossref](https://www.crossref.org) metadata, public domain ([CC0](https://creativecommons.org/publicdomain/zero/1.0/)) |
| `raw/commons/` | Metadata of the images (author, license, URL; not the images) | Wikimedia Commons; each image keeps its own license, recorded in the file |
| `raw/phylopic/` | Metadata of the silhouettes | [PhyloPic](https://www.phylopic.org); each silhouette keeps its own license |
| `derived/` | Extracted facts and AI-assisted texts with their citations | Original writing based on facts from the sources above (no copied prose), [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) as set out in `LICENSE-CONTENT.md` on `main` |

Each raw file is one dated version (`<source>/<kind>/<key>/<YYYY-MM-DD>.json`),
so the history of every source is kept. Abstracts of studies and quotes taken
from them are never stored here: they stay in the local cache of whoever runs
the pipeline.
