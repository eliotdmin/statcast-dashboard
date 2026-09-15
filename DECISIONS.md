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

## D17 — Grade every forecast against the noise ceiling, never against 1.0
**2026-09-12.** At one month of playing time the target is mostly coin flips: an oracle knowing every
hitter's true talent exactly scores R2 = 0.186 at 60 PA. Reporting "R2 = 0.06" without that
denominator makes a model that captures a third of the available signal look broken. Every predictive
result in this repo reports the ceiling alongside it, computed from the pair identity
`E[(w1-w2)^2] = sigma^2*(1/pa1+1/pa2) + var(drift)`.

## D18 — Never explain an outcome residual with another outcome rate
**2026-09-12.** Regressing wOBA-minus-xwOBA on ground-ball-single rate produced R2 = 0.246 and meant
nothing: a ground ball that finds a hole is both variables at once. Predictors for any residual are
split into **ante-hoc** (properties of the batted ball and context, knowable before it lands) and
**outcome-derived**, and the two R2 values are always reported apart. Sanity test: if the proposed
explainer's own split-half reliability is near zero, it is luck, and luck cannot explain luck.

## D19 — Playing time is a predictor, and must be ablated, never silently included
**2026-09-12.** Plate appearances alone out-predict xwOBA (0.032 vs 0.015). It is real information —
a manager's private read on health and matchups — but it is not a hitting skill. Any model reporting
predictive performance runs with and without it and reports both.

## D20 — Every predictive claim is benchmarked against Marcel before it is published
**2026-09-12.** "Beats xwOBA" is not an achievement; xwOBA is a descriptive statistic, not a
forecaster. Marcel — 5/4/3 weighted seasons, regression to the mean, age bump — is the floor.
A model that does not clear it has shown nothing, and on this dataset none of ours does at the
one-month horizon. Any future forecasting result in this repo reports Marcel alongside it, with the
baseline's constants **tuned on training data** and the comparison **bootstrapped**, because a
point-estimate win with n in the hundreds is not a win.

## D21 — Suspiciously good baselines mean leakage, not insight
**2026-09-12.** Season-level Marcel scored R2=0.575 and the tuner chose "barely regress". Both were
symptoms of the history window including the season being forecast. The rule: when a *baseline*
jumps far above its published performance, or when tuning pushes a regression constant toward zero,
stop and audit the time cutoff before interpreting anything.

## D22 — Regress harder than feels right; it is the only free lunch found so far
**2026-09-12.** Changing Marcel's regression constant from the classic 1200 to a tuned 3000 moved
season-level R2 from 0.0745 to 0.1640 — a bigger improvement than every Statcast feature in this
repo combined. The past-to-future correlation of a hitter's weighted record is only **0.40**, so the
right move is to keep ~40% of a hitter's deviation from league average and discard the rest, even
with 2,000 PA of history. Any new projection in this repo starts by tuning the shrinkage, and only
then considers features.

## D23 — Check a mechanism's MAGNITUDE before building on it
**2026-09-12.** The ground-ball/error mechanism is real, correctly identified and well evidenced,
and it improves projection by nothing. A one-line arithmetic check — per-unit effect x spread of the
driver x exposure, compared against the sd of the thing being explained — showed it accounts for
7.3% of the gap's spread. **Run that check before writing the model, not after.**

## D24 — Never compute a public metric from a raw column without an acceptance test
**2026-09-12.** `woba_value` looks like wOBA and is not: it credits reached-on-error, fielder's
choice and dropped third strikes as reaches. Four days of analysis inherited a 9-point inflation,
and one published finding was entirely an artifact of it.

**Rule.** Any metric this repo computes from pitch-level columns is first reconciled against an
independent published version of the same metric for the same players — `expected_stats.woba` for
wOBA, and the equivalent leaderboard for anything else. The check is two lines and it is not
optional. Prefer the downloaded value outright wherever the unit of analysis is player-season;
compute from pitches only at units no leaderboard publishes (per count, per batted ball, per month).

**Diagnostic.** A systematic offset with correlation ~0.99 against the published version is a
definition mismatch, not noise. Chase the events, not the arithmetic.

## D25 — "% real" is a property of the column, not of the player's number
**2026-09-15.** The Stretch Finder chip that reads `72% real` means
`rho = var(true)/var(observed)` *across players* at that sample size, projected from the measured
half-season split-half by Spearman-Brown. It says that if you re-ran the same six weeks, about 72%
of the variance in that percentile ranking would come back. It does **not** mean any individual
number is 72% accurate, and it is not a confidence interval.

**Consequence adopted.** Fading a bar is not enough — a faded bar still shows the raw percentile,
and readers read the bar. The tool now draws the *shrunk* percentile `50 + rho x (raw - 50)` as the
solid bar and the raw percentile as a dashed outline behind it. The gap between them is the part
the data does not support. Anything this repo publishes with percentile bars does the same.

## D26 — "Is it noise?" and "is it big?" are two questions; ship both
**2026-09-15.** `profile.py` reports `delta_z` (delta over the standard error sampling noise alone
would produce) *and* `delta_sd` (delta in units of the between-player spread). They come apart in
both directions and either one alone misleads:

- Arm angle is measured with reliability ~0.999. A 0.9-degree drift clears the noise bar at
  z = 2.5 and is 0.07 sd of the league — statistically unambiguous, practically nothing.
- Dylan Cease's strikeout rate fell 4.2 points over 242 batters faced: z = -1.06 (indistinguishable
  from noise) but 0.6 sd (a change anyone would notice if it were real). The honest sentence is
  "he may well have changed this much and this sample cannot tell you," which is more useful than
  either "significant" or "not significant."

**Rule.** No single-number significance verdict ships without its effect size beside it.

## D27 — The input-corroboration hypothesis is dead at every resolution
**2026-09-15.** Tested at 15-, 30-, 45- and 60-day windows, fit 2023-2025 and scored on 2026. Adding
a reliability-weighted composite of within-player input changes to a model that already has wOBA and
xwOBA (current and prior) never produces a confidence interval that excludes zero:

| window | M2 (xwOBA) | M4 (+ input delta) | M4 - M2 | 95% CI |
|---|---|---|---|---|
| 15d | .0222 | .0302 | +.0079 | [-.0023, +.0178] |
| 30d | .0335 | .0301 | -.0034 | [-.0176, +.0097] |
| 45d | .0385 | .0351 | -.0033 | [-.0238, +.0166] |

The 15-day hint is in the direction the theory predicts (corroboration should matter most where the
results sample is smallest) and is not significant. **Do not build on it without a fresh holdout.**

The paradox to keep in mind: those same input changes have window-to-window correlations of +.37 to
+.58 and 47% of moves past |z| = 2 hold half their magnitude into the next window. They are real and
persistent and they do not move next month's wOBA, because next month's wOBA is barely movable.

## D28 — 2026 is no longer a holdout; it is a development set
**2026-09-15.** The 2026 slice has now been scored dozens of times across this project: four model
specifications at four window lengths, two player types, several PA floors, and the streak subgroup
analysis. Each look is a degree of freedom. The honest name for what 2026 has become is a validation
set, and any figure quoted from it should be read as optimistic by an unknown amount.

**Rule going forward.** See `PREREGISTRATION.md`. No further model selection touches 2026. The next
genuinely clean evaluation is 2027, and the predictions to be scored against it are written down now,
before the data exists.
