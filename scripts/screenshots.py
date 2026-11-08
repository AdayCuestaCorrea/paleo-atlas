"""README screenshots (docs/img/web/) from the local build, in dark mode, 1210x980.

    uv run paleo site
    uv run --with playwright python scripts/screenshots.py

Uses the Chromium Playwright already installed (``playwright install chromium``);
the site is served from site/_build on a free local port while it runs.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "site" / "_build"
OUT = ROOT / "docs" / "img" / "web"
VIEW = {"width": 1210, "height": 980}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


def serve() -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(Quiet, directory=str(BUILD))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def scroll_to(page, selector: str, offset: int = 70) -> None:
    """Put an element just under the sticky header."""
    page.evaluate(
        "([s, o]) => window.scrollTo(0, document.querySelector(s).getBoundingClientRect().top"
        " + window.scrollY - o)",
        [selector, offset],
    )
    page.wait_for_timeout(600)


def main() -> None:
    server, base = serve()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            # Reduced motion: the carousel starts paused, so the shot is stable.
            ctx = browser.new_context(viewport=VIEW, color_scheme="dark", reduced_motion="reduce",
                                      locale="es-ES")  # fmt: skip
            page = ctx.new_page()

            page.goto(f"{base}/es/index.html", wait_until="networkidle")
            page.wait_for_timeout(800)
            page.screenshot(path=OUT / "home.jpg", quality=85, type="jpeg")

            page.click('.scope button[data-scope="all"]')
            page.locator(".ribbon__seg", has_text="Cretácico").first.click()
            page.wait_for_timeout(1200)
            scroll_to(page, "#h-explore", 80)
            page.screenshot(path=OUT / "explore.jpg", quality=85, type="jpeg")

            page.goto(f"{base}/es/taxones/tyrannosaurus.html", wait_until="networkidle")
            page.wait_for_timeout(800)
            page.screenshot(path=OUT / "taxon.jpg", quality=85, type="jpeg")

            scroll_to(page, "#parientes", 80)
            page.wait_for_timeout(600)
            page.screenshot(path=OUT / "taxon-relatives.jpg", quality=85, type="jpeg")
            browser.close()
    finally:
        server.shutdown()
    print("Screenshots:", ", ".join(sorted(f.name for f in OUT.glob("*.jpg"))))


if __name__ == "__main__":
    main()
