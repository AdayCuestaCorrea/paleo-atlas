from pathlib import Path

import pytest

from paleo.parse.wikipedia import ParsedPage, parse_page

FIXTURES = Path(__file__).parent / "fixtures"
ARCHOSAUR_FIXTURE = FIXTURES / "wikipedia" / "2026_in_archosaur_paleontology.r1383165113.wikitext"


@pytest.fixture(scope="session")
def archosaur_text() -> str:
    return ARCHOSAUR_FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def archosaur_page(archosaur_text: str) -> ParsedPage:
    return parse_page("2026 in archosaur paleontology", 1383165113, archosaur_text)
