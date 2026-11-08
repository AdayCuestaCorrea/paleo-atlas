[Español (canónico)](ALCANCE.md) · **English**

# SCOPE — Paleo Atlas (summary)

> **English summary of [`ALCANCE.md`](ALCANCE.md)**, which is canonical and much longer (phases with every checkbox, decisions, risks, the full change log). This summary is updated when a phase closes, not on every change. If the two do not match, `ALCANCE.md` wins. Section numbers follow `ALCANCE.md`, so `ALCANCE.md` §N is the detail of §N here.

**Summarised from version:** 46 (2026-11-08) · **Status:** Phases 0, 2, 4 (except the LinkedIn post), 5 and 6 done; Phase 1 completing its 2 unattended weeks (until 2026-11-21); Phase 3 published, with narrative pages for the whole encyclopedia still growing in batches.

Website: https://adaycuestacorrea.github.io/paleo-atlas/ · Interview pack: [`docs/interview-pack/`](docs/interview-pack/one-pager.md)

---

## 1. Vision

A **visual, living paleontology encyclopedia in Spanish and English** that updates itself:

- **Latest news:** what is published today shows up on the website within hours; a weekly recap is archived.
- **Encyclopedia:** one page per taxon with a picture, key data, a size comparison, the **history of everything discovered or changed about it**, a map of finds and the museums that hold specimens.
- **Relationships:** family, full classification and a relationship tree on a geological time scale.
- **For everyone:** a glossary with pop-up explanations.
- **Visible rigour:** every study carries reliability signals (peer reviewed, preprint, retracted…).

Audience: paleontology fans in either language, and **technical recruiters and interviewers** (Data Engineer / Data Scientist / AI Engineer): it is first of all a portfolio piece.

**Guiding principle:** every tool has to be justified by the problem, not by the CV. If a decision cannot be defended in a technical interview, it does not go in.

## 2. Career goal

Show, with a system that runs in public, the skills asked for in the Data Engineer / Data Scientist postings reviewed during the author's job search (19 postings on 2026-10-31; only anonymous counts are public): Spark (4 of 19), Airflow (3), dbt (2), CI/CD (4), data quality, LLMs and NLP. Each skill maps to a component: the GBIF job in PySpark with a benchmark, Airflow DAGs, dbt with SCD2 history and tests, GitHub Actions, the LLM narrative pages and the news classifier.

**Not covered on purpose:** AWS (ruled out by the 0 € rule), Power BI, Kubernetes, MLflow, Kafka. Databricks moved to the backlog in v46.

**Honesty note on Spark:** GBIF filters on the server, so the volume that arrives fits in DuckDB. Spark runs locally and is **measured** against DuckDB on the same job; DuckDB won, and that is what is documented.

## 3. In and out of scope

**In:** the groups of §4; a bilingual website; daily change detection and a weekly recap; per-taxon history; reliability signals; an encyclopedia from PBDB and GBIF; local Spark with a benchmark; free-licensed 2D images; classification and a relationship tree; a size comparator with sourced sizes only; **original narrative pages in ES and EN where every sentence cites its source**; glossary and news classification; Airflow in Docker; README, ADRs and interview pack.

**Out (unless a change is recorded):** anything that costs money; groups not in §4; mobile app, accounts, comments; a conversational explainer; minute-level real time; Spark in the daily layer; scraping news sites or press images; NC or unclear-licence images; copying or adapting prose from Wikipedia or papers; claiming in a CV anything the project does not really do.

## 4. Taxonomic scope

Defined as data (`dbt/seeds/scope_clades.csv`), not code.

| Block | Groups | Since |
|---|---|---|
| Archosaurs | Dinosauria (fossil birds included), Pterosauria, Crocodylomorpha and relatives | Phase 1 |
| Marine reptiles | Ichthyosauromorpha, Sauropterygia, Mosasauridae | Phase 3 |
| Fossil fishes | Placodermi, fossil Chondrichthyes, and a seed of 29 famous genera (*Leedsichthys*, *Tiktaalik*…) | Phase 3 |

Synapsids and mammals, invertebrates and plants stay in the backlog.

## 5. Data sources

In use: **F1** Wikipedia yearly pages and genus articles · **F2** PBDB (taxonomy, opinions, ranges, occurrences) · **F3** GBIF filtered download (cited by DOI) · **F4** PhyloPic silhouettes · **F5** Wikimedia Commons · **F6** Crossref (study metadata, retractions, corrections; abstracts never stored publicly) · **F8** DOAJ · **F13** Wikidata (checks each genus article with two independent signals) · **F9** RSS from three outlets whose licence allows reusing headline and link (ScienceDaily, The Conversation, SINC).

Postponed or discarded: F7 ZooBank (API down), F10 3D sources (backlog since v40), F11 Open Tree of Life (12 % coverage as a topology), F12 published size datasets (backlog, for cross-checking). Licences were checked before use; access follows each source's rules (descriptive User-Agent, serial requests to Wikimedia, `mailto=` for Crossref).

## 6. Architecture

```
open sources → paleo ingest → raw JSON versioned in git (`data` branch) → dbt + DuckDB → static site (Jinja2) → GitHub Pages
                                                         ↑ LLM: sourced facts → EN text → ES adaptation + checks
                                     GBIF (monthly) → name reconciliation in DuckDB and in PySpark (benchmark)
```

Ten decisions, each with an ADR in [`docs/adr/`](docs/adr/README.md): D1 no Spark in the daily layer · D2 DuckDB instead of a hosted database · D3 state lives in git and the warehouse is rebuilt from scratch · D4 commands independent of the orchestrator · D5 Spark only for GBIF, measured · D6 images only with allowed licences · D7 own narrative pages, verified · D8 bilingual from the start · D9 SCD2 history in SQL from the raw versions · D10 cheap change detection first.

## 7. Phases and deliverables

| Phase | Done when | Status (2026-11-08) |
|---|---|---|
| 0 — Setup | Repo published | Done |
| 1 — MVP (archosaurs, bilingual) | The public site shows the 2026 archosaur species in both languages, with verified narrative page, image, reliability signals and history, and has updated itself **2 weeks in a row** unattended | Built; the 2 weeks count from the 2026-11-07 merge (until 2026-11-21) |
| 2 — Airflow | The DAGs produce exactly the same result as Actions | Done (0 differences in 33 tables and 97 site files) |
| 3 — Encyclopedia, expansion and Spark | The three blocks are published and the benchmark is documented with real figures | Published; narrative pages for all 2,743 genera with an article grow in overnight GPU batches (598 EN / 582 ES so far); the Databricks variant moved to the backlog |
| 4 — Portfolio | The project is on the CV with URL and verifiable metrics | Done: bilingual README, ADRs, one-pager, postmortem, STAR stories, CV entry, GitHub profile; the LinkedIn post is left to the author |
| 5 — AI and news | News classification metrics are in the README and the glossary is on the pages with its sample accuracy | Done |
| 6 — Size comparator | The comparator follows §11.3 and is published | Done (3D models moved to the backlog in v40) |

Each phase has a document explaining the why, in Spanish: [`docs/fases/`](docs/fases/README.md).

## 8–10. Data model, history and study verification

- **dbt layers:** staging (one model per source) → intermediate → marts (`dim_taxon`, `dim_study`, `fct_taxon_event`, `fct_taxon_text`, `fct_news`, `fct_taxon_size`…), 66 models and 13 seeds.
- **History:** an event every time a taxon changes (described, synonymised, recombined, invalidated, revalidated, new study, Wikipedia row changed), from SCD2 over the raw versions and from PBDB's taxonomic opinions back to 1758.
- **Studies:** each one tracked since 2026 is checked in Crossref and DOAJ: peer-reviewed journal, preprint, retracted, corrected, trusted journal.

## 11. Website

Spanish and English under `/es/` and `/en/`, every page linked to its twin. Pages: language selector, home (curiosities carousel, latest studies and news, explorer by period, group and country), weekly recap, taxon page, indexes, glossary, how sources are evaluated, sources and licences, about, client-side search, news, size comparator and a public **Data status** page.

- **Taxon page:** full header image, quick facts and geological time strip, one-column reading with citations, side column with fact sheet and map, study history by decade.
- **Relationship tree:** PBDB classification and ranges, up to 20 relatives.
- **Size comparator:** only sizes read from verified sentences, with the citation, the range and whether it comes from partial remains; draggable silhouettes against people, animals alive today and buildings.

## 12. AI: narrative pages and glossary

- **Narrative pages:** the LLM extracts facts with their source, writes in English citing one fact per sentence and adapts to Spanish sentence by sentence. Only what passes the checks is published (faithfulness of numbers, names and dates; no 8-word copies; one citation per sentence; repetitions; length); otherwise a fallback text built from the data.
- **Models:** Qwen 3.5 9B on the local GPU for large batches, Groq's free plan in Actions.
- **Glossary:** each definition is written from the term's Wikipedia article (cited by revision), checked the same way and judged by a model from another family; a hand-reviewed sample of 20 is published with its accuracy.

## 13. 3D models

Out of scope since v40 (backlog); the design in `ALCANCE.md` §13 still holds if it comes back.

## 14–15. Commands and orchestration

- **Commands:** every step is a `paleo` command (`check`, `ingest …`, `build`, `narrate`, `site`, `report`…).
- **GitHub Actions:** runs them daily at 06:23 UTC, with a backup at 10:47 that does nothing if a run already finished. GitHub fires the cron 7–8.5 h late, which is enough for a site that changes once a day.
- **Airflow 3.3 in Docker:** runs the same commands locally, without publishing.
- **Failures:** a failed run never publishes a broken site; the previous one stays up.

## 16. Data quality and observability

- **dbt tests on every run:** keys, relationships, accepted values, PBDB lag tolerance (warning for 8 weeks, then error), freshness, licences, size citations, ES/EN parity, plus SCD2 unit tests.
- **pytest:** parsers with real fixtures, reconciliation cases, the checkers with good and bad cases, ingestion with simulated transport.
- **CI:** runs the whole pipeline offline on fixtures.
- **Run reports:** every run leaves a record in `runs/`, which feeds the public Data status page.

## 17. Project metrics

Measured, never estimated, with a date: see the table in [`ALCANCE.md` §17](ALCANCE.md#17-métricas-del-proyecto-para-cv-y-entrevistas). On 2026-11-08:

- 4,890 pages (10,260 web pages) and 19,541 history events;
- 302 pytest and 196 dbt tests;
- 932,494 GBIF specimens processed (138,388 reconciled);
- DuckDB 0.86 s against Spark 13.7 s;
- 598 / 582 verified narrative pages;
- blind news classification at 74 % agreement (the person with themselves, 84 %);
- ~3 min per daily run;
- 0 € a month.

## 18. Costs: 0 €

Hard rule: nothing that can produce a bill. GitHub (public repo: Actions and Pages), free public APIs, GBIF's download API instead of the AWS copy, Spark in local mode, Ollama on the author's GPU, Groq's free plan with a quota limiter and content-addressed caching, a `github.io` domain.

## 19. Licences and ethics

- **Licences:** code under **AGPL-3.0**; own content (texts, recaps, glossary, design) under **CC BY-NC-SA 4.0**; third-party data and images keep their licence, always shown.
- **No prose copied:** no prose from Wikipedia is copied or adapted, only facts are extracted, and AI-written text is labelled as such.
- **Images:** only CC0, public domain, CC BY or CC BY-SA.
- **Citations:** each GBIF download is cited by DOI.

## 20. Documentation

- **README** in English and Spanish.
- **Scope:** `ALCANCE.md` is canonical and this file is its summary.
- **Phase documents** in [`docs/fases/`](docs/fases/README.md).
- **ADRs** in [`docs/adr/`](docs/adr/README.md).
- **Interview pack** in [`docs/interview-pack/`](docs/interview-pack/one-pager.md): one-pager, postmortem and STAR stories, in both languages. The demo video was dropped in v35: the demo is the public website.

## 21–23. Risks, decisions and calendar

See `ALCANCE.md`. The main risks, with their mitigations:

- **Scope growth:** phases with a definition of done, and a backlog.
- **An LLM that invents things:** sourced facts, checks, fallback text and a reviewed sample.
- **Licence mistakes:** licence checks before use, tests and no NC material.
- **The GitHub cron not firing:** an off-the-hour schedule, a backup run and a freshness test.
- **Claiming in a CV something that is not done:** only measured metrics.

## 24. Backlog

Includes, among others:

- 3D models;
- pterosaur wingspan and body mass in the comparator;
- cross-checking sizes with published datasets;
- the GBIF job on Databricks Free Edition;
- more groups (synapsids, invertebrates, plants);
- an RSS feed of the site;
- palaeogeographic maps;
- a public data API;
- a second free LLM provider.

## 25. Changelog

The full log (v1 on 2026-10-31 to v46 on 2026-11-08) is in [`ALCANCE.md` §25](ALCANCE.md#25-registro-de-cambios). Milestones:

| Version | Date | Milestone |
|---|---|---|
| v7 | 2026-11-01 | Phase 0 closed |
| v11–v13 | 2026-11-02 | Phase 1 website published; first full review |
| v14 | 2026-11-02 | Phase 2 (Airflow) |
| v16–v27 | 2026-11-02/04 | Phase 3: encyclopedia, GBIF and Spark benchmark, history back to 1758, overnight GPU batches |
| v28–v31 | 2026-11-04/07 | New home page and taxon page; bilingual README |
| v29 | 2026-11-07 | Phase 3 merged into `main` |
| v34 | 2026-11-07 | Public Data status page |
| v36–v41 | 2026-11-07/08 | Phase 5: news and glossary |
| v40–v44 | 2026-11-08 | Phase 6: size comparator; 3D to the backlog |
| v43 | 2026-11-08 | New palette |
| v46 | 2026-11-08 | Phase 4: interview pack, CV, GitHub profile; Databricks to the backlog |
