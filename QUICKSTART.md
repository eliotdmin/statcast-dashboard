# Quickstart — opening this repo in an IDE

Everything here runs as plain Python against a local SQLite file. No services,
no notebooks, no build step.

```bash
cd ~/Projects/statcast-dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## The one thing that is not in git

`data/statcast.db` is **1.8 GB** and gitignored. Cloning this repo elsewhere gets
you the code and the knowledge files but no data. To rebuild it:

```bash
python3 backfill.py --years 2023 2024 2025 2026     # hours, unattended
python3 verify_recovery.py                          # confirm row counts match ingest_log
python3 audit.py                                    # coverage + 12 integrity checks
```

Or copy the file directly from the machine that already has it — far faster.

## Where to start reading

`CLAUDE.md` sets the reading order and is picked up automatically by Claude Code.
In short: `DECISIONS.md` (D1–D24, the standing rules) → `FINDINGS.md` (dated
results, including the retractions) → `DATA_DICTIONARY.md` (generated from
`schema.yaml`; edit the YAML, not the markdown).

## Script map

| script | what it does | runtime |
|---|---|---|
| `backfill.py` / `fetch.py` | pull pitch data and leaderboards into SQLite | hours |
| `audit.py` | coverage, missingness, 12 integrity checks | ~2 min |
| `extract_monthly.py` | build the 10,287-row hitter-month panel as CSV | ~2 min |
| `predict.py` / `predict2.py` | noise floor, horse race, model zoo, ablations | ~10 min |
| `marcel3.py` / `marcel4.py` | Marcel benchmark (leak-free) and segment analysis | ~5 min |
| `counts.py` | wOBA and xwOBA by count reached | ~2 min |
| `woba_fix.py` | **the corrected wOBA numerator + acceptance test** | ~3 min |
| `pitchers_gap.py` | pitcher wOBA-against vs xwOBA-against | ~3 min |
| `mkmachine.py` / `report_profiles.py` | render the HTML artifacts | seconds |

## Two traps that have already cost real time

1. **`woba_value` is not wOBA** (D24). It credits reached-on-error, fielder's
   choice and dropped third strikes as reaches. Use the corrected numerator in
   `woba_fix.py`, and reconcile any computed metric against the published
   leaderboard in `expected_stats` before trusting it.
2. **`sz_top` changed definition in 2026** (D15). Anything compared across
   seasons must be measured in absolute feet, not relative to a provider column.

## Working alongside Cowork

The same repo is driven from a Cowork session. Both write to `FINDINGS.md` and
`DECISIONS.md`, so avoid running long Cowork jobs and local edits on the same
branch at the same time. Simplest split: branch locally for anything
experimental, let Cowork own `data-integrity`.
