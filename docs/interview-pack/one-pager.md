**English** · [Español](one-pager.es.md)

# Paleo Atlas — one-page summary

**A paleontology encyclopedia in Spanish and English that rebuilds itself every day from open scientific data, at no cost.**
Website: https://adaycuestacorrea.github.io/paleo-atlas/ · Code: https://github.com/AdayCuestaCorrea/paleo-atlas

## The product

- **4,890 pages** on archosaurs (dinosaurs, birds, pterosaurs, crocodile relatives), marine reptiles and fossil fishes, in two languages: more than 10,000 web pages.
- **Up to date:** every day it queries its sources, each at its own rhythm (Wikipedia daily; the Paleobiology Database, Crossref, Commons and PhyloPic weekly or monthly; GBIF monthly). If something changed, it rebuilds the warehouse and publishes again.
- **With a history:** 19,541 events (descriptions, synonymies, genus changes…) since 1758 and 8,195 studies; those tracked since 2026 carry their reliability signals (peer review, preprint, retraction).
- **Texts that cite every sentence:** an LLM writes from facts extracted with their source, and only what passes the automatic checks is published.
- **Transparent:** a public [Data status](https://adaycuestacorrea.github.io/paleo-atlas/en/status.html) page shows every run, the tests and the freshness of each source.

## The architecture

```
open sources → paleo ingest → raw store versioned in git → dbt + DuckDB → static site (Jinja2) → GitHub Pages
                                                      ↑ LLM: facts → EN text → ES + checks
                                  GBIF (monthly) → name reconciliation in DuckDB and in PySpark
```

- **The state lives in git**: every source response is stored as versioned JSON, and the warehouse is rebuilt from scratch on every run. Any day can be reproduced, and the history (SCD type 2) is derived in SQL from those versions.
- **Commands, not orchestrator code**: GitHub Actions runs the same `paleo` commands every day as the Airflow 3.3 DAGs, and both were shown to give the same result.
- **Spark only where it was measured**: the reconciliation of 932,494 GBIF specimens is written in DuckDB and in PySpark, with identical output. DuckDB is 15–17× faster at this volume, so the daily layer stays on DuckDB.

**Stack:** Python 3.14 · dbt · DuckDB · PySpark · Airflow · GitHub Actions · Ollama (Qwen 3.5 9B, local GPU) · Groq · Jinja2 · framework-free JavaScript · pytest.

## The figures (measured on 2026-11-08)

| | |
|---|---|
| Tests | 265 pytest · 170 dbt tests on every run (163 data tests, 7 unit tests) |
| GBIF ↔ PBDB reconciliation | 138,388 specimens matched to their genus: exact, by synonym or by typo |
| Benchmark, 932,494 rows | DuckDB 0.86 s and 459 MB · Spark 13.7 s and 1.5 GB |
| Verified narrative pages | 598 in English and 582 in Spanish (growing every night on the local GPU) |
| Glossary | 163 terms; 144 definitions verified in English and 139 in Spanish |
| Monthly cost | 0 € |

## How quality is evaluated

- **Data:** dbt tests on every run (keys, relationships, accepted values, freshness, scope rules). An error stops publishing; a warning is published and explained on the status page.
- **LLM texts:** every sentence must cite a fact, keep its numbers and scientific names, and not copy 8 words in a row from the source. Model configurations were compared on 12 reference pages before choosing one.
- **Website:** every build is checked for broken links, ES/EN parity and the license of every picture.
- **Decisions:** 10 ADRs with context, alternatives and consequences, and a document per phase with what went wrong and what was learned.
