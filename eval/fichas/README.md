# Evaluation set: 15 hand-reviewed pages

Phase 7 of `ALCANCE.md`. On 2026-11-22 each of these 15 well-known pages was reviewed by a separate agent. Each agent read the live English and Spanish pages, the page's texts and facts, the cited Wikipedia article and its own paleontology knowledge. Every fix in Phase 7 is measured against this set.

*Tyrannosaurus, Triceratops, Velociraptor, Spinosaurus, Stegosaurus, Brachiosaurus, Diplodocus, Allosaurus, Ankylosaurus, Parasaurolophus, Pachycephalosaurus, Archaeopteryx, Iguanodon, Carnotaurus, Giganotosaurus*

## Files

- **`findings.csv`**: one row per problem.
  - `element`: where the problem is.
    - `text`: the narrative.
    - `header_age`, `countries`, `museums`, `valid_species`, `study_history`, `relatives`, `images`, `classification`: the panels built from PBDB, GBIF and Commons.
  - `cause`: why it happened. Examples:
    - `pbdb_range`, `misread_source`, `eswiki_error`;
    - `es_meaning` (the Spanish changes the meaning);
    - `es_calque` (a literal translation that reads wrong);
    - `en_es_mismatch`.
  - `severity`: `high` is wrong and visible, `medium` is misleading, `low` is wording.
  - `find`: for text rows, a substring that locates the sentence. Alternatives are separated by `|`.
  - `en_sentences`, `es_sentences`: the exact sentences it matched in the texts of 2026-11-22. Several are separated by ` || `.
  - `correct`, `checked_in`: what the page should say and where it was checked.
- **`pages.csv`**: one row per page, at the time of the review.
  - The text versions (`generated_at`, `facts_hash`).
  - The number of sentences per language and how many of them have a problem.

## Starting point (2026-11-22)

| | English | Spanish |
|---|---|---|
| Sentences in the 15 texts | 420 | 417 |
| With a high-severity problem | 7 (1.7 %) | 13 (3.1 %) |
| With a high or medium problem | 22 (5.2 %) | 55 (13.2 %) |
| With any problem | 36 (8.6 %) | 96 (23.0 %) |

Other figures:
- **141 findings in total:**
  - 91 in the texts;
  - 50 in the panels: 9 high, 17 medium and 24 low.
- **Panel problems:** 13 of the 15 pages have a header age taken from PBDB that is too wide or wrong. On the other two, the same range turns up elsewhere: inside the text (*Iguanodon*) and in the relatives chart (*Carnotaurus*).
- **Most frequent causes:**
  - the model misread the source (23);
  - the PBDB range (14);
  - calques in Spanish (14);
  - Spanish that changes the meaning (13).

**The figures are a lower bound.** The reviewers reported what they noticed; they did not check every sentence. To measure a fix, run it on these pages and count the rows that are no longer present:
- a text row is gone when none of its sentences remain, or when the problem is fixed;
- a panel row is gone when the page no longer shows the problem.

## Results

`results.csv` records the outcome of each fix per finding:
- `fixed`: the problem is gone;
- `partly`: some of it remains;
- `mitigated`: the data is unchanged but the page now says what it is;
- `open`: not fixed yet.

**Step 2, data panels (2026-11-22):** of the 50 panel findings, 30 are fixed, 8 partly, 7 mitigated and 7 open. All 9 high-severity ones are fixed. One finding was itself out of date. The reviewer expected *Giganotosaurus* to be Cenomanian, but English Wikipedia now gives early Albian, 111–106 Ma, after a 2026 study, and that is what the page shows.

The same set will be used to measure the automatic reviewer (Phase 7, step 5): which of these problems it finds, and how many sentences it flags that aren't problems.
