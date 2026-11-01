"""Command-line entry point: ``paleo <command>``.

Every pipeline step is a command with a reliable exit code, so GitHub Actions
and Airflow can call exactly the same thing (ALCANCE.md §14, decision D4).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Annotated

import typer

from paleo.config import enabled_pages, get_paths
from paleo.http import make_client
from paleo.ingest import wikipedia as wiki_ingest
from paleo.parse import wikipedia as wiki_parse

app = typer.Typer(help="Paleo Atlas data pipeline.", no_args_is_help=True)
ingest_app = typer.Typer(help="Download sources and store raw responses.", no_args_is_help=True)
parse_app = typer.Typer(help="Turn raw responses into rows for dbt.", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(parse_app, name="parse")

Year = Annotated[int | None, typer.Option(help="Year of the Wikipedia pages [default: this year].")]


def _year(year: int | None) -> int:
    return year if year is not None else dt.date.today().year


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def check(year: Year = None) -> None:
    """Exit 0 if any source has changed since the last run, 1 if nothing changed."""
    changed = []
    with make_client() as client:
        for page in enabled_pages():
            title = page.title(_year(year))
            if wiki_ingest.has_new_revision(client, title):
                changed.append(title)
    if changed:
        for title in changed:
            typer.echo(f"changed: {title}")
        raise typer.Exit(0)
    typer.echo("no changes")
    raise typer.Exit(1)


@ingest_app.command("wikipedia")
def ingest_wikipedia(year: Year = None) -> None:
    """Store the latest revision of each enabled yearly page."""
    with make_client() as client:
        for page in enabled_pages():
            result = wiki_ingest.ingest_page(client, page.title(_year(year)))
            state = "stored" if result.created else "already stored"
            typer.echo(f"{result.revision.title}: revision {result.revision.revid} {state}")


@parse_app.command("wikipedia")
def parse_wikipedia(
    year: Year = None,
    all_revisions: Annotated[
        bool, typer.Option(help="Re-parse every stored revision, not only the latest.")
    ] = False,
) -> None:
    """Parse stored revisions into new_taxa.jsonl and research.jsonl."""
    paths = get_paths()
    found = False
    for page in enabled_pages():
        title = page.title(_year(year))
        revids = wiki_ingest.stored_revids(title, paths.raw)
        if not revids:
            typer.echo(f"{title}: nothing stored yet (run `paleo ingest wikipedia`)", err=True)
            continue
        found = True
        for revid in revids if all_revisions else revids[-1:]:
            raw = wiki_ingest.load_raw(wiki_ingest.page_dir(title, paths.raw) / f"{revid}.json")
            parsed = wiki_parse.parse_page(raw["title"], raw["revid"], raw["wikitext"])
            out = wiki_parse.write_interim(parsed, paths.interim)
            typer.echo(
                f"{raw['title']} @ {revid}: {len(parsed.new_taxa)} new taxa, "
                f"{len(parsed.research)} research items, "
                f"{parsed.warning_count()} warnings → {out}"
            )
    if not found:
        raise typer.Exit(1)
