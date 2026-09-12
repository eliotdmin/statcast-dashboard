# Statcast Breakout & Regression Dashboard

League-wide Statcast pipeline that finds hitters and pitchers whose *results*
have drifted away from their *underlying contact quality*, and projects where
they land the rest of the season.

## Setup (one time)

```bash
cd ~/Projects/statcast-dashboard
pip install -r requirements.txt        # or: conda activate <env> && pip install -r requirements.txt
```

## First run

Start small to confirm everything works before the long backfill:

```bash
python3 run_pipeline.py --year 2026 --skip-pitches
```

That pulls only the season-to-date leaderboards (fast, ~10s) and writes
`output/dashboard_data.json`.

## Pitch-level backfill

Everything beyond the season-to-date leaderboards — rolling trends, count-state
splits, pitch-type analysis, the regression validation — needs pitch-level data.
Start with the recent window:

```bash
python3 run_pipeline.py --year 2026 --days-back 60 --newest-first
```

`--newest-first` means a run you interrupt still leaves you the most useful days.
To extend backward later, just raise or drop the flag — the `ingest_log` table
records every day already fetched, so nothing is re-downloaded:

```bash
python3 run_pipeline.py --year 2026          # the rest of the season
```

**Every column Savant returns is stored**, not a curated subset, because
recovering a column you did not save costs a full re-download. That includes
`balls`/`strikes` (count states), `pitch_type`, `stand`/`p_throws` (platoon),
base-out state, fielding alignment, `delta_run_exp`, and bat tracking where
available. Expect roughly 400MB–1GB of SQLite for a full season. Savant
occasionally adds columns mid-season; appends widen the table rather than fail.

## Testing whether any of this predicts anything

```bash
python3 regression_test.py --year 2026 --windows 15 30 45 60
```

Walks the season in adjacent block pairs and asks whether period-1 xwOBA
predicts period-2 wOBA better than period-1 wOBA does — the dashboard's premise,
tested out-of-sample rather than assumed. Also fits the regression-to-the-mean
coefficient per window length, which is what "short-term vs long-term
regression" means numerically. Read its docstring for the caveats; survivorship
bias is real and it cannot be corrected here.

## Daily refresh

```bash
./refresh.sh
```

To schedule it on macOS, load the launchd job:

```bash
cp com.eliot.statcast.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.eliot.statcast.plist
```

It runs at 11:00 each morning — Statcast data lags about a day, so the previous
day's games are settled by then.

## What the numbers mean

| Field | Meaning |
|---|---|
| `luck_gap` | `est_woba - woba`. How much better the player deserved than he got. |
| `luck_z` | That gap as a z-score vs. this season's qualified players. |
| `outlook` | Sign-corrected `luck_z`. **Positive always means "expect improvement."** For pitchers the sign is flipped, because a pitcher who allowed *less* than deserved has been lucky. |
| `proj_woba_ros` | Shrinkage projection: observed skill pulled toward league average based on sample size. |
| `pct_ev`, `pct_barrel`, `pct_hardhit` | Contact-quality percentiles — the corroborating evidence that a gap is real skill, not noise. |

## Honest limits

- The projection is a **simple shrinkage estimate**, not ZiPS or Steamer. No
  aging curve, no park factors, no playing-time forecast, no platoon splits.
- Expected stats do not know about a hitter's speed. Fast players persistently
  out-hit their xwOBA; that is skill, not luck, and this model will keep
  calling them regression candidates. Same for extreme shift-beaters.
- `MIN_PA` gates are a blunt instrument. Metrics stabilise at different rates.
- Baseball Savant is a public courtesy endpoint, not a contracted API. It can
  change shape or rate-limit without notice.

## Files

- `db.py` — SQLite schema and ingest bookkeeping
- `fetch.py` — incremental Statcast pulls via pybaseball
- `analyze.py` — signals, z-scores, projections
- `run_pipeline.py` — orchestrator, writes `output/dashboard_data.json`
- `selftest.py` — offline math verification, no network needed
