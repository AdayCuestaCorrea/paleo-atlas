"""Store the Wikipedia test fixture as if it had been ingested.

Lets CI (and anyone without network access) run `paleo parse` and `dbt build`
end to end on real, version-controlled data:

    PALEO_DATA_DIR=/tmp/paleo-data uv run python scripts/seed_fixture_data.py
"""

import json
from pathlib import Path

from paleo.config import get_paths
from paleo.ingest.wikipedia import page_dir

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests/fixtures/wikipedia/2026_in_archosaur_paleontology.r1383165113.wikitext"
)
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


if __name__ == "__main__":
    main()
