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

**Step 3, text checks (2026-11-22):** `paleo recheck-texts` runs the new checks over every verified text, with no model, and leaves out or puts right what they catch. Of the 89 text findings, 38 are gone, including 9 of the 11 high-severity ones. The two high ones left are misreadings of the source (*Allosaurus*'s skin, *Parasaurolophus*'s growth), which no rule catches.

Sentences of the 15 texts with a problem from this set, before and after:

| | English | Spanish |
|---|---|---|
| High | 1.7 % → 0.5 % | 3.1 % → 0.5 % |
| High or medium | 5.2 % → 4.1 % | 13.2 % → 6.8 % |
| Any | 8.6 % → 7.5 % | 23.0 % → 11.9 % |

The same set will be used to measure the automatic reviewer (Phase 7, step 5): which of these problems it finds, and how many sentences it flags that aren't problems.

**Step 5, whole-page reviewer (night of 2026-11-23):** `paleo review pages` read all 2,827 pages with gpt-oss 20B. It left out 1,524 repeated sentences and marked 1,269 pages for a rewrite because of contradictions or missing context. `paleo review rewrite` then went through 302 of them, best known first:
- 291 rewrites passed every check and replaced the page;
- 9 failed in Spanish and 1 in English, so those pages kept their text;
- 1 got an answer the run couldn't read.

The other 967 wait for later nights.

On the 15 pages, 10 were rewritten and 5 only lost repeated sentences or weren't touched. Of the 51 text findings still open after step 3:
- **14 are gone:** 13 fixed, including the last-but-one high one (*Allosaurus*'s skin, now three separate finds), and 1 partly fixed. Each was checked by hand: the problem is gone, not just reworded.
- **37 remain:** 1 high (*Parasaurolophus*'s growth), 20 medium and 16 low. Several rewritten pages kept the same faulty claim in new words, for example "this light skull" after "a massive skull", or *Kelsey*'s size given only in feet.

**New problems.** The rewrites wrote 109 new English sentences on these pages. Reading them by hand found 8 new problems:
- **medium (3):**
  - *Ankylosaurus*: "a broad and low back" put inside the skull sentence;
  - *Velociraptor*: "a genus of two known dinosaurs", where the source means two species;
  - *Pachycephalosaurus*: the dome is said to "cushion the brain".
- **low (5):**
  - a repeated naming date (*Allosaurus*);
  - a repeated age (*Pachycephalosaurus*);
  - "Other remains" with nothing before it (*Triceratops*);
  - two *Archaeopteryx* sentences that join unrelated claims with "while";
  - *Velociraptor*'s claws compared with bird wing bones.

**Net effect.** About 14 problems gone against 3 new medium and 5 new low ones. *Archaeopteryx*'s page went from 32 to 19 sentences, so a rewrite can also lose content. The Spanish of the new sentences was not reviewed by hand.

**Step 5, flagged sentences only (2026-11-25):** after nights 8 and 9, the rewrites change only the sentences the reviewer flagged (`paleo review rewrite`; the old way is `--whole-page`).

The remaining 290 pages took 10 minutes:
- 151 replaced;
- 135 unchanged, because the model returned every flagged sentence as it was;
- 4 failed in Spanish.

The fixes are good at missing context ("the juvenile specimen" now names whose it is), but rarely solve contradictions.

I checked 18 replaced pages, drawn at random, by hand:
- **11 clearly better** and 4 about the same.
- **4 with a new problem:**
  - *Atlantosuchus*: the Spanish said "Eoceno Superior" where the English says Late Palaeocene.
  - *Diogenornis*: "with recent estimates" is invented.
  - *Gondwanasuchus*: "baurusáuridos" instead of "baurusúquidos".
  - *Camarillasaurus*: two sentences now repeat the reinterpretation.

The *Atlantosuchus* error led to a new alignment rule: a Spanish sentence may not name a period that its English sentence doesn't name. It also recognises the British spelling Palaeocene, Mississippian and Pennsylvanian, and Paleogene, Neogene and Tertiary. Run over every page, it left out 4 wrong Spanish sentences: *Atlantosuchus*, *Lithornis*, *Presbyornis* and *Antliodus*.
