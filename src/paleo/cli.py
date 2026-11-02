"""Command-line entry point: ``paleo <command>``.

Every pipeline step is a command with a reliable exit code, so GitHub Actions
and Airflow can call exactly the same thing (ALCANCE.md §14, decision D4).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess
from typing import Annotated

import typer

from paleo.config import enabled_pages, get_paths, project_root
from paleo.http import make_client
from paleo.ingest import articles, crossref, doaj, images, pbdb
from paleo.ingest import wikipedia as wiki_ingest
from paleo.parse import wikipedia as wiki_parse

app = typer.Typer(help="Paleo Atlas data pipeline.", no_args_is_help=True)
ingest_app = typer.Typer(help="Download sources and store raw responses.", no_args_is_help=True)
parse_app = typer.Typer(help="Turn raw responses into rows for dbt.", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(parse_app, name="parse")
eval_app = typer.Typer(help="Evaluate narrative pages against the gold set.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")
report_app = typer.Typer(help="Run log and run report (ALCANCE.md §16).", no_args_is_help=True)
app.add_typer(report_app, name="report")
gbif_app = typer.Typer(
    help="GBIF fossil specimens, monthly (ALCANCE.md §7, Phase 3).", no_args_is_help=True
)
app.add_typer(gbif_app, name="gbif")

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
    """Exit 0 if any source has changed since the last run, 1 if nothing changed and
    2 if the check itself failed (the workflow then runs everything, so the error
    surfaces in the ingest and the run report instead of passing for "no changes")."""
    import httpx

    from paleo.http import HttpError

    changed = []
    try:
        with make_client() as client:
            for page in enabled_pages():
                title = page.title(_year(year))
                if wiki_ingest.has_new_revision(client, title):
                    changed.append(title)
    except (HttpError, httpx.HTTPError) as exc:
        typer.echo(f"check failed: {exc}", err=True)
        raise typer.Exit(2) from exc
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
    """Resolve candidate taxon names against PBDB (versioned per name), and download
    the catalog of every clade in scope and the occurrences of every block (monthly)."""
    paths = get_paths()
    names = pbdb.names_of_interest(paths.interim)
    with make_client() as client:
        r = pbdb.ingest_names(client, names, raw_root=paths.raw, refresh=refresh)
        typer.echo(
            f"PBDB: {r.requested} names, {r.skipped_fresh} fresh, "
            f"{r.found} found, {r.not_found} not found, {r.new_versions} new versions"
        )
        c = pbdb.ingest_catalog(client, pbdb.scope_clades(), raw_root=paths.raw, refresh=refresh)
        o = pbdb.ingest_occurrences(
            client, pbdb.scope_clades(), raw_root=paths.raw, refresh=refresh
        )
    typer.echo(
        f"PBDB catalog: {c.clades} clades, {c.skipped_fresh} fresh, "
        f"{c.records} records, {c.new_versions} new versions"
    )
    typer.echo(
        f"PBDB occurrences: {o.blocks} blocks, {o.skipped_fresh} fresh, "
        f"{o.records} records, {o.new_versions} new versions"
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
        issns = doaj.issns_of_interest(paths.raw)
        d = doaj.ingest_issns(client, issns, raw_root=paths.raw, refresh=refresh)
    typer.echo(
        f"DOAJ: {d.requested} ISSNs, {d.skipped_fresh} fresh, {d.listed} listed, "
        f"{d.not_listed} not listed, {d.new_versions} new versions"
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
    """Wikipedia articles (EN and, when it exists, ES) of the new taxa, and the
    article, Wikidata ids and lead image of the encyclopedia genera (a few hundred
    genera per run, re-checked monthly)."""
    from paleo.ingest import genus_articles

    paths = get_paths()
    with make_client() as client:
        r = articles.ingest_articles(client, paths.interim, raw_root=paths.raw, refresh=refresh)
        typer.echo(
            f"Articles: {r.taxa} taxa, {r.skipped_fresh} fresh, {r.found['en']} EN and "
            f"{r.found['es']} ES found, {r.new_versions} new versions"
        )
        genera = genus_articles.catalog_genera(paths.raw)
        g = genus_articles.ingest_genus_articles(
            client, genera, raw_root=paths.raw, refresh=refresh
        )
    typer.echo(
        f"Genus articles: {g.genera} genera, {g.skipped_fresh} fresh, {g.looked_up} looked up, "
        f"{g.with_article} with an article, {g.new_versions} new versions, "
        f"{g.failed} failed (retried next run)"
    )


Provider = Annotated[str, typer.Option(help="LLM provider: ollama or groq.")]
Model = Annotated[str | None, typer.Option(help="Model name [default: per provider].")]
Only = Annotated[list[str] | None, typer.Option(help="Only these taxa (repeatable).")]
Limit = Annotated[int | None, typer.Option(help="Process at most this many taxa.")]
Force = Annotated[bool, typer.Option(help="Regenerate even if the inputs did not change.")]
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
    force: Force = False,
) -> None:
    """Extract checkable facts for new taxa (writes data/derived/facts)."""
    from paleo.llm import LLM, LLMOutputError, QuotaExhausted
    from paleo.narrative.facts import extract_facts, sources_hash
    from paleo.narrative.sources import chunks_for, taxon_key

    paths = get_paths()
    llm = LLM(provider, model or DEFAULT_MODELS[provider])
    for taxon in _new_taxa(only, limit):
        chunks = chunks_for(
            taxon, interim_root=paths.interim, raw_root=paths.raw, cache_root=paths.data / "cache"
        )
        existing = paths.data / "derived" / "facts" / f"{taxon_key(taxon)}.json"
        unchanged = existing.exists() and json.loads(existing.read_text("utf-8"))[
            "sources_hash"
        ] == sources_hash(chunks)
        if unchanged and not force:
            typer.echo(f"{taxon}: up to date")
            continue
        study = next((c.doi for c in chunks if c.chunk_id.endswith(":study:1")), None)
        if study:
            with make_client() as client:
                if crossref.ensure_private(client, study, paths.data / "cache"):
                    chunks = chunks_for(
                        taxon,
                        interim_root=paths.interim,
                        raw_root=paths.raw,
                        cache_root=paths.data / "cache",
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
        except LLMOutputError as exc:  # one bad answer must not stop the batch
            typer.echo(f"{taxon}: skipped, invalid model output ({exc})")
            continue
        typer.echo(f"{taxon}: {r.accepted} facts accepted, {r.rejected} rejected")
    typer.echo(f"{llm.label}: {llm.stats}")


@app.command()
def write(
    provider: Provider = "ollama",
    model: Model = None,
    only: Only = None,
    limit: Limit = None,
    force: Force = False,
) -> None:
    """Write and check the EN text and its ES adaptation (writes data/derived/texts)."""
    from paleo.llm import LLM, LLMOutputError, QuotaExhausted
    from paleo.narrative.sources import chunks_for, taxon_key
    from paleo.narrative.write import is_up_to_date, write_page

    paths = get_paths()
    llm = LLM(provider, model or DEFAULT_MODELS[provider])
    names = _scientific_names()
    for taxon in _new_taxa(only, limit):
        facts_path = paths.data / "derived" / "facts" / f"{taxon_key(taxon)}.json"
        if not facts_path.exists():
            typer.echo(f"{taxon}: no facts yet (run `paleo facts`)")
            continue
        if not force and is_up_to_date(facts_path, paths.data / "derived"):
            typer.echo(f"{taxon}: up to date")
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
        except LLMOutputError as exc:  # one bad answer must not stop the batch
            typer.echo(f"{taxon}: skipped, invalid model output ({exc})")
            continue
        typer.echo(f"{taxon}: {r.status} {r.words}" + (f" review={r.review}" if r.review else ""))
        for lang, problems in r.problems.items():
            for problem in problems[:5]:
                typer.echo(f"   [{lang}] {problem}")
    typer.echo(f"{llm.label}: {llm.stats}")


@app.command()
def titles(provider: Provider = "ollama", model: Model = None, limit: Limit = None) -> None:
    """Spanish versions of the study titles (writes data/derived/study_titles)."""
    from paleo.llm import LLM, QuotaExhausted
    from paleo.narrative.titles import translate_titles

    paths = get_paths()
    llm = LLM(provider, model or DEFAULT_MODELS[provider])
    try:
        r = translate_titles(
            llm,
            raw_root=paths.raw,
            derived_root=paths.data / "derived",
            scientific_names=_scientific_names(),
            limit=limit,
        )
    except QuotaExhausted as exc:
        typer.echo(f"Quota exhausted ({exc}); the rest stay in English until the next run.")
        return
    typer.echo(
        f"{r.total} titles: {r.up_to_date} up to date, {r.translated} translated, "
        f"{r.rejected} rejected"
    )
    typer.echo(f"{llm.label}: {llm.stats}")


@eval_app.command("validate-gold")
def validate_gold() -> None:
    """Check that every gold page passes the same checks as generated pages."""
    from paleo.narrative import gold
    from paleo.narrative.sources import chunks_for

    paths = get_paths()
    names = _scientific_names()
    failed = 0
    for path in sorted((project_root() / gold.GOLD_DIR).glob("*.json")):
        doc = gold.load(path)
        chunks = chunks_for(
            doc["taxon"],
            interim_root=paths.interim,
            raw_root=paths.raw,
            cache_root=paths.data / "cache",
        )
        problems = gold.validate(doc, chunks, names)
        words = {
            lang: sum(len(t.split()) for t, _ in gold.sentences(doc, lang)) for lang in ("en", "es")
        }
        status = "OK" if not problems else f"{len(problems)} problems"
        typer.echo(f"{doc['taxon']}: {len(doc['facts'])} facts, {words} words — {status}")
        for problem in problems:
            typer.echo(f"   {problem}")
        failed += bool(problems)
    raise typer.Exit(1 if failed else 0)


@eval_app.command("run")
def eval_run(
    provider: Provider = "ollama",
    model: Model = None,
    label: Annotated[str | None, typer.Option(help="Name of the run [default: model].")] = None,
    only: Only = None,
) -> None:
    """Run the narrative pipeline on the gold set with one model and write a report."""
    import re

    from paleo.llm import LLM
    from paleo.narrative import evaluate
    from paleo.narrative.sources import chunks_for

    paths = get_paths()
    llm = LLM(provider, model or DEFAULT_MODELS[provider])
    label = label or re.sub(r"[^A-Za-z0-9.-]+", "-", llm.label).strip("-")
    names = _scientific_names()
    embed = evaluate.Embedder()
    results = []
    for doc in evaluate.load_gold(project_root()):
        if only and doc["taxon"] not in only:
            continue
        chunks = chunks_for(
            doc["taxon"],
            interim_root=paths.interim,
            raw_root=paths.raw,
            cache_root=paths.data / "cache",
        )
        r = evaluate.evaluate_taxon(
            llm,
            doc,
            chunks,
            run_dir=paths.data / "eval_runs" / label,
            cache_root=paths.data / "cache",
            scientific_names=names,
            embed=embed,
        )
        typer.echo(
            f"{r.taxon}: {r.status} en={r.en} es={r.es} "
            f"fact_recall={r.fact_recall} text_recall={r.text_recall}"
        )
        results.append(r)
        if r.status == "pending_quota":
            typer.echo("Quota exhausted: rerun tomorrow; finished calls are cached.")
    summary = evaluate.summarize(results, llm)
    report = evaluate.write_report(summary, project_root() / "eval" / "reports", label)
    typer.echo(f"Report: {report}")


@app.command()
def site(
    base: Annotated[
        str, typer.Option(envvar="PALEO_SITE_BASE", help="URL prefix, e.g. /paleo-atlas.")
    ] = "",
    out: Annotated[str | None, typer.Option(help="Output folder [default: site/_build].")] = None,
    check: Annotated[
        bool, typer.Option("--check", help="Only check the built site (links, hreflang…).")
    ] = False,
) -> None:
    """Render the static website (ES + EN) from the warehouse, or check it."""
    from pathlib import Path

    from paleo.site.build import build_site, write_report

    paths = get_paths()
    out_dir = Path(out) if out else project_root() / "site" / "_build"
    if check:
        from paleo.site.check import check_site

        result = check_site(out_dir, base=base)
        for problem in result.problems[:50]:
            typer.echo(f"  {problem}")
        typer.echo(f"Checked {result.pages} pages: {len(result.problems)} problems")
        raise typer.Exit(0 if result.passed else 1)
    report = build_site(paths.warehouse, out_dir, base=base)
    write_report(report, paths.data / "site_report.json")
    typer.echo(
        f"Site: {report['pages']} pages, {report['taxa']} taxa, "
        f"{report['verified_texts']} verified texts → {out_dir}"
    )
    if report["untranslated_terms"]:
        typer.echo(f"Untranslated terms: {', '.join(report['untranslated_terms'])}")


@app.command()
def build() -> None:
    """Run ``dbt build`` (models + tests) on the current raw and interim data."""
    dbt_dir = project_root() / "dbt"
    env = {**os.environ, "PALEO_DATA_DIR": str(get_paths().data)}
    cmd = ["dbt", "build", "--project-dir", str(dbt_dir), "--profiles-dir", str(dbt_dir)]
    raise typer.Exit(subprocess.run(cmd, env=env, check=False).returncode)


@report_app.command("start")
def report_start(
    trigger: Annotated[str, typer.Option(help="schedule, backup, manual or local.")] = "local",
    changed: Annotated[bool, typer.Option(help="Change detection found something new.")] = True,
) -> None:
    """Record that a run started and what change detection found (data/runs/)."""
    from paleo import report

    run = report.start_run(get_paths().data, trigger=trigger, changed=changed)
    typer.echo(f"Run started {run['started_at']} ({trigger}, changed={changed})")


@report_app.command("finish")
def report_finish(
    jobs: Annotated[
        str | None, typer.Option(help="GitHub API dump of this run's jobs (step durations).")
    ] = None,
) -> None:
    """Complete the current run record and print the report as Markdown."""
    from pathlib import Path

    from paleo import report

    paths = get_paths()
    run = report.finish_run(
        paths.data,
        warehouse=paths.warehouse,
        run_results=project_root() / "dbt" / "target" / "run_results.json",
        jobs=Path(jobs) if jobs else None,
    )
    typer.echo(report.markdown(run))


@report_app.command("ran-today")
def report_ran_today() -> None:
    """Exit 0 if a run already finished without failures today, 1 otherwise."""
    from paleo import report

    raise typer.Exit(0 if report.ran_today(get_paths().data) else 1)


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


@gbif_app.command("extract")
def gbif_extract(
    key: Annotated[
        str | None, typer.Option(help="Resume an already requested download instead.")
    ] = None,
) -> None:
    """Request the monthly GBIF download, wait for it (minutes to hours) and fetch it
    to the local cache; its record (key, DOI, filter) goes to the raw store."""
    from paleo.ingest import gbif

    with make_client() as client:
        try:
            rec, path = gbif.extract(client, raw_root=get_paths().raw, key=key)
        except gbif.GbifError as exc:
            typer.echo(f"GBIF: {exc}", err=True)
            raise typer.Exit(1) from exc
    typer.echo(
        f"GBIF download {rec['key']}: {rec['total_records']} records, DOI {rec['doi']} -> {path}"
    )


@gbif_app.command("reconcile")
def gbif_reconcile(
    key: Annotated[
        str | None, typer.Argument(help="GBIF download key [default: the latest download].")
    ] = None,
    engine: Annotated[str, typer.Option(help="duckdb or spark.")] = "duckdb",
) -> None:
    """Reconcile the download with the PBDB genera and write the aggregated extract
    (genus_specimens, institutions, countries, unmatched) to the raw store."""
    from paleo.gbif_job.run import latest_download, reconcile

    key = key or latest_download()
    if key is None:
        typer.echo("No GBIF download yet: run `paleo gbif extract` first.", err=True)
        raise typer.Exit(1)
    counts, seconds = reconcile(key, engine)
    typer.echo(f"GBIF {key} with {engine} in {seconds:.1f} s: {counts}")
