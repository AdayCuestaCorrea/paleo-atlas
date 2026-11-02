"""GBIF fossil specimens -> PBDB genera: one transformation, two engines (§7, Phase 3).

``spec`` defines the job; ``duckdb_job`` and ``spark/jobs/gbif_reconcile.py`` implement
it and must produce the same extract, so the benchmark compares like with like.
"""
