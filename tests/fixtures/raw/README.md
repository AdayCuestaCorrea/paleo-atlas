# Recorded API snapshots for tests and CI

Real responses stored by `paleo.store.RawStore` for the taxa and studies in the
Wikipedia excerpt (`../wikipedia/`), recorded on 2026-11-01:

- `pbdb/` — Paleobiology Database records, **CC BY 4.0** (https://paleobiodb.org).
- `crossref/` — Crossref metadata (free to use); abstracts were never stored.
- `commons/` — Wikimedia Commons file metadata (license, author, URLs); each
  image keeps its own license, shown in the metadata.
- `phylopic/` — PhyloPic node and image metadata; each silhouette keeps its own
  license, shown in the metadata.
- `gbif/` — the record of GBIF download 0023284-261023074918325
  (https://doi.org/10.15468/dl.8v87yz, 2026-11-02) and a slice of its reconciled
  extract: the genera of the PBDB catalog fixtures, the institutions in their top
  lists, all countries and the 50 largest unmatched names. Aggregates only (counts
  and 0.5° cells), no single record; cite the DOI.
- `news/` — 9 articles from the news feeds (F9), recorded on 2026-11-07: headline,
  link, date and the feed's own summary, from outlets whose terms allow it
  (ScienceDaily RSS terms, The Conversation CC BY-ND 4.0, SINC CC BY 4.0).

Regenerate by re-recording from a real run (see `scripts/seed_fixture_data.py`).

`../derived/` holds one generated narrative page (facts + EN/ES texts for
*Spinosaurus mirabilis*) so CI can build the text models. Its quotes are
Wikipedia excerpts (CC BY-SA 4.0); quotes from abstracts are never stored there.
