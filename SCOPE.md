[Español (canónico)](ALCANCE.md) · **English**

# SCOPE — Paleo Atlas

> **English translation of [`ALCANCE.md`](ALCANCE.md).** The Spanish document is canonical; this version is updated when each phase closes, not on every change. If the two disagree, `ALCANCE.md` wins.
>
> **Single source of truth for the project.** If something is not here, it is not in scope.
> Every scope change is recorded in the [Changelog](#25-changelog) with a date and a reason.
> New ideas go to the [Backlog](#24-idea-backlog) first; they only enter scope when moved with a changelog entry.
> Checkboxes `[ ]` are ticked `[x]` when done.

**Created:** 2026-10-31 · **Translated from version:** 7 · **Status:** Phase 0 closed · Phase 1 starts 2026-11-02

---

## Contents

1. [Vision](#1-vision)
2. [Career goal and traceability to job postings](#2-career-goal-and-traceability-to-job-postings)
3. [In and out of scope](#3-in-and-out-of-scope)
4. [Taxonomic scope](#4-taxonomic-scope)
5. [Data sources](#5-data-sources)
6. [Architecture](#6-architecture)
7. [Phases and deliverables](#7-phases-and-deliverables)
8. [Data model (dbt)](#8-data-model-dbt)
9. [Per-taxon change history](#9-per-taxon-change-history)
10. [Study verification](#10-study-verification)
11. [The website: languages, pages and taxon page](#11-the-website-languages-pages-and-taxon-page)
12. [AI: narrative taxon pages and glossary](#12-ai-narrative-taxon-pages-and-glossary)
13. [3D models](#13-3d-models)
14. [Pipeline command contract](#14-pipeline-command-contract)
15. [Orchestration and freshness](#15-orchestration-and-freshness)
16. [Data quality and observability](#16-data-quality-and-observability)
17. [Project metrics (for CV and interviews)](#17-project-metrics-for-cv-and-interviews)
18. [Costs: €0](#18-costs-0)
19. [Licensing, attribution and ethics](#19-licensing-attribution-and-ethics)
20. [Documentation and portfolio material](#20-documentation-and-portfolio-material)
21. [Risks and mitigations](#21-risks-and-mitigations)
22. [Decisions](#22-decisions)
23. [Schedule](#23-schedule)
24. [Idea backlog](#24-idea-backlog)
25. [Changelog](#25-changelog)
26. [Repository layout](#26-repository-layout)

---

## 1. Vision

A **living, visual paleontology encyclopedia in Spanish and English** that updates itself:

- **Breaking news:** what is published today shows up on the site within hours (see §15).
- **Weekly recap:** a summary of everything that happened during the week, archived.
- **Encyclopedia:** one page per taxon with a 2D image (and 3D when a reliable model exists), key facts, **a history of everything discovered or changed about it**, a map of finds and the museums holding specimens.
- **Visual relationships:** family and classification of each animal, and a **relationship tree** showing its "siblings", laid out on geological time.
- **Size comparator:** *T. rex* versus *Ankylosaurus*, an elephant or a plane, to scale.
- **For every audience:** a glossary and explanations for readers who don't know what a holotype or the Cretaceous is.
- **Visible rigor:** every study shows reliability signals (peer-reviewed, preprint, retracted…).

Audience:
- **Readers:** paleontology enthusiasts, in Spanish or English.
- **Recruiters and technical interviewers** (Data Engineer / Data Scientist / AI Engineer): first and foremost, this is a portfolio piece.

**Guiding principle:** every tool must be justified by the problem, not by the CV. If a decision cannot be defended in a technical interview, it doesn't go in.

---

## 2. Career goal and traceability to job postings

Demonstrate, with a system that runs in public, the skills requested by the Data Engineer / Data Scientist postings evaluated during the author's job search (19 postings as of 2026-10-31; per-company detail stays private).

| Skill | Postings mentioning it (of 19) | Required in | Component that demonstrates it |
|---|---|---|---|
| Spark / PySpark | 4 | 2 | GBIF job in local PySpark + benchmark against DuckDB (Phase 3) |
| Databricks | 3 | — | *Optional:* same job on Databricks Free Edition (Phase 3) |
| Airflow | 3 | 1 | Dockerized DAGs calling the same commands (Phase 2) |
| dbt | 2 | — | dbt-duckdb: staging → intermediate → marts + **snapshots (SCD2)** for history (Phase 1) |
| CI/CD | 4 | — | GitHub Actions: tests on every push + scheduled runs (Phase 1) |
| Data quality | cross-cutting | — | dbt tests + pytest + run report (Phase 1) |
| LLM / generative AI | AI Engineer profile | — | Narrative taxon pages: sourced fact extraction → writing → faithfulness and anti-copy checks (Phases 1 and 3); glossary (Phase 5) |
| NLP / ML | DS profile | — | News classification and deduplication with evaluation (Phase 5) |

**Deliberately not covered:**
- **AWS:** ruled out by the €0 rule (§18). It is a real gap (some postings ask for it); if needed, it will be covered separately.
- Power BI, Kubernetes, MLflow, Kafka: they make no sense for this problem.

**Honesty note on Spark:** the GBIF download API filters server-side, so the incoming volume is manageable with DuckDB. Spark runs in local mode and is **measured** against DuckDB on the same job. If DuckDB wins, that is what gets documented. What gets shown in an interview is the comparison with numbers, not "I used Spark".

---

## 3. In and out of scope

### In
- The groups in §4, by phase.
- **Bilingual** site (Spanish and English) with a language selector.
- Daily detection of new items + weekly recap.
- Per-taxon change history.
- Reliability signals for every study.
- Encyclopedia with PBDB and GBIF data; local Spark + benchmark.
- Freely licensed 2D images; curated 3D models when they exist and are reliable.
- Family and classification on every taxon page; relationship tree with a time scale (Phase 3).
- Size comparator against present-day objects and animals, only with sourced sizes (Phase 6).
- **Original narrative taxon pages** in ES + EN, every sentence cited (§12.1): new species in Phase 1, the whole encyclopedia in Phase 3.
- AI: glossary and news classification (Phase 5).
- Airflow in Docker; GitHub Actions for scheduled runs.
- Bilingual README, ADRs, interview pack.

### Out (not done unless a change is recorded)
- Any paid service (AWS, paid hosted databases, paid APIs).
- Groups not listed in §4 (they go to the backlog).
- Mobile app, user accounts, comments.
- Chatbot / conversational explainer (dropped on 2026-11-01: the glossary covers that need).
- Minute-level real time (needs an always-on server; see backlog).
- Spark in the daily/weekly layer.
- Scraping news sites; press images.
- Images or 3D models under non-commercial (NC) licenses or without a clear license (§19).
- Copying or adapting prose from Wikipedia or papers: only facts are extracted (§12.1, §19).
- Claiming anything on the CV or in interviews that the project doesn't actually do.

---

## 4. Taxonomic scope

Scope is defined in a data file (`dbt/seeds/scope_clades.csv`), not in code. **Extending scope = adding rows to the seed + a changelog entry.**

| Block | Groups | Famous examples | Yearly Wikipedia page (check exact title) | Phase |
|---|---|---|---|---|
| Archosaurs | Dinosauria (incl. fossil birds), Pterosauria, Crocodylomorpha and relatives | *Spinosaurus*, *T. rex*, *Quetzalcoatlus*, *Sarcosuchus* | "YYYY in archosaur paleontology" | 1 |
| Marine reptiles | Ichthyosauromorpha, Sauropterygia (plesiosaurs, pliosaurs, nothosaurs, placodonts), Mosasauridae | *Mosasaurus*, *Liopleurodon*, *Ophthalmosaurus* | "YYYY in reptile paleontology" | 3 |
| Fossil fishes | Placodermi, fossil Chondrichthyes (sharks), other notable fossil fishes | *Dunkleosteus* (a placoderm — **a fish, not a reptile**), *Otodus megalodon* | "YYYY in paleoichthyology" | 3 |

Notes:
- Mosasaurs are squamates (relatives of lizards and snakes), not archosaurs. That is why they sit under "marine reptiles" and not in block 1.
- Out for now (backlog): fossil synapsids and mammals (*Dimetrodon*, mammoth), invertebrates (trilobites, ammonites), plants.

---

## 5. Data sources

> Before using each source: check its current license and terms of use and record it here ("Verified" column).

| # | Source | Provides | Access | Frequency | License (to verify) | Verified |
|---|---|---|---|---|---|---|
| F1 | Wikipedia — yearly pages from §4 (current year + earlier years for history) | New taxa: name, status, authors, age, geological unit, locality, reference | MediaWiki API; never HTML scraping | Daily (change detection) | Text CC BY-SA 4.0 (+ GFDL): facts are used, text is not copied | [x] 2026-11-01 |
| F2 | PBDB — `data1.2` API | Taxonomy, synonymies, **taxonomic opinions with year and reference** (history), time range, occurrences | REST API | Daily (new taxa) + monthly (full) | CC BY 4.0 (cite PBDB) | [x] 2026-11-01 |
| F3 | GBIF — download API (server-side filter) | Fossil specimens (`basisOfRecord = FOSSIL_SPECIMEN`) for the §4 groups: coordinates, institution, country | Free public API (GBIF account) | Monthly | Each download has a DOI that must be cited; per-record licenses | [ ] |
| F4 | PhyloPic — API v2 | Silhouettes per taxon (falling back to genus or clade) | REST API | Daily (only taxa without an image) | Per image. **Only PDM, CC0, CC BY 3.0/4.0, CC BY-SA 3.0** (CC BY-NC and CC BY-NC-SA excluded) | [x] 2026-11-01 |
| F5 | Wikimedia Commons — API | Reconstructions and fossil photos | MediaWiki API | Daily (only taxa without an image) | Per file; Commons does not accept NC-only or ND licenses | [x] 2026-11-01 |
| F6 | Crossref — REST API | Study metadata: type (article / preprint), journal, ISSN, **retractions and corrections** | Public API | For every new study + monthly review | Metadata free to use; abstracts may be copyrighted | [x] 2026-11-01 |
| F7 | ZooBank | Official name registration (mandatory for electronic publications under the ICZN) | API / public search | For every new taxon | To verify | [ ] |
| F8 | DOAJ | Whether an open-access journal is listed in the directory | Public API | For every new journal | To verify | [ ] |
| F9 | *(Phase 5)* RSS feeds from ES/EN media | News: headline, link, date | RSS | Daily | Headline + link + our own summary only | [ ] |
| F10 | *(Phase 6)* 3D model sources (§13): Smithsonian 3D, MorphoSource, Sketchfab, museum collections | 3D models | API or official embed | Manual curation | Per model; same allowed licenses as F4 | [ ] |
| F11 | *(Phase 3)* Open Tree of Life — API | Synthetic relationship tree (topology), with cross-references to other databases | Public API | Monthly | To verify | [ ] |
| F12 | *(Phase 6)* Published body-size datasets (e.g. on Dryad) + hand-curated seed | Estimated length and mass, with range and citation | Download + curation | One-off | Dryad publishes under CC0; others to verify per dataset | [ ] |

### License check results (2026-11-01)

| Source | What it says | What we do |
|---|---|---|
| **F1 Wikipedia** | Text under CC BY-SA 4.0 (and GFDL). Reusing or modifying the text requires attribution, noting changes, and releasing under the same license. Images have their own per-file license | We only extract facts (§12.1); the anti-copy test enforces it. The article is cited as a source on the taxon page. No Wikipedia images except through Commons (F5) |
| **F2 PBDB** | The whole database has been under **CC BY 4.0** since 2013; attribution only | PBDB attribution on every taxon page and on "Sources & licenses". Until we find the official citation wording on their site, we use the project's general citation |
| **F4 PhyloPic** | Four license groups: public domain (PDM, CC0), attribution (CC BY 3.0/4.0), ShareAlike (CC BY-SA 3.0) and **non-commercial (CC BY-NC 3.0, CC BY-NC-SA 3.0)**, still carried by some older images. CC BY requires crediting the creator with the attribution text from the image page and linking the license | License allowlist: PDM, CC0, CC BY 3.0/4.0, CC BY-SA 3.0. **NC images are discarded** (§19). Check in Phase 1 which license and author fields API v2 returns |
| **F5 Wikimedia Commons** | Per-file license. Commons **does not accept** NC-only or ND files. The API (`prop=imageinfo&iiprop=extmetadata`) returns `LicenseShortName`, `LicenseUrl`, `Artist`, `Credit`, `AttributionRequired`, `UsageTerms` | Allowlist on `LicenseShortName` (the most reliable field). Multi-licensed files: manual review, since the API warns those values are unreliable |
| **F6 Crossref** | "Almost none of the metadata is subject to copyright, and you may use it for any purpose". Abstracts may be copyrighted. Retractions appear in the `update-to` field, with `source` = `publisher` or `retraction-watch`; filter `update-type:retraction` | Metadata used freely. From abstracts we only extract facts; they are never published. Requests carry `mailto=` to join the "polite" pool |

**To check later:** F3 GBIF (Phase 3), F7 ZooBank, F8 DOAJ, F9 RSS (Phase 5), F10 3D (Phase 6), F11 Open Tree of Life (Phase 3), F12 sizes (Phase 6).

Sources for this check: [Reusing Wikipedia content](https://en.wikipedia.org/wiki/Wikipedia:Reusing_Wikipedia_content) · [Paleobiology Database now CC BY (Creative Commons, 2013)](https://creativecommons.org/2013/12/19/paleobiology-database-now-cc-by/) · [PhyloPic: Usage of Images](https://www.phylopic.org/articles/image-usage) · [Commons:Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing) · [Extension:CommonsMetadata](https://www.mediawiki.org/wiki/Extension:CommonsMetadata) · [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) · [Crossref: Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/) · [Wikimedia User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy) · [API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette)

**Common access rules:**
- `User-Agent` in the form `paleo-atlas-bot/<version> (<repo URL>; <email>) <library>/<version>`: Wikimedia requires a descriptive User-Agent with contact information, containing "bot" for automated clients, and blocks generic ones without notice.
- Wikimedia: requests **in series** (never in parallel), batch titles in one request (`titles=A|B|C`), `maxlag`, gzip, GET for reads, cache what has already been downloaded.
- Crossref: `mailto=` parameter.
- Respect rate limits; retries with exponential backoff.
- Store the raw response **as is** before transforming anything.

---

## 6. Architecture

```
DAILY LAYER (DuckDB, GitHub Actions)              MONTHLY LAYER (local PySpark)
────────────────────────────────────              ─────────────────────────────
Anything changed? (Wikipedia revision,            F3 GBIF: filtered download (with DOI)
 RSS, PBDB) ── no ──► stop                          → reconcile names against PBDB
     │ yes                                          → aggregate by taxon / institution / country
F1 F2 F4 F5 F6 F7 ─► raw JSON (`data` branch)       → Parquet extract
     │                                              ↕ same job in DuckDB → benchmark
     └────────► dbt (DuckDB): staging → intermediate → marts ◄──┘
                     + snapshots (history, §9)
                                 │
                 Static site generator (ES + EN)
                                 │
                           GitHub Pages
```

**Architecture decisions (each will get an ADR, see §20):**
- **D1.** No Spark in the daily layer: the volume doesn't justify it.
- **D2.** DuckDB instead of a hosted database: zero cost, zero maintenance.
- **D3.** State lives in git: raw responses versioned on the `data` branch; the DuckDB warehouse is **rebuilt from scratch** on every run → idempotent and auditable.
- **D4.** Orchestrator-agnostic commands: Airflow and GitHub Actions only call them.
- **D5.** Spark only for GBIF, locally, and measured against DuckDB.
- **D6.** Images and 3D only under allowed licenses (§19); never press images.
- **D7.** Original narrative pages: sourced facts → newly written prose via LLM → automated checks. The template is the fallback if anything fails (§12.1).
- **D8.** Bilingual from day one: data is language-independent; only texts and templates are duplicated.
- **D9.** History via dbt snapshots from day one: what isn't captured can't be rebuilt later.
- **D10.** Cheap change detection before running the full pipeline.

---

## 7. Phases and deliverables

Each phase has a **definition of done**. A phase doesn't start until the previous one is done.

### Phase 0 — Setup
- [x] Folder skeleton
- [x] Scope document
- [x] Name, licenses, language and budget decided (§22)
- [x] Licenses in the repo (`LICENSE`, `LICENSE-CONTENT.md`)
- [x] Decide A4 (Python and package manager) and A5 (site generator)
- [x] Verify licenses for F1, F2, F4, F5, F6 (§5)
- [x] Create public GitHub repo
- [x] Set up environment: uv, Python 3.14, ruff, pytest, `.editorconfig`
- [x] English version of this document (`SCOPE.md`)

**Done when:** repo published on GitHub.

### Phase 1 — MVP (archosaurs, bilingual)
- [ ] `ingest wikipedia`: current-year page via the API, stored raw
- [ ] Parser for the taxa table (irregular wikitext → rows), with fixtures
- [ ] `ingest pbdb`: data for each new taxon
- [ ] `ingest images`: PhyloPic → Commons → genus or clade silhouette, with license and author
- [ ] `ingest studies`: Crossref + ZooBank for each study (§10)
- [ ] dbt-duckdb: staging, intermediate and marts from §8
- [ ] **dbt snapshots** of taxon and study from the very first run (§9)
- [ ] Choose an LLM with a free tier (A18)
- [ ] Sourced fact extraction (Wikipedia ES/EN, PBDB, study metadata) for new species
- [ ] Narrative writing in ES + EN from the facts (§12.1)
- [ ] Checks: faithfulness, anti-copy, citation per sentence (§16) + manual review of a sample
- [ ] dbt and pytest tests from §16
- [ ] ES + EN site: home with language selector, "Breaking news", taxon page with history, weekly recap, "How we assess sources", "Sources & licenses"
- [ ] CI: tests on every push/PR
- [ ] Daily scheduled run with change detection + weekly recap (§15)
- [ ] Run report for every run
- [ ] Site published on GitHub Pages

**Done when:** the public site shows 2026's new archosaur species in both languages, with a verified narrative page, an image (or the group's), reliability signals and history, and it has updated itself **2 weeks in a row** without intervention.

### Phase 2 — Airflow
- [ ] `docker compose` with Airflow
- [ ] Daily DAG and weekly (recap) DAG, calling the same commands as Actions
- [ ] Monthly DAG (placeholder until Phase 3)
- [ ] Screenshots for the README (DAG, successful run, retry)

**Done when:** the DAGs produce exactly the same result as the Actions workflows.

### Phase 3 — Encyclopedia, expansion and Spark
- [ ] Full PBDB ingestion for all §4 groups (not only new taxa)
- [ ] Extend the scope seed: marine reptiles and fossil fishes (§4)
- [ ] Rebuild history backwards: PBDB taxonomic opinions + yearly Wikipedia pages from earlier years (§9)
- [ ] Filtered GBIF download (F3) and its DOI on the sources page
- [ ] Local PySpark job: name reconciliation against PBDB (synonyms, typos, rank) + aggregates
- [ ] Same job in DuckDB → **benchmark** (time, memory, code complexity)
- [ ] *Optional:* same job on Databricks Free Edition (check quotas and access to external data)
- [ ] Site: encyclopedia pages with map of finds, museums and timeline
- [ ] Indexes by group, period and country
- [ ] Full family and classification on every page (PBDB)
- [ ] Narrative pages for the whole encyclopedia (§12.1), in batches within the LLM free tier
- [ ] Relationship tree with a time scale (§11.2): Open Tree of Life topology (F11), falling back to PBDB classification; PBDB time ranges
- [ ] Real monthly DAG in Airflow

**Done when:** the encyclopedia for the three §4 blocks is published and the benchmark is documented with real numbers.

### Phase 4 — Portfolio
- [ ] Complete bilingual README (§20)
- [ ] ADRs D1–D10
- [ ] Interview pack: one-pager, 2-minute video, postmortem
- [ ] CV entry via career-ops `add` mode, with real metrics from §17
- [ ] Link on LinkedIn and on the GitHub profile

**Done when:** the project appears on the CV with a URL and verifiable metrics.

### Phase 5 — AI and news
- [ ] RSS ingestion (F9)
- [ ] News classification (new species / revision / new fossil / noise): classic baseline vs LLM, with metrics
- [ ] Extraction of the mentioned taxon and link to its page
- [ ] Deduplication of the same story across outlets (embeddings)
- [ ] Bilingual glossary with pop-up explanations on taxon pages (§12)

**Done when:** news classification metrics are published in the README and the glossary is reviewed and live on taxon pages.

### Phase 6 — Extras
- [ ] Curated 3D models (§13)
- [ ] Size comparator (§11.3)

**Done when:** each extra meets its rules in §11.3 and §13 and is published.

---

## 8. Data model (dbt)

### Entities
| Entity | Description |
|---|---|
| Taxon | Accepted name, rank, authors, year, clade, §4 block, time range |
| Event | Something that happens to a taxon: description, reassignment, synonymy, new specimen, new hypothesis, retraction *(Phase 5: news)* (§9) |
| Study | Scientific publication: DOI, journal, type, reliability signals (§10) |
| Specimen / occurrence | Fossil record with place, age and institution (PBDB and GBIF) |
| Institution | Museum or collection |
| Image | URL, type (silhouette / reconstruction / fossil), license, author, level (species / genus / clade) |
| 3D model | URL, type (scan / reconstruction), year, author, license (§13) |
| Body size | Estimated length and/or mass (min–max), method, citation (§11.3) |
| Reference object | Human, elephant, bus, plane…: sourced measurements (§11.3) |
| Fact | Atomic statement about a taxon, with source, citation and source snippet (§12.1) |
| Page text | Sections written per language, sentences linked to their facts, verification status |
| Glossary term | Term, ES definition, EN definition, review status (§12) |

### Layers (indicative names)
- **seeds:** `scope_clades`, `trusted_journals`, `contested_topics`, `models_3d`, `glossary`, `body_sizes`, `reference_objects`
- **staging:** `stg_wikipedia__new_taxa`, `stg_wikipedia__articles`, `stg_pbdb__taxa`, `stg_pbdb__opinions`, `stg_pbdb__occurrences`, `stg_gbif__fossil_specimens`, `stg_phylopic__images`, `stg_commons__images`, `stg_crossref__works`, `stg_zoobank__names`, `stg_otol__tree`, `stg_body_sizes`
- **snapshots:** `snap_taxon`, `snap_study`
- **intermediate:** `int_taxon_name_resolution`, `int_taxon_enriched`, `int_image_best_per_taxon`, `int_study_reliability`, `int_taxon_events`, `int_taxon_facts`
- **marts:** `dim_taxon`, `dim_taxon_tree` (parent-child + time range), `dim_study`, `dim_institution`, `dim_geologic_interval`, `fct_taxon_event`, `fct_taxon_text` (verified text per language), `fct_specimens_by_taxon`, `fct_weekly_recap`, `fct_run_summary`

---

## 9. Per-taxon change history

Every taxon page has a **timeline** with everything known about the taxon. When a new item affects an already known taxon (e.g. a new study on *Spinosaurus*), its "Breaking news" entry links to that timeline.

**Event types:** original description · genus reassignment or new combination · synonymy · *nomen dubium* · new specimen · new hypothesis (ecology, appearance, size) · correction or retraction of the study.

**Where it comes from:**
| Origin | Covers | Phase |
|---|---|---|
| dbt snapshots over our own ingestions (SCD type 2) | Every change since the project starts | 1 |
| PBDB taxonomic opinions (each opinion has a year and a reference) | Full taxonomic history going back | 3 |
| Yearly Wikipedia pages from earlier years | Descriptions from past years | 3 |
| Classified news | New hypotheses and debates | 5 |

**Open debates:** when studies contradict each other (e.g. whether *Spinosaurus* was an aquatic hunter or a wader), the event is marked **"Under debate"** and links to the studies behind each position. Curated by hand in the `contested_topics` seed.

---

## 10. Study verification

We don't judge the science: **we show verifiable signals** and explain what they mean.

| Signal | How it is checked | Badge on the site |
|---|---|---|
| Peer-reviewed | Crossref: type `journal-article` in a journal with an ISSN | 🟢 Peer-reviewed |
| Preprint | Crossref: type `posted-content`, or a preprint server (bioRxiv, PaleorXiv…) | 🟡 Preprint (not yet reviewed) |
| Retracted or corrected | Crossref (includes Retraction Watch data) | 🔴 Retracted / 🟠 Corrected |
| Registered name | ZooBank | ✔ Registered in ZooBank |
| Open-access journal in DOAJ | DOAJ | Secondary signal |
| Journal on the trusted list | `trusted_journals` seed (hand-curated: Nature, Science, JVP, Cretaceous Research, PeerJ, Papers in Palaeontology, Acta Palaeontologica Polonica…) | Secondary signal |
| Included in PBDB | PBDB | Secondary signal |

**Rules:**
- The rule that combines signals is **public and simple** (no opaque scores) and is explained on the "How we assess sources" page.
- A retracted study is never deleted: its event stays in the history with the red badge.
- Monthly retraction review of every study already published.
- General notice in every page footer: popular-science content, science changes, original sources are always linked.

---

## 11. The website: languages, pages and taxon page

### Languages
- Spanish and English, under `/es/` and `/en/`.
- The root page is a **simple language selector** (and the browser remembers the choice).
- Every page links to its counterpart in the other language.
- Scientific names untranslated; common names and texts in each language.

### Pages
1. **Language selector** (root).
2. **Home:** "Breaking news" + link to the latest recap.
3. **Weekly recap** (archive of every week).
4. **Taxon page.**
5. **Indexes:** by group, period, country *(Phase 3)*.
6. **Glossary** *(Phase 5)*.
7. **How we assess sources.**
8. **Sources & licenses.**
9. **About:** what it is, authorship, link to the repo.

### 11.1 Taxon page content
| Field | Source | If missing |
|---|---|---|
| Scientific name and meaning | F1 / PBDB | Hide the meaning |
| 2D image + author + license | F4 / F5 | Genus or clade silhouette, with an "approximate image" notice |
| 3D model *(Phase 6)* | F10 | Hide |
| Family and classification (family → order → class) | PBDB | Lowest known level |
| Group (clade) and block | PBDB / seed | Clade from F1 |
| Period and age (Ma) | PBDB / F1 | "Unknown" |
| Find locality | F1 / PBDB | Hide |
| Size (range + citation) and "Compare" button *(Phase 6)* | F12 / `body_sizes` seed (§11.3). **Never made up** | Hide |
| Relationship tree *(Phase 3)* | §11.2 | Classification as text only |
| **Narrative text** in sections: Description, Discovery, Paleobiology, Classification, Period and habitat, Debates; every sentence cited | §12.1 | Template text (§11.4) |
| Timeline / history | §9 | Original description only |
| Studies with badges | §10 | — |
| Map of finds *(Phase 3)* | PBDB + GBIF | Hide |
| Museums holding specimens *(Phase 3)* | GBIF | Hide |
| Sources and last-updated date | Pipeline | Always visible |

### 11.2 Relationship tree (Phase 3)
This kind of figure is called a **cladogram** or, with a time axis, a **time-calibrated phylogenetic tree**.
- **View:** the taxon in the center, its family and its "siblings" (closest relatives), each with its silhouette (F4) and name, and lines showing the relationships.
- **Time axis:** each branch is drawn over the interval in which the animal lived (first and last appearance in PBDB), on the period scale (Triassic, Jurassic, Cretaceous…). Filters by period.
- **Navigable:** clicking a sibling opens its page; you can move up or down a level (family → order). The whole tree is never drawn at once, only the taxon's neighborhood.
- **Honesty:** the topology comes from Open Tree of Life (a synthesis of many studies) or, if missing, from PBDB's classification, which is a classification and not a phylogenetic analysis. The view states its origin, and that the placement of many animals is debated.

### 11.3 Size comparator (Phase 6)
- Pick 2–4 items: atlas taxa and reference objects (person, African elephant, bus, airliner…).
- Drawn **to scale** with their silhouettes (F4), on a metric grid, with a person's height as reference.
- **Sourced sizes only:** each taxon shows its estimated range (min–max) and citation. Without a sourced size, the taxon doesn't appear in the comparator.
- Reference objects have sourced measurements in the `reference_objects` seed.
- Notice: sizes of extinct animals are estimates and change with new studies (links to the §9 history).

### 11.4 Fallback text (template)
Only used when the narrative page doesn't exist yet or fails its checks. Templates per language built from the fields. E.g.: "A new sauropod genus from the Upper Cretaceous of Argentina, described by X et al. (2026)".

---

## 12. AI: narrative taxon pages and glossary

### 12.1 Narrative pages (Phase 1: new species · Phase 3: whole encyclopedia)
Original prose, not bullet points, in ES + EN, with every sentence cited.

**Process:**
1. **Fact extraction:** the LLM reads the sources (Wikipedia ES and EN articles, PBDB, study metadata and abstracts) and pulls out **atomic facts**. Each fact keeps its source, citation and source snippet.
2. **Fact check:** each fact must be supported by its source snippet; otherwise it is discarded.
3. **Writing:** the LLM writes **new prose** in sections (Description, Discovery, Paleobiology, Classification, Period and habitat, Debates) **from the facts only**, in each language, citing every sentence.
4. **Automated checks** (§16):
   - **Faithfulness:** every name, number and date in the text is in the facts.
   - **Anti-copy:** no sentence reproduces long word sequences from the source.
   - **Citation per sentence:** no sentence without at least one citation.
5. **Manual review** of a sample; the pass rate of each check is published (§17).

**Rules:**
- If a page fails its checks, the fallback text (§11.4) is published and the page is flagged for review.
- Pages are generated **once per change** in the facts (not on every visit) and stored in the repo → they fit within a free tier.
- If the LLM free quota runs out, the pipeline keeps working: pending pages wait with the fallback text.
- Debated topics (§9) are presented as debates, with each position and its studies; a hypothesis is never presented as fact.
- Footer of every page: "Text written with AI assistance from the cited sources and automatically verified".

### 12.2 Glossary (Phase 5) — zero runtime cost
- 150–300 terms (holotype, theropod, Cretaceous, Ma, *nomen dubium*…), in ES + EN.
- First draft by an LLM, **reviewed by hand** before publishing (review status in the seed).
- On taxon pages, terms show a pop-up explanation on hover or tap; full glossary page.

---

## 13. 3D models

Two types, with different rules:

| Type | Example origins | Reliability | Rule |
|---|---|---|---|
| **Scan of a real fossil** | Smithsonian 3D, MorphoSource, museum collections | High: it is the bone, not an interpretation | Preferred |
| **Life reconstruction** | Sketchfab, paleoartists | Artistic; may become outdated | Only with author and year; automatic notice if it predates the taxon's latest major revision (from the §9 history): "May not reflect the latest studies" |

- License: same allowed licenses as images (§19). If only the official embedded viewer is permitted, that viewer is used.
- Tech: glTF viewer (`<model-viewer>`) or official embed, **loaded only on click** so the page stays light.
- Heavy models are not hosted in the repo (GitHub Pages size limits): they are linked or embedded from their origin.
- Manual curation in the `models_3d` seed. Expected coverage: low (dozens of taxa). The 2D image always stays.

---

## 14. Pipeline command contract

What must exist; implementation is decided in Phase 1.

| Command | Does | Idempotent |
|---|---|---|
| `paleo check` | Has any source changed since the last run? (exit code) | Yes |
| `paleo ingest wikipedia --year YYYY` | Downloads and stores raw | Yes |
| `paleo ingest pbdb` | PBDB data for pending taxa | Yes |
| `paleo ingest images` | Image for taxa without one | Yes |
| `paleo ingest studies` | Crossref + ZooBank + DOAJ | Yes |
| `paleo gbif extract` *(Phase 3)* | Filtered download + Spark/DuckDB job | Yes |
| `paleo build` | `dbt snapshot` + `dbt build` | Yes (full rebuild; snapshots accumulate history) |
| `paleo site` | Generates the ES + EN site | Yes |
| `paleo recap --week YYYY-Www` | Generates that week's recap | Yes |
| `paleo report` | Run report | Yes |

Requirements: reliable exit codes (0 = OK), structured logs, no hidden state outside git and `data/`.

---

## 15. Orchestration and freshness

A static site can't be real-time to the minute, but it can be **within hours**, for free:

| What | Where | When |
|---|---|---|
| Tests (pytest + dbt) | GitHub Actions | Every push and PR |
| Change detection + pipeline if there is something new | GitHub Actions (cron) | Daily (or every 6 h if useful, A6) |
| Weekly recap | GitHub Actions (cron) | Monday morning, Canary Islands time (A6) |
| Monthly pipeline (GBIF, retraction review) | Local (Spark on the author's machine) | Monthly |
| Demo | Airflow in Docker (local) | On demand |

- Cheap detection: compare Wikipedia page revision IDs and RSS/PBDB content with what is stored. If nothing changed, nothing else runs.
- Pipeline failure → GitHub email notification; the previous site stays published (a broken site is never published).
- GitHub cron schedules are not punctual (they can be delayed).
- **To verify:** GitHub disables scheduled workflows in public repos after 60 days without activity. Check whether pipeline commits count as activity.

---

## 16. Data quality and observability

### dbt tests (minimum)
- `unique` and `not_null` on the keys of every dimension.
- `relationships` between facts and dimensions.
- `accepted_values` on event type, image type and allowed licenses.
- **PBDB lag tolerance:** a new taxon without a PBDB match is a *warning* for N weeks (A7); after that, an *error*.
- Freshness: the latest change detection can't be older than 2 days.
- No image or 3D model without an allowed license and an author.
- Every study has at least one computed reliability signal.
- Every body size has a range, a method and a citation.
- Every tree node has an origin (Open Tree of Life or PBDB).
- Narrative pages: faithfulness (names, numbers and dates present in the facts), anti-copy (no sequence of N or more words identical to the source; N set in Phase 1), at least one citation per sentence, every fact with a source snippet.
- Language parity: every ES page exists in EN and vice versa.

### Python tests
- Wikipedia table parser with stored real cases (fixtures).
- Name reconciliation with known cases (synonyms, typos).
- Faithfulness and anti-copy checkers, with stored good and bad cases (Phase 1).

### Run report (every run)
Sources with changes, new / updated taxa, new events, % with a PBDB match, % with an image by level, test warnings and errors, duration per step.

---

## 17. Project metrics (for CV and interviews)

Filled in with real data; **never estimated on the CV**.

| Metric | Value | Date |
|---|---|---|
| New 2026 taxa captured / total on the Wikipedia pages | — | — |
| Taxa in the encyclopedia per block | — | — |
| Events in the history | — | — |
| % with a PBDB match | — | — |
| % with an image (species / genus / clade) | — | — |
| % of studies peer-reviewed / preprints / retracted | — | — |
| Mean delay publication → site (hours) | — | — |
| Consecutive weeks without manual intervention | — | — |
| Number of tests (pytest + dbt) | — | — |
| Daily pipeline duration | — | — |
| Monthly cost | €0 | — |
| GBIF: fossil specimens processed | — | — |
| Spark vs DuckDB benchmark: time, memory | — | — |
| News classifier: precision / recall (baseline vs LLM) | — | — |
| Narrative pages passing faithfulness / anti-copy / citation per sentence (%) | — | — |
| Extracted facts passing the fact check (%) | — | — |

---

## 18. Costs: €0

**Hard rule:** the project can't cost money. Nothing that could produce a bill. If a service asks for a card, it is only used if its free tier has a cap that prevents charging, and that is documented.

| Item | Free solution |
|---|---|
| Repo, CI, scheduled runs, website | GitHub (public repo: Actions and Pages are free) |
| Data APIs (F1–F8) | Public and free |
| GBIF | Download API (free) instead of the full AWS snapshot |
| Spark | Local mode on the author's machine (Docker) |
| Databricks *(optional)* | Free Edition (check limits) |
| LLM (from Phase 1) | Free tier (A18); if exhausted, pages wait with the fallback text |
| Domain | `github.io` |

---

## 19. Licensing, attribution and ethics

*(This is not legal advice; if the project ever generates income, it should be checked with a professional.)*

| What | License | Why |
|---|---|---|
| **Code** | **AGPL-3.0** | Copyleft that also covers network use: anyone running a service with this code (modified or not) must publish their code under the same license and keep the author's attribution. As copyright holder, the author can grant separate commercial licenses later (dual licensing) |
| **Original content** (taxon page texts, recaps, glossary, site design) | **CC BY-NC-SA 4.0** | Attribution required; no commercial use without the author's permission; derivatives under the same license |
| **Third-party data and images** | Their own, always visible | Attribution on every taxon page and on "Sources & licenses" |

**Rules to avoid conflicts with sources:**
- **Wikipedia prose is never copied or adapted** (CC BY-SA doesn't allow an NC derivative). Facts are not copyrightable: the LLM reads the text only to **extract facts**, and what gets published is new writing that passes the anti-copy test (§12.1).
- Pages cite the primary source (the study) whenever possible, not just Wikipedia.
- **Images and 3D models: only CC0, public domain, CC BY or CC BY-SA.** Nothing NC: if the project is ever monetized (ads, sponsorships), an NC image would have to be removed.
- Every image and model shows its author and license.
- Every GBIF download is cited with its DOI.
- AI-generated text is labeled as such.
- Rigor: if a fact isn't in a source, it isn't shown.

**AI-generated text:** it is probably not copyrightable (the EU and the US require human authorship), so the NC clause protects it only weakly. What is genuinely the author's and protectable: the human selection and review, the reviewed glossary, the design, the code and the brand.

**No license protects the idea itself.** What protects it: publishing early, the dated git history (proof of authorship), the "Paleo Atlas" name and visible authorship on the site and in the repo.

---

## 20. Documentation and portfolio material

### Bilingual README
- `README.md` (English) and `README.es.md` (Spanish), each linking to the other language on its first line.
- Content: what it is + link to the site + screenshot · architecture · design decisions (including **"Why no Spark in the daily layer"** and **"Spark vs DuckDB: measured"**) · benchmark · data quality and metrics · how to run locally · sources and licenses · known limitations.

### Scope document
- `ALCANCE.md` (Spanish) is **canonical**. `SCOPE.md` (English) is updated when each phase closes, not on every change, to avoid maintaining two living documents at once.

### ADRs (`docs/adr/`)
D1–D10 from §6, in a short format: context, decision, alternatives, consequences.

### Interview pack (`docs/interview-pack/`)
- **One-pager:** product, architecture, metrics, evaluation plan.
- **Demo:** public URL + 2-minute video.
- **Postmortem:** what worked, what didn't, what would change.
- Candidate **STAR stories**: state in git, history via snapshots, PBDB lag, name reconciliation, Spark vs DuckDB, reliability signals, LLM faithfulness checks, the €0 rule.

---

## 21. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Scope grows too much** (already 6 phases) | Project never finished | Phases with a definition of done; ideas go to the backlog; the CV is updated after Phase 1, not at the end |
| The project eats into job-application time | Job search slows down | Part-time schedule (§23); applications come first |
| The Wikipedia table changes format | Broken ingestion | Parser with fixtures; the previous site stays published |
| New taxa take time to reach PBDB | Incomplete pages | Lag-tolerant test; page shows what is available |
| No image for new species | Poor page | Genus or clade image, with a notice |
| The LLM makes things up | Misinformation | Facts with source snippets + faithfulness check + fallback text + sample review |
| Paraphrase too close to Wikipedia | License conflict | Anti-copy test; writing from facts only, never from the original text |
| LLM free quota runs out | Pages without narrative text | Batch generation, once per change; fallback text meanwhile |
| Licenses applied incorrectly | Legal issue / bad image | Prior verification (§5); license tests; nothing NC |
| Unsourced or outdated sizes | Misinformation | Cited sizes only; visible range; §16 test |
| Tree presented as absolute truth | Misinformation | Origin stated in the view; notice that relationships are debated |
| Outdated 3D model | Misinformation | Prefer scans; automatic date-based notice (§13) |
| GitHub disables the cron for inactivity | Site stops updating | Verify the rule (§15); warning in the run report |
| Claiming something on the CV that wasn't done | Caught out in an interview | Real metrics only (§17); CV via career-ops `add` mode |

---

## 22. Decisions

### Closed
| # | Decision | Outcome | Date |
|---|---|---|---|
| A1 | Name | **Paleo Atlas** (`paleo-atlas`) | 2026-10-31 |
| A2 | Licenses | Code **AGPL-3.0**; original content **CC BY-NC-SA 4.0** (§19) | 2026-10-31 |
| A3 | Languages | ES + EN site with a selector; bilingual README; `ALCANCE.md` canonical in ES + `SCOPE.md` in EN at each phase close | 2026-10-31 |
| A9 | Where Spark runs | Locally (Docker); Databricks Free Edition optional. GBIF via the download API | 2026-10-31 |
| A10 | Budget | **€0** (§18) | 2026-10-31 |
| A12 | Extend groups | Yes: marine reptiles and fossil fishes (§4), in Phase 3 | 2026-10-31 |
| A13 | Phase 5 | Yes | 2026-10-31 |
| A4 | Python and package manager | **uv** + **Python 3.14** (uv-managed, not the system one), pinned in `.python-version`. Checked on 2026-11-01: dbt-core 1.12, dbt-duckdb 1.11, DuckDB 2.0, Airflow 3.3 and PySpark 4.3 declare 3.14 support and dependencies resolve without conflicts. Tools: ruff (lint + format) and pytest | 2026-11-01 |
| A5 | Site generator | **Custom, in Python with Jinja2** + framework-free JavaScript for interactive parts | 2026-11-01 |
| A17 | How taxon pages are written | **Option A:** original narrative pages from cited facts (§12.1), from Phase 1 | 2026-11-01 |
| A15 | Conversational explainer | **Dropped**; the glossary stays (§12.2) | 2026-11-01 |

### Open
| # | Decision | Options | When |
|---|---|---|---|
| A18 | LLM for taxon pages (free tier, ES + EN, enough quota) | To compare | Phase 1, before week 3 |
| A6 | Detection frequency and recap time | Daily / every 6 h; Monday 06:00 Canary time | Phase 1 |
| A7 | PBDB lag tolerance in weeks (N) | 4, 8, 12 | Phase 1 |
| A8 | Airflow version | 2.x, 3.x | Phase 2 |
| A11 | Where the GBIF extract is stored | `data` branch, GitHub Releases | Phase 3 |
| A14 | Do Phase 6? | Yes / no / 3D only / comparator only | After Phase 5 |
| A16 | Initial trusted-journal list | `trusted_journals` seed | Phase 1 |

---

## 23. Schedule

Part-time and weekends, **without slowing down job applications**. Indicative dates; Phases 5 and 6 get dates once Phase 4 is done.

| Week | Dates | Phase |
|---|---|---|
| 1 | 2026-11-02 → 11-08 | Phase 1 (Wikipedia ingestion, parser, dbt staging) |
| 2 | 11-09 → 11-15 | Phase 1 (PBDB, images, studies, snapshots) |
| 3 | 11-16 → 11-22 | Phase 1 (narrative pages: facts, writing, checks) |
| 4 | 11-23 → 11-29 | Phase 1 (ES + EN site, Actions; the 2 weeks of autonomous runs begin) |
| 5 | 11-30 → 12-06 | Phase 2 + **provisional CV entry** |
| 6 | 12-07 → 12-13 | Phase 3 (full PBDB ingestion, extended groups, backward history) |
| 7 | 12-14 → 12-20 | Phase 3 (GBIF, Spark, benchmark) |
| 8 | 12-21 → 12-27 | Phase 3 (encyclopedia and narrative pages in batches) + Phase 4 |
| 9+ | from 12-28 | Phase 5, then Phase 6 |

---

## 24. Idea backlog

Ideas that are **not** in scope yet. To move an idea into scope: assign a phase + add a changelog entry.

| Idea | Notes |
|---|---|
| Minute-level real time | Listen to Wikipedia changes live (EventStreams); needs an always-on process |
| RSS feed of the site itself | Easy with a static site |
| Site search | There are serverless search engines for static sites |
| Paleogeographic map (where the continents were at the time) | Plate-reconstruction services exist; to investigate |
| Weekly email newsletter with the recap | Needs a free sending service |
| More groups: synapsids and mammals, invertebrates, plants | Extend the §4 seed |
| Public Paleo Atlas data API | Review redistribution licenses |

---

## 25. Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-11-01 | v7: environment set up (A4 settled: Python 3.14); `SCOPE.md` created; **Phase 0 closed**; §2 anonymized (no company names); order of F10 and changelog fixed | Phase 0 close |
| 2026-11-01 | v6: licenses for F1, F2, F4, F5 and F6 checked; image license allowlists; Wikimedia and Crossref access rules (§5) | Phase 0 check |
| 2026-11-01 | v5: original narrative pages from cited facts, moved forward to Phase 1 (§12.1); faithfulness and anti-copy checks; A4 and A5 closed; new decision A18 (LLM); schedule extended by one week | User decision (option A) |
| 2026-11-01 | v4: conversational explainer removed (former §12.3); proposals for A4 and A5 | User decision |
| 2026-11-01 | v3: family and classification on the taxon page; relationship tree with time scale (§11.2, Phase 3); size comparator (§11.3, Phase 6); sources F11 (Open Tree of Life) and F12 (body sizes) | User request |
| 2026-10-31 | v2: per-taxon history (§9); study verification (§10); bilingual site; daily "Breaking news" + weekly recap; AI (summaries, glossary, explainer) (§12); 3D models (§13); extension to marine reptiles and fossil fishes (§4); AWS replaced by GBIF via API + local Spark (€0 rule); AGPL-3.0 + CC BY-NC-SA 4.0 licenses; new Phase 6; backlog | User decisions on the v1 questions |
| 2026-10-31 | v1: document created | Project start |

---

## 26. Repository layout

```
paleo-atlas/
├── ALCANCE.md              ← scope document (canonical, ES)
├── SCOPE.md                ← this document (EN), updated at each phase close
├── README.md / README.es.md
├── LICENSE                 ← AGPL-3.0 (code)
├── LICENSE-CONTENT.md      ← CC BY-NC-SA 4.0 (original content)
├── pyproject.toml / uv.lock / .python-version
├── src/paleo/
│   ├── ingest/             ← F1–F12
│   ├── enrich/             ← name reconciliation, images, reliability
│   └── site/               ← site generator (ES + EN)
├── spark/jobs/             ← GBIF job (Phase 3)
├── dbt/
│   ├── models/{staging,intermediate,marts}/
│   ├── snapshots/          ← history (§9)
│   ├── tests/  seeds/  macros/
├── airflow/dags/
├── .github/workflows/
├── site/{templates,static}/
├── benchmarks/             ← Spark vs DuckDB
├── tests/                  ← pytest
├── docs/
│   ├── adr/
│   └── interview-pack/
└── data/                   ← local, git-ignored (versioned raw data lives on the `data` branch)
```
