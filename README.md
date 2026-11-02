**English** · [Español](README.es.md)

# Paleo Atlas

A living, visual paleontology encyclopedia in Spanish and English, rebuilt automatically from open scientific data.

**Website:** https://adaycuestacorrea.github.io/paleo-atlas/

**Status:** Phase 1 (archosaur species of 2026, both languages) is live and updated daily by GitHub Actions; Phase 2 (the same pipeline as Airflow DAGs, with proven parity) is implemented. The full project scope lives in [`ALCANCE.md`](ALCANCE.md) (Spanish, canonical); [`SCOPE.md`](SCOPE.md) is the English version, updated at the end of each phase.

**How each phase works and why** (Spanish): [`docs/fases/`](docs/fases/).

This README will be completed in Phase 4 (architecture, design decisions, benchmark, metrics).

## Airflow (local)

The same pipeline that GitHub Actions runs every day, as Airflow 3.3 DAGs in Docker ([`airflow/`](airflow/)). Every task calls a `paleo` command; the DAGs hold no pipeline logic of their own.

| DAG | When | What |
|---|---|---|
| `paleo_daily` | Tue–Sun 06:23 UTC | Change detection; the full pipeline only if a source changed |
| `paleo_weekly` | Mon 06:23 UTC | Everything, without change detection (weekly recap) |
| `paleo_monthly` | 1st of the month | Every source queried again (retractions, corrections); GBIF and Spark come in Phase 3 |
| `paleo_ci_parity` | On demand | The CI fixture job, to compare its output with CI's |

**Same result as GitHub Actions**, checked three ways: a test compares the `paleo` commands of the DAGs with those of the workflows, in order; `scripts/parity.py` compares a fingerprint (one hash per warehouse table and per website file) of the `paleo_ci_parity` DAG with the one uploaded by CI for the same commit; and the run log of a daily DAG run matches that of the Actions run of the same day. The DAGs never publish: they work on a local clone of the `data` branch, and only Actions pushes.

![paleo_daily graph](docs/img/airflow/graph.jpg)
![A run where ingest_wikipedia failed and Airflow retried it](docs/img/airflow/retry.jpg)
![The retried task's log: Wikipedia unreachable, connection refused](docs/img/airflow/retry-up-for-retry.jpg)

```sh
cd airflow
./bin/init-work.sh                                  # local clone of the data branch
GIT_SHA=$(git rev-parse HEAD) docker compose up -d --build
# http://localhost:8080 (local only, no password)
docker compose down
```

## License

Code: [AGPL-3.0](LICENSE) · Original content: [CC BY-NC-SA 4.0](LICENSE-CONTENT.md) · Third-party data and images keep their own licenses.
