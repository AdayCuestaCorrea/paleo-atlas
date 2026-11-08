**English** · [Español](historias-star.es.md)

# Paleo Atlas — STAR stories

Five interview stories, with measured figures. Each one can be told in about 2 minutes; the links lead to the evidence in the repo.

## 1. Spark only where it was measured

- **Situation:** the pipeline's daily layer runs on DuckDB. The GBIF download brings 932,494 fossil specimens whose names have to be reconciled with 4,787 PBDB genera, which is exactly the kind of job usually given to Spark.
- **Task:** decide with data whether Spark deserved a place in the pipeline, instead of adding it because it shows up in job ads.
- **Action:** I wrote a single specification of the job (exact → synonym → typo, plus aggregates by genus, institution and country) and two implementations, in DuckDB SQL and in PySpark. I checked that the four extracts were identical row by row (same SHA-256 fingerprints) and measured three sizes, three repetitions each in a fresh process, with the peak memory of the whole process tree, JVM included.
- **Result:** with the 932,494 rows, DuckDB takes 0.86 s and 459 MB; Spark, 13.7 s and 1.5 GB (15–17 times slower, 3–6 times more memory), and it needs 242 lines of code against 124. The daily layer stays on DuckDB, and Spark runs once a month in the Airflow DAG (14 s in Docker). It is all in [`benchmarks/gbif/results.md`](../../benchmarks/gbif/results.md) and in ADRs D1 and D5, which also state when the decision would change: if a daily source no longer fitted in a runner's memory (in the order of tens of millions of rows). Of Spark's 13.7 s, ~7.5 s are fixed start-up cost.

## 2. Reconciling names between two databases that do not agree

- **Situation:** GBIF and PBDB do not share a taxonomy. GBIF's tree does not even have the clades in scope (you cannot ask for "Archosauria"), and specimens arrive with synonyms, old combinations and typos.
- **Task:** map every specimen to its encyclopedia genus without letting in mammals, turtles or misidentified animals.
- **Action:** I asked GBIF for all fossil chordates except mammals and turtles and left the fine filter to the reconciliation with PBDB, which is where the truth about the scope lives. Three steps in order: exact name, synonym according to PBDB, and a typo one edit away from a single genus (Levenshtein ≤ 1). Coordinates that GBIF flags as wrong do not go on the map. For each genus's Wikipedia article I applied the same idea, with two independent signals: the PBDB ID in Wikidata and its ancestry up to the root of the block.
- **Result:** 138,388 specimens reconciled with 1,739 genera (118,371 exact, 17,052 by synonym and 2,965 by typo), from 78 institutions, with the download's DOI cited on the website. The double signal prevented a real error: the Wikidata item for *Coloradia*, a moth, carried the PBDB ID of a dinosaur.

## 3. An LLM that cites every sentence, and checks that are not too strict

- **Situation:** the website publishes science texts written by an LLM, in two languages, with nobody reviewing them one by one, and under the 0 € rule: a small model on the local GPU and Groq's free plan.
- **Task:** make sure no published text says anything that is not in its sources.
- **Action:** I split the work into checkable steps: extract facts with their source, write in English citing one fact per sentence, and adapt to Spanish sentence by sentence. Every sentence goes through checks for numbers, scientific names, anti-copy (8 words in a row) and citation; if a page fails, the website shows a text built from its data instead. I chose the configuration with 12 reference pages. When one batch gave 56 failures out of 214 in Spanish, I read them one by one: most were silly rules ("Manu" inside *manual*, "siglo XIX" counted as a lost number, a clade written in Spanish).
- **Result:** 598 verified pages in English and 582 in Spanish; 82 % of the 43,764 extracted facts pass the check. Fixing the rules rescued 43 Spanish pages without calling the model again. And a lesson I tell: automation guarantees faithfulness, not style; the Spanish calques only showed up by reading a sample.

## 4. Measuring a classifier without fooling yourself

- **Situation:** news from three outlets with a license is classified by an LLM into four classes and grouped when two outlets, or two languages, tell the same story.
- **Task:** publish honest metrics for both.
- **Action:** 300 headlines were labelled by hand with a purpose-built tool, and 294 matched the LLM's proposal. Instead of publishing 98 %, I treated it as what it was, an upper bound caused by anchoring, and ran a blind sample of 50 without the proposal, which also repeated the human labels. For deduplication I compared a TF-IDF baseline (threshold chosen by cross-validation) with an LLM judging each candidate pair, on 47 labelled pairs.
- **Result:** blind, the LLM agrees with the person 74 % of the time, and the person with themselves 84 %: that is the ceiling of the task. The two classes most often confused were also the ones the person kept changing, so they were merged and agreement rose for both. In deduplication, the judge reached F1 1.00 against 0.29 for TF-IDF, with 4 calls. Both figures are published in the README with what they mean.

## 5. A daily pipeline that costs nothing

- **Situation:** a personal project with no budget: nothing that could produce a bill.
- **Task:** a reliable daily pipeline, with an LLM, without paid services.
- **Action:** the state lives in git (every raw response versioned in a `data` branch), the warehouse is a DuckDB file rebuilt from scratch on every GitHub Actions run, and the website is static on GitHub Pages. For the LLM: content-addressed caching (a repeated call spends no quota), a quota limiter, resumable batches and the volume on the local GPU, with a temperature watchdog. Each source has its own rhythm (Wikipedia daily; PBDB, Commons or GBIF weekly or monthly), and before anything else, one light request per yearly page (only the ID of the latest revision) tells whether there is anything new, so no requests or LLM quota are spent for nothing. A public status page shows every run, its tests and the freshness of each source.
- **Result:** 0 € a month. A full run takes ~3 minutes on Actions, with 196 dbt tests: an error stops publishing, and a warning is published and explained on the status page. The 5 scheduled runs from 4 to 8 November were green. And the limitation is written down: GitHub's free cron fires 7 to 8.5 hours late, which is enough for a website that changes once a day.
