# Gold set: reference taxon pages

Twelve hand-written reference pages used to evaluate the narrative pipeline
(decision A18 in `ALCANCE.md`). Each file has:

- **facts** — atomic statements, each with the id of its source chunk and a
  verbatim `quote` from it;
- **texts** — an English page written from those facts and its Spanish
  adaptation, sentence by sentence, every sentence citing its facts.

They follow exactly the pipeline's format and pass exactly the same checks
(`uv run paleo eval validate-gold`): verbatim quotes, numbers and names taken
from the facts, no copied prose, no repeated facts, ES aligned with EN.

| Taxon | Why it is in the set |
|---|---|
| *Spinosaurus mirabilis* | well documented; the lifestyle debate only appears in the Spanish article |
| *Asio pythiotus* | no Wikipedia article at all |
| *Ctenosuchus*, *Tromerosaurus* | a correction to the naming study was published |
| *Vegavis geitononesos* | the article is about the genus and the Spanish one is outdated |
| *Cryptarcus*, *Rexarthuria* | new genus for a species named long ago |
| *Antusuchus* | the sources contradict each other on its age |
| *Crocodylus lucivenator* | long technical article; easy to overstate (it did not hunt Lucy) |
| *Carinthiasuchus*, *Bavaricarbo*, *Haolong* | different groups, ages and article lengths |

**Authorship and licenses.** Written by Claude (Opus 5.5) in an interactive
session on 2026-11-01; `reviewed_by_user` records the human review. The
`quote` fields are verbatim excerpts from Wikipedia articles (CC BY-SA 4.0,
contributors listed in each article's history) and from the Paleobiology
Database (CC BY 4.0); no quotes come from copyrighted abstracts.
