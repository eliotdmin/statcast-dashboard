# Decisions

Why the project is built the way it is. Each entry records the decision, what it
was chosen over, and what would make it wrong. A decision nobody can reconstruct
gets re-litigated every few months; a decision with its reasoning attached can be
reversed deliberately.

Append new entries at the bottom. Supersede rather than delete.

---

### D1. Store every column Savant returns, not a curated subset

Recovering a column you did not save costs a full re-download — hours, and a
dependency on a courtesy endpoint that can change shape. Storage is the cheap
side of that trade at roughly 500 MB per season.

*Rejected:* selecting the ~20 columns the dashboard uses.
*Would be wrong if:* a season exceeded what the machine can hold, which is not
close — four seasons is 1.8 GB against 236 GB free.

### D2. Never version the database; version what regenerates it

`data/` is gitignored. GitHub rejects files over 100 MB and the database is
1.8 GB, but the real argument is that it is *derived* data, fully reproducible
from `backfill.py` in about 2.5 hours. `ingest_log` records every day fetched,
which is what makes that reproduction exact rather than approximate.

*Rejected:* Git LFS.
*Would be wrong if:* the upstream source disappeared, at which point the database
becomes irreplaceable primary data and needs a real backup — not git.

### D3. `schema.yaml` is the single source of truth

Applicability conditions and plausible ranges lived in `audit.py` as Python
dicts while the same facts lived in prose in the markdown. Two hand-maintained
copies of one set of facts drift, and the documentation is the copy that drifts
silently. `audit.py` reads its conditions from the YAML; `make_dictionary.py`
renders the markdown from it. **`DATA_DICTIONARY.md` is a build artifact — edits
to it are lost on the next build.**

The audit fails on any database column with no schema entry. That is deliberate:
`db.append_pitches` widens the table when Savant adds a column mid-season, and an
undocumented column is a metric nobody has decided how to treat.

### D4. Exclude the postseason; keep spring training but filter it

Every metric here is a regular-season qualified-player statistic, so the
postseason is a different population — different rosters, different bullpen
usage. `season_days` ends at the regular-season finale.

Spring training is different: the backfill windows start early on purpose, to
catch the Seoul (2024) and Tokyo (2025) series, and that also pulls in ~50k
spring pitches. Those rows stay in the table and are filtered downstream with
`game_type = 'R'`. The audit check for spring rows is **permanently red on
purpose** — it is a standing reminder that the filter is mandatory, not a bug to
fix by deleting rows.

### D5. Measure nulls against applicability, never overall

`launch_speed` is not "missing" on a called strike; there was no batted ball.
Reporting structural and real nulls together produces a table where `events`
looks 75% missing and a genuine 4% tracking gap is invisible next to it. Every
column with an applicability condition is audited within that condition, and the
report states the condition it used.

### D6. Assertions live in the audit; corrections live in the schema

The three convention findings in `FINDINGS.md` all came from integrity checks
that asserted textbook behaviour and failed. That is the intended workflow: write
the check as an assertion, let the data refute it, then correct the schema.

**If a check fails, the schema is wrong until proven otherwise, not the data.**

Known exceptions are recorded *with their reason* — see `SCHEDULE_EXCEPTIONS` in
`audit.py`. A permanently red check with no explanation trains you to ignore the
audit, which is worse than not having it.

### D7. Report `outlook_adj` alongside `outlook`, never instead of it

The speed adjustment is a hypothesis, not an improvement. Which signal predicts
better is a question for `regression_test.py`. The fitted coefficient and R² are
written into the payload so the assumption can be checked rather than trusted.
On one season the effect is not distinguishable from zero — see `FINDINGS.md`.

*Would be wrong if:* the four-season refit shows a substantial coefficient, at
which point `outlook_adj` should replace `outlook` rather than sit beside it. If
it stays this small, delete it.

### D8. The user runs git; Claude proposes commits

The sandbox shell cannot delete files, so `git add` creates `.git/index.lock` and
cannot remove it, leaving the repo locked with a misleading "another git process
is running" error. Beyond the mechanics, the commit is a unit of review: Claude
drafts the change and the message, the user reads the diff and pushes.

Work lands on a branch, never directly on `main`.

*Corollary:* automate the checks rather than the eyeballing. A pre-commit hook
running `selftest.py` is stronger control than reading a file list, because it
catches the failures a file list cannot show.

### D9. Never write to the database through the Cowork mount

A `CREATE INDEX` issued from the sandbox failed mid-write with `disk I/O error`
and left the 1.8 GB file structurally corrupt — under-reporting its own row count
by 23,523 pitches with no error raised anywhere. Reads through the mount are
fine; writes are not. Copy to sandbox-local scratch and work on the copy, or run
on the Mac.

`refresh.sh` runs `PRAGMA quick_check` after every refresh so this is caught in
hours rather than by accident.

### D10. The repo lives in `~/Projects`, not `~/Desktop`

macOS TCC protects `~/Desktop`, `~/Documents` and `~/Downloads`. A script run by
launchd executes as `/bin/bash`, which has no access, so the scheduled refresh
failed before writing a single log line — while the same script run by hand
worked, because Terminal has been granted access. That asymmetry is what made it
so hard to diagnose, and it is why the job silently did nothing for weeks.

*Rejected:* granting Full Disk Access to `/bin/bash`, which hands unrestricted
disk access to every shell script on the machine, permanently, to fix one job.

### D11. Machine-specific paths go in `.refreshrc`, not the plist

The launchd job needs an absolute interpreter path, and launchd does not read a
shell profile. `.refreshrc` is gitignored and generated with
`echo "STATCAST_PYTHON=$(which python3)" > .refreshrc` from the shell where the
pipeline already works — capturing the right answer instead of guessing it, and
keeping a per-machine path out of a committed file.

### D12. Store what is expensive to fetch; fetch what is cheap at runtime

Pitch-level data takes ~2.5 hours and 685 requests: store it, log it, never
re-fetch. Sprint speed, expected stats and batted-ball leaderboards take seconds:
pull them fresh each run. The constraint on adding more sources is not disk — the
leaderboards are all under 100 MB combined — it is that every stored table is a
table that must be documented, audited and reconciled.

### D13. Auto-write the archive; keep a human on the core

`docs/log/` is append-only, dated history — a mediocre entry there is harmless,
because it records what happened rather than claiming what is true. `FINDINGS.md`
and `DECISIONS.md` are different: future sessions read them and trust them, so a
wrong entry propagates silently.

The asymmetry is the argument. A missing entry is recoverable — git history and
the session transcript are both still on disk. A wrong entry is not, because
nothing downstream questions it. So automation is welcome up to the point of
writing to the core, and a person approves that step.

This is not a claim that a model cannot write a good log. It is that nothing
unreviewed should write to the file everything else trusts, which is the same
reason code review exists in codebases with good test suites.

*Rejected:* a `SessionEnd` hook or scheduled job that distills the transcript
straight into `FINDINGS.md`. Also rejected on mechanics: `SessionEnd` hooks get
~1.5 seconds and cannot invoke a model at all — `prompt` and `agent` handlers are
documented only on other events.
*Would be wrong if:* the log stops being written at all, at which point an
imperfect automatic entry beats nothing. Revisit if two months pass with empty
`docs/log/`.

### D14. Hooks gather; skills decide

`SessionStart` runs a shell script that prints recent commits, carried-over open
questions and uncommitted changes. That is mechanical work with a deterministic
answer, and a hook does it perfectly and for free.

Judging what a session meant is not mechanical, and no shell command can do it.
That belongs in `/project-log`, invoked deliberately.

*Rejected:* wiring a `SessionEnd` hook for symmetry. It would have produced a
list of commits `git log` already gives you, while the part worth having stayed
manual regardless.

## D15 — Never measure a season-over-season change relative to a Statcast-provided reference column
**2026-09-11.** `sz_top`/`sz_bot` changed definition in 2026: per-pitch operator estimate (353,643
distinct values in 2025) became a per-batter formula (390 distinct values, one per batter), 0.22 ft
lower on average. An analysis of the called zone measured in `sz_top` units reported the top of the
zone expanding; measured in absolute feet it contracted sharply. Same data, opposite conclusion.

**Rule.** Anything compared across seasons is measured in units the rulebook fixes — feet off the
ground, feet off the centre of the plate, mph — never in units a data provider can redefine.
Provider-derived columns (`zone`, `sz_top`, `sz_bot`, `launch_speed_angle`, `estimated_*`) are fine
*within* a season and suspect *across* seasons until checked.

**Guard.** `audit.py` must gain a schema-drift check: per column per season, mean / sd / null rate /
**distinct-value count**, flagging any year-over-year jump past a threshold. The distinct-count
column alone catches this instantly (353,643 -> 390). This is the second field to silently change
meaning between seasons; a mechanical check is cheaper than catching it by eye a third time.

## D16 — Every displayed change is shrunk and expressed in league true-change SDs
**2026-09-11.** `calibrate.py` writes `output/calibration.json`; `profiles.py` loads it and reports
`d`, `shrunk = d * var_true/(var_true+se^2)`, and `z = shrunk/sd_true` for every metric.
Reports rank by |z|, not by |d| and not by |d/se|. Significance tests against zero and sample size
controls the answer; the calibration tests against how far players actually move, which is the
question. A report generated without `calibration.json` prints a warning rather than silently
falling back to raw changes.
