# Recorded API snapshots for tests and CI

Real responses stored by `paleo.store.RawStore` for the taxa and studies in the
Wikipedia excerpt (`../wikipedia/`), recorded on 2026-11-01:

- `pbdb/` — Paleobiology Database records, **CC BY 4.0** (https://paleobiodb.org).
- `crossref/` — Crossref metadata (free to use); abstracts were never stored.
- `commons/` — Wikimedia Commons file metadata (license, author, URLs); each
  image keeps its own license, shown in the metadata.
- `phylopic/` — PhyloPic node and image metadata; each silhouette keeps its own
  license, shown in the metadata.

Regenerate by re-recording from a real run (see `scripts/seed_fixture_data.py`).
