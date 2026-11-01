"""Command-line entry point: ``paleo <command>``.

Every pipeline step is a command with a reliable exit code, so GitHub Actions
and Airflow can call exactly the same thing (ALCANCE.md §14, decision D4).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import subprocess
from typing import Annotated

import typer

from paleo.config import enabled_pages, get_paths, project_root
from paleo.http import make_client
from paleo.ingest import articles, crossref, images, pbdb
from paleo.ingest import wikipedia as wiki_ingest
from paleo.parse import wikipedia as wiki_parse

app = typer.Typer(help="Paleo Atlas data pipeline.", no_args_is_help=True)
ingest_app = typer.Typer(help="Download sources and store raw responses.", no_args_is_help=True)
parse_app = typer.Typer(help="Turn raw responses into rows for dbt.", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(parse_app, name="parse")

Refresh = Annotated[bool, typer.Option(help="Ignore freshness and query every entity again.")]
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


@ingest_app.command("pbdb")
def ingest_pbdb(refresh: Refresh = False) -> None:
    """Resolve candidate taxon names against PBDB (versioned per name)."""
    paths = get_paths()
    names = pbdb.names_of_interest(paths.interim)
    with make_client() as client:
        r = pbdb.ingest_names(client, names, raw_root=paths.raw, refresh=refresh)
    typer.echo(
        f"PBDB: {r.requested} names, {r.skipped_fresh} fresh, "
        f"{r.found} found, {r.not_found} not found, {r.new_versions} new versions"
    )


@ingest_app.command("studies")
def ingest_studies(refresh: Refresh = False) -> None:
    """Crossref metadata for every cited DOI (abstracts kept out of the repo)."""
    paths = get_paths()
    dois = crossref.dois_of_interest(paths.interim)
    with make_client() as client:
        r = crossref.ingest_dois(client, dois, raw_root=paths.raw, refresh=refresh)
    typer.echo(
        f"Crossref: {r.requested} DOIs, {r.skipped_fresh} fresh, "
        f"{r.found} found, {r.not_found} not found, {r.new_versions} new versions"
    )


@ingest_app.command("images")
def ingest_images(refresh: Refresh = False) -> None:
    """Commons files from the Wikipedia tables and PhyloPic silhouettes."""
    paths = get_paths()
    with make_client() as client:
        r = images.ingest_images(client, paths.interim, raw_root=paths.raw, refresh=refresh)
    typer.echo(
        f"Images: {r.commons_files} Commons files, {r.phylopic_queries} PhyloPic lookups "
        f"({r.phylopic_found} with an image), {r.new_versions} new versions"
    )


@ingest_app.command("articles")
def ingest_articles(refresh: Refresh = False) -> None:
    """Wikipedia articles (EN and, when it exists, ES) of the new taxa."""
    paths = get_paths()
    with make_client() as client:
        r = articles.ingest_articles(client, paths.interim, raw_root=paths.raw, refresh=refresh)
    typer.echo(
        f"Articles: {r.taxa} taxa, {r.skipped_fresh} fresh, {r.found['en']} EN and "
        f"{r.found['es']} ES found, {r.new_versions} new versions"
    )


Provider = Annotated[str, typer.Option(help="LLM provider: ollama or groq.")]
Model = Annotated[str | None, typer.Option(help="Model name [default: per provider].")]
Only = Annotated[list[str] | None, typer.Option(help="Only these taxa (repeatable).")]
Limit = Annotated[int | None, typer.Option(help="Process at most this many taxa.")]
DEFAULT_MODELS = {
    "ollama": "paleo-qwen3.5-9b",  # see ollama/Modelfile.qwen3.5-9b (16K context)
    "groq": "openai/gpt-oss-120b",
}


def _new_taxa(only: list[str] | None, limit: int | None) -> list[str]:
    from paleo.ingest.articles import new_taxa_titles

    names = sorted(new_taxa_titles(get_paths().interim))
    if only:
        wanted = {o.lower() for o in only}
        names = [n for n in names if n.lower() in wanted or n.lower().replace(" ", "-") in wanted]
    return names[:limit] if limit else names


def _scientific_names() -> set[str]:
    from paleo.ingest import pbdb as pbdb_ingest

    paths = get_paths()
    taxa = pbdb_ingest.store(paths.raw)
    names = set(_new_taxa(None, None))
    for key in taxa.stored_keys():
        latest = taxa.latest(key)
        if latest and latest["payload"]["found"]:
            names.update(r.get("taxon_name", "") for r in latest["payload"]["records"])
    # Genus names (capitalized): they must survive the Spanish adaptation untouched.
    return {word for name in names for word in name.split() if word[:1].isupper()}


@app.command()
def facts(
    provider: Provider = "ollama",
    model: Model = None,
    only: Only = None,
    limit: Limit = None,
) -> None:
    """Extract checkable facts for new taxa (writes data/derived/facts)."""
    from paleo.llm import LLM, QuotaExhausted
    from paleo.narrative.facts import extract_facts
    from paleo.narrative.sources import chunks_for

    paths = get_paths()
    llm = LLM(provider, model or DEFAULT_MODELS[provider])
    for taxon in _new_taxa(only, limit):
        chunks = chunks_for(
            taxon, interim_root=paths.interim, raw_root=paths.raw, cache_root=paths.data / "cache"
        )
        try:
            r = extract_facts(
                llm,
                taxon,
                chunks,
                derived_root=paths.data / "derived",
                cache_root=paths.data / "cache",
            )
        except QuotaExhausted as exc:
            typer.echo(f"Quota exhausted ({exc}); remaining taxa stay pending.")
            break
        typer.echo(f"{taxon}: {r.accepted} facts accepted, {r.rejected} rejected")
    typer.echo(f"{llm.label}: {llm.stats}")


@app.command()
def write(
    provider: Provider = "ollama",
    model: Model = None,
    only: Only = None,
    limit: Limit = None,
) -> None:
    """Write and check the EN text and its ES adaptation (writes data/derived/texts)."""
    from paleo.llm import LLM, QuotaExhausted
    from paleo.narrative.sources import chunks_for, taxon_key
    from paleo.narrative.write import write_page

    paths = get_paths()
    llm = LLM(provider, model or DEFAULT_MODELS[provider])
    names = _scientific_names()
    for taxon in _new_taxa(only, limit):
        facts_path = paths.data / "derived" / "facts" / f"{taxon_key(taxon)}.json"
        if not facts_path.exists():
            typer.echo(f"{taxon}: no facts yet (run `paleo facts`)")
            continue
        chunks = chunks_for(
            taxon, interim_root=paths.interim, raw_root=paths.raw, cache_root=paths.data / "cache"
        )
        try:
            r = write_page(
                llm, facts_path, chunks, derived_root=paths.data / "derived", scientific_names=names
            )
        except QuotaExhausted as exc:
            typer.echo(f"Quota exhausted ({exc}); remaining taxa stay pending.")
            break
        typer.echo(f"{taxon}: {r.status} {r.words}")
        for lang, problems in r.problems.items():
            for problem in problems[:5]:
                typer.echo(f"   [{lang}] {problem}")
    typer.echo(f"{llm.label}: {llm.stats}")


@app.command()
def build() -> None:
    """Run ``dbt build`` (models + tests) on the current raw and interim data."""
    dbt_dir = project_root() / "dbt"
    env = {**os.environ, "PALEO_DATA_DIR": str(get_paths().data)}
    cmd = ["dbt", "build", "--project-dir", str(dbt_dir), "--profiles-dir", str(dbt_dir)]
    raise typer.Exit(subprocess.run(cmd, env=env, check=False).returncode)


@parse_app.command("wikipedia")
def parse_wikipedia(
    year: Year = None,
    force: Annotated[
        bool, typer.Option(help="Re-parse revisions that were already parsed.")
    ] = False,
) -> None:
    """Parse every stored revision into new_taxa.jsonl and research.jsonl.

    Revisions that already have interim output are skipped unless ``--force``
    (e.g. after improving the parser).
    """
    paths = get_paths()
    found = False
    for page in enabled_pages():
        title = page.title(_year(year))
        revids = wiki_ingest.stored_revids(title, paths.raw)
        if not revids:
            typer.echo(f"{title}: nothing stored yet (run `paleo ingest wikipedia`)", err=True)
            continue
        found = True
        skipped = 0
        for revid in revids:
            done = wiki_parse.interim_dir(title, revid, paths.interim) / "parse_report.json"
            if done.exists() and not force:
                skipped += 1
                continue
            raw = wiki_ingest.load_raw(wiki_ingest.page_dir(title, paths.raw) / f"{revid}.json")
            parsed = wiki_parse.parse_page(
                raw["title"], raw["revid"], raw["wikitext"], raw.get("timestamp")
            )
            out = wiki_parse.write_interim(parsed, paths.interim)
            typer.echo(
                f"{raw['title']} @ {revid}: {len(parsed.new_taxa)} new taxa, "
                f"{len(parsed.research)} research items, "
                f"{parsed.warning_count()} warnings → {out}"
            )
        if skipped:
            typer.echo(f"{title}: {skipped} revision(s) already parsed (use --force to redo)")
    if not found:
        raise typer.Exit(1)
