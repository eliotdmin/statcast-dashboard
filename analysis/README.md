# One-off analyses

The studies behind FINDINGS.md and the technical report. Each was written to answer one question
and run once; none is part of the daily pipeline, and several depend on the state of the database
or of other outputs at the time they were run.

They lived in the repo root until 2026-09-23, so paths in DECISIONS.md, FINDINGS.md and the report
name them without this folder (`variance.py`, not `analysis/variance.py`).

Still at the root, because they run every day or are imported by something that does:
`run_pipeline.py`, `refresh.sh`, `deploy.sh`, `blocks_all.py`, `streaks.py`, `matchup.py`,
`breakouts.py`, `reliability.py`, `lines.py`, `fetch*.py`, `history.py`, `audit.py`, `schema.py`,
`db.py`, `report.py`, `publish_report.py`, `make_og.py`, `make_dictionary.py`, `site/mksite.py`.
