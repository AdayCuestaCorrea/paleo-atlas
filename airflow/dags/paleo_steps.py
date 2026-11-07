"""The pipeline's steps, in the order of .github/workflows/pipeline.yml.

Plain Python (no Airflow import), so the CI checks without Airflow that the DAGs run
the same `paleo` commands, in the same order and with the same arguments, as the
GitHub Actions workflow (tests/test_airflow_steps.py). Options that only say *where*
or *how* an orchestrator runs a command (--trigger, --provider, --out, --jobs) are
added by the DAG and are not part of this contract. The same goes for the
fixture job of ci.yml (CI_FIXTURE).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    task_id: str
    commands: tuple[str, ...]  # `paleo` subcommands, without the program name
    network: bool = False  # retried with backoff in Airflow
    narrative: bool = False  # LLM step: optional, never fails the run


# The daily run of pipeline.yml, job `update`.
DAILY: tuple[Step, ...] = (
    # "Anything new?": change detection, then the run record (changed or not).
    Step("detect", ("check", "report start --changed", "report start --no-changed")),
    # "Ingest and parse"
    Step("ingest_wikipedia", ("ingest wikipedia",), network=True),
    Step("parse_wikipedia", ("parse wikipedia",)),
    Step("ingest_pbdb", ("ingest pbdb",), network=True),
    Step("ingest_studies", ("ingest studies",), network=True),
    Step("ingest_images", ("ingest images",), network=True),
    Step("ingest_articles", ("ingest articles",), network=True),
    Step("ingest_news", ("ingest news",), network=True),
    # "Facts and texts for pending species" (and the news categories)
    Step("news_classify", ("news classify",), narrative=True),
    Step("news_dedup", ("news dedup",), narrative=True),
    Step("facts", ("facts",), narrative=True),
    Step("write", ("write",), narrative=True),
    Step("titles", ("titles",), narrative=True),
    # "dbt build": interim/ is rebuilt from the stored revisions when nothing changed.
    Step("parse_unchanged", ("parse wikipedia",)),
    Step("dbt_build", ("build",)),
    # "Build the website"
    Step("site", ("site",)),
    Step("site_check", ("site --check",)),
    # "Run report"
    Step("report_finish", ("report finish",)),
)

# Commands of pipeline.yml with no Airflow counterpart, and why.
ACTIONS_ONLY = {
    "report ran-today": "the 10:47 backup cron of GitHub Actions; Airflow schedules reliably",
}

# Monthly run: every source queried again, ignoring freshness (retractions,
# corrections, DOAJ changes, new PBDB records), then the GBIF download (it can take
# GBIF hours to prepare) reconciled with the PBDB genera in Spark (§7, Phase 3).
MONTHLY: tuple[Step, ...] = (
    Step("report_start", ("report start --changed",)),
    Step("parse_wikipedia", ("parse wikipedia",)),
    Step("refresh_pbdb", ("ingest pbdb --refresh",), network=True),
    Step("refresh_studies", ("ingest studies --refresh",), network=True),
    Step("refresh_images", ("ingest images --refresh",), network=True),
    Step("catalog_build", ("build",)),  # the genera the GBIF job reconciles with
    Step("gbif_extract", ("gbif extract",), network=True),
    Step("gbif_reconcile", ("gbif reconcile --engine spark",)),
    Step("dbt_build", ("build",)),
    Step("site", ("site",)),
    Step("site_check", ("site --check",)),
    Step("report_finish", ("report finish",)),
)

# The fixture job of .github/workflows/ci.yml (no network), for the parity check of
# scripts/parity.py: (task_id, working directory, command), in the order of ci.yml.
CI_FIXTURE_AS_OF = "2026-11-02"
CI_FIXTURE: tuple[tuple[str, str, str], ...] = (
    ("seed_fixtures", ".", "python scripts/seed_fixture_data.py"),
    ("parse_wikipedia", ".", "paleo parse wikipedia --year 2026"),
    ("dbt_build", "dbt", f"dbt build --profiles-dir . --vars '{{as_of: \"{CI_FIXTURE_AS_OF}\"}}'"),
    ("site", ".", "paleo site --base /paleo-atlas"),
    ("site_check", ".", "paleo site --check --base /paleo-atlas"),
    ("fingerprint", ".", "python scripts/fingerprint.py"),
)


def by_id(steps: tuple[Step, ...]) -> dict[str, Step]:
    return {s.task_id: s for s in steps}


def commands(steps: tuple[Step, ...]) -> list[str]:
    return [c for s in steps for c in s.commands]
