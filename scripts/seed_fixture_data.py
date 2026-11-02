"""Store the test fixtures as if they had been ingested.

Copies the yearly Wikipedia pages and the recorded PBDB, Crossref, Commons and
PhyloPic snapshots for their taxa into $PALEO_DATA_DIR/raw, so CI (and anyone
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
# Real revisions of the yearly pages: (title, revid, pageid, timestamp).
PAGES = [
    ("2026 in archosaur paleontology", 1383165113, 81645351, "2026-11-01T08:48:46Z"),
    ("2026 in reptile paleontology", 1383217772, 82002162, "2026-11-01T16:26:03Z"),
    ("2026 in paleoichthyology", 1383218081, 82004934, "2026-11-01T16:27:34Z"),
]


def main() -> None:
    for title, revid, pageid, timestamp in PAGES:
        fixture = FIXTURES / "wikipedia" / f"{title.replace(' ', '_')}.r{revid}.wikitext"
        target = page_dir(title, get_paths().raw) / f"{revid}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "source": "wikipedia",
            "title": title,
            "pageid": pageid,
            "revid": revid,
            "timestamp": timestamp,
            "fetched_at": "fixture",
            "license": "CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/",
            "wikitext": fixture.read_text(encoding="utf-8"),
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
