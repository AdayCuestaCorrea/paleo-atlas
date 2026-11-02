"""Project-wide configuration: paths, identity and source pages.

Everything that can change between environments (local, CI, Airflow) is read
from environment variables with sensible defaults, so the same commands run
unchanged under any orchestrator (ALCANCE.md, decision D4).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from paleo import __version__

REPO_URL = "https://github.com/AdayCuestaCorrea/paleo-atlas"
CONTACT_EMAIL = "adaycuestacorrea@gmail.com"

# Wikimedia requires a descriptive User-Agent with contact details and the
# word "bot" for automated clients (ALCANCE.md §5).
USER_AGENT = (
    f"paleo-atlas-bot/{__version__} ({REPO_URL}; {CONTACT_EMAIL}) httpx/{httpx.__version__}"
)

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def project_root() -> Path:
    """Repository root (two levels above ``src/paleo``)."""
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    """Filesystem layout for pipeline data."""

    data: Path

    @property
    def raw(self) -> Path:
        return self.data / "raw"

    @property
    def interim(self) -> Path:
        return self.data / "interim"

    @property
    def warehouse(self) -> Path:
        return self.data / "warehouse.duckdb"


def get_paths() -> Paths:
    """Data paths, overridable with ``PALEO_DATA_DIR`` (used by tests and CI)."""
    data = os.environ.get("PALEO_DATA_DIR")
    return Paths(data=Path(data).resolve() if data else project_root() / "data")


@dataclass(frozen=True)
class WikipediaPage:
    """A yearly Wikipedia page that lists new taxa and research for one block."""

    block: str  # taxonomic block from ALCANCE.md §4
    title_template: str
    enabled: bool  # blocks are switched on by phase

    def title(self, year: int) -> str:
        return self.title_template.format(year=year)


# ALCANCE.md §4: archosaurs since Phase 1; marine reptiles and fossil fishes since Phase 3
# (only their sections in scope get pages: dbt macro wikipedia_group).
WIKIPEDIA_PAGES: tuple[WikipediaPage, ...] = (
    WikipediaPage("archosaurs", "{year} in archosaur paleontology", enabled=True),
    WikipediaPage("marine_reptiles", "{year} in reptile paleontology", enabled=True),
    WikipediaPage("fossil_fishes", "{year} in paleoichthyology", enabled=True),
)


def enabled_pages() -> list[WikipediaPage]:
    return [p for p in WIKIPEDIA_PAGES if p.enabled]


def slugify_title(title: str) -> str:
    """``2026 in archosaur paleontology`` -> ``2026_in_archosaur_paleontology``."""
    return title.strip().replace(" ", "_")
