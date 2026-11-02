"""Store the test fixtures as if they had been ingested.

Copies the Wikipedia excerpt and the recorded PBDB, Crossref, Commons and
PhyloPic snapshots for its taxa into $PALEO_DATA_DIR/raw, so CI (and anyone
without network access) can run `paleo parse` and `dbt build` end to end on
real, version-controlled data:

    PALEO_DATA_DIR=/tmp/paleo-data uv run python scripts/seed_fixture_data.py
"""

import json
import shutil
from pathlib import Path

from paleo.config import get_paths
from paleo.ingest.wikipedia import page_dir

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
FIXTURE = FIXTURES / "wikipedia" / "2026_in_archosaur_paleontology.r1383165113.wikitext"
TITLE = "2026 in archosaur paleontology"
REVID = 1383165113


def main() -> None:
    target = page_dir(TITLE, get_paths().raw) / f"{REVID}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "source": "wikipedia",
        "title": TITLE,
        "pageid": 81645351,
        "revid": REVID,
        "timestamp": "2026-11-01T08:48:46Z",
        "fetched_at": "fixture",
        "license": "CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/",
        "wikitext": FIXTURE.read_text(encoding="utf-8"),
    }
    target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"seeded {target}")
    for source in sorted(p for p in (FIXTURES / "raw").iterdir() if p.is_dir()):
        shutil.copytree(source, get_paths().raw / source.name, dirs_exist_ok=True)
        print(f"seeded {source.name} snapshots")
    # One generated narrative page (facts + EN/ES texts) so dbt can build the text models.
    shutil.copytree(FIXTURES / "derived", get_paths().data / "derived", dirs_exist_ok=True)
    print("seeded derived narrative page")
    # One recorded run, so the freshness test and the site footer have a date.
    shutil.copytree(FIXTURES / "runs", get_paths().data / "runs", dirs_exist_ok=True)
    print("seeded run log")


if __name__ == "__main__":
    main()
