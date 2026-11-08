**English** · [Español](postmortem.es.md)

# Paleo Atlas — postmortem

From 2026-10-31 (first version of the scope) to 2026-11-08 (Phases 1, 2, 3, 5 and 6 published). Every failure is described in detail in the "What went wrong" section of each [phase document](../fases/README.md) (in Spanish); this page collects what repeats across phases.

## What worked

- **State in git and the warehouse from scratch.** Every source response is stored as versioned JSON and the warehouse is rebuilt in full on every run. Because of that, the history (SCD type 2) is derived in SQL from the versions, any day can be reproduced, and merging two data branches comes down to a script (`scripts/merge_data.py`) that joins by key.
- **Commands, not orchestrator code.** Actions and the Airflow DAGs call the same `paleo` commands. The parity check found 0 differences across 33 tables and 97 website files.
- **Measure before deciding.** Spark versus DuckDB was decided with a benchmark (same job, identical output row by row: DuckDB 0.86 s against 13.7 s). News deduplication, with 47 labelled pairs (LLM judge F1 1.00 against 0.29 for TF-IDF). The model for the narrative pages, with 12 reference pages and 4 configurations.
- **Automatic checks plus a human sample.** The LLM never publishes without passing the checks (one citation per sentence, numbers, names, anti-copy), and every new output (glossary, sizes) is published with the accuracy of a 20-item sample reviewed by hand: 19 of 20 in both cases.
- **Mock-ups with real data before building.** The home page, the taxon page, the status page, the news, the size comparator and the palette were each chosen among 3 or 4 mock-ups built with the real data. That surfaced problems that placeholder text hides: a page 6.7 screens long, 960 px images used as thumbnails, or a contrast that did not reach AA.
- **The 0 € rule** forced a design around quotas: content-addressed caching (a repeated call spends no quota), resumable batches and the local GPU for volume. The monthly cost is 0 €.

## What did not work

- **Private data in the first commit.** On 2026-11-01, private information that should not have been there slipped into the public repo, and the only clean way to remove it from the history was to delete the repo and create it again. Since then, a local `pre-push` hook searches a list of terms in the files and in the commit messages, and it is never skipped.
- **A GitHub cron is not a time of day.** The 06:00 UTC one never fired; the 06:23 one fires 7 to 8.5 hours late. It does not matter for a website that changes once a day, but it took a backup cron, a freshness test and the build date in the footer to make a failure visible.
- **Overnight batches depend on the PC.** One batch stopped at the 7th species because of a truncated JSON; another was cut at 06:21 because the PC went to sleep (227 genera done). The first was fixed with retries and by skipping the bad item; the second is still pending (`systemd-inhibit` in the batch script).
- **Checks that were too literal hid the real failures.** In one batch, 56 of 214 Spanish pages failed, most of them because of silly rules: "Manu" inside *manual*, "siglo XIX" (19th century) counted as a lost number, a clade written in Spanish. With the rules fixed, 43 were rescued without calling the model again.
- **Looking only at what changes.** The comparator silhouettes were reviewed by eye in several rounds, but each round looked at the silhouettes that changed. *Giganotosaurus* came out with a *Monolophosaurus*, and later *T. rex* with "Tyrannosaurus magnus". The user spotted both on the published website. In the end a query that looks at all of them was written: silhouettes whose node is neither the page nor one of its species.
- **Labelling with the model's proposal in view.** 294 of 300 headlines kept the LLM's label: that is anchoring, not accuracy. A blind sample of 50 was needed (LLM 74 %; the person against themselves, 84 %), and both figures are published with what they mean.
- **Small LLMs write calques in Spanish** ("superdepredador", "Hacia 1875") that no automatic check detects. They were found by reading, and fixed with rules in the prompts.
- **The browser cache misleads reviews.** Several times a fix "did not work" because Chrome was serving the old CSS or JavaScript from the local server.

## What I would change

1. **A checklist before the first push** to a public repo, with the terms hook installed from the first commit, not after the scare.
2. **Decide how labelling works before showing the model's proposal.** A blind sample from the start, and the proposal only to speed up the rest.
3. **Turn every review query into a test.** The silhouette one, the size extremes (the top 10 and bottom 10 found 0 m, 1 mm and a 58 m record) or the Wikipedia links of species that have a genus page were run by hand once; as dbt tests, they would warn on their own next time.
4. **Rehearse with real data and under the runner's conditions from the start.** The Phase 3 merge rehearsal exposed two failures the fixture could not see: a PDF in the Wikipedia table that brought down image ingestion, and a model that could run out of memory (now 0.3 s instead of ~4 s, with the same result row by row).
5. **Long batches as a service that inhibits sleep** from day one, and logs outside `/tmp` from the start (the first one was there, and `/tmp` is wiped when the PC shuts down, which is exactly what the batch does when it finishes).
6. **Less scope at once.** The scope went through 45 versions in 9 days. The change log in `ALCANCE.md` kept it manageable, but starting Phase 5 before closing Phases 1 and 3 left open boxes in three phases at the same time.
