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

## D29 — Deploy `web/`, never the repo root
**2026-09-17.** `data/statcast.db` (1.8 GB) lives at the repo root. A `vercel deploy` run from there
tries to bundle it and fails outright on Vercel's 100 MB single-file limit. `web/` is the actual
deployable unit — it has its own `vercel.json` — and the repo root should never be linked as a
Vercel project directory.

**Symptom if this is forgotten again:** `Error: File size limit exceeded (100 MB)` immediately on
deploy, with no other explanation.

## D30 — `web/vercel.json` pins `"framework": null`; `web/.vercelignore` excludes `serve.py`
**2026-09-17.** The first (mistaken) deploy attempt off the repo root — surrounded by dozens of
top-level `.py` analysis scripts (`audit.py`, `backfill.py`, etc.) — caused Vercel's framework
auto-detector to guess "Python" and save that as the project's **Framework Preset**, a setting that
persists server-side across deploys rather than being re-detected fresh each time. Every subsequent
deploy, even a correct one scoped to `web/`, kept failing with `No python entrypoint found` because
of that stale setting, not because of anything in `web/` itself.

`web/serve.py` (the local-dev-only stand-in for the Vercel function, needs neither Node nor a Vercel
login) was also part of what triggered the original misdetection, so it is now excluded from the
upload via `.vercelignore` — though that alone does not fix a Framework Preset already saved on the
Vercel side; `"framework": null` in `vercel.json` is what overrides it going forward.

**Would be wrong if:** Vercel changes framework detection to stop persisting across deploys — until
then, if `No python entrypoint found` resurfaces, check the Framework Preset under
`vercel.com/edm16/statcast-dashboard/settings` directly rather than re-diagnosing from scratch.

## D31 — `/api/summary` streams as newline-delimited JSON, not raw SSE passthrough
**2026-09-17.** Both backends (`api/summary.js` on Vercel, `serve.py` locally) now request
`stream: true` from Anthropic and relay it to the browser as three line shapes: `delta` (a chunk of
prose), `error`, and one terminal `done` carrying model/usage/cost. The browser gets one parser
regardless of which backend answered it, and regardless of live vs. the no-key stored-fallback mode
(which now emits the identical protocol — one `delta` with the full canned text, then `done`).

**Why not relay Anthropic's SSE directly:** it would make the browser understand Anthropic's event
framing itself, and usage arrives split across two different event types (`message_start` has
input/cache tokens, `message_delta` has cumulative output tokens) — accumulating that server-side and
reporting it once, in `done`, keeps the client simple.

**Would be wrong if:** Anthropic's streaming usage-reporting shape changes.

## D32 — Shipped `/api/summary` with no request auth, on a key already exposed in a chat transcript
**2026-09-17.** The `ANTHROPIC_API_KEY` in production is the one that appeared in plaintext in a
Claude Code session transcript earlier the same day. The user was told twice — once when it first
appeared, once again when the endpoint's lack of auth meant *any visitor to the deployed site*, not
just whoever saw the transcript, can spend against it directly — and explicitly chose not to rotate
it or add auth, judging the deploy low-stakes and non-commercial.

**Rejected:** rotating the key (near-zero cost, recommended, declined); adding request auth beyond
the existing 12-req/min per-IP throttle in `api/summary.js` (not implemented).

**Would be wrong if:** billing shows spend inconsistent with expected personal/demo traffic, or the
dashboard gets meaningfully more visitors than that — rotate and add real auth at that point, not
after.

## D33 — The summary never auto-generates; stale reads are flagged instead
**2026-09-18.** Briefly, the summary regenerated itself 600 ms after every filter change and tab
switch. Reversed the same day: every call costs tokens, the endpoint has no auth (D32), and scrubbing
through filters would fire calls nobody reads. Now a call happens only on an explicit click. Each tab
remembers the `title|sub` signature of the evidence its last read described (`node._genKeys` in
`app.js`); when the filters change, the evidence table updates live but the old prose stays on screen
under a "filters changed" banner until the reader clicks Regenerate. Text that quietly stops matching
the screen was the original bug this replaces.

The default model is `claude-haiku-4-5-20251001` (override with `PROFILE_MODEL`). The prose is short
and tightly constrained by `prompts/base.md`, so speed mattered more than the quality margin.

**Would be wrong if:** Haiku drifts on the `base.md` guardrails (calling a `noise` row a change,
regression talk from the wOBA−xwOBA gap). Spot-check live output before trusting it.

## D34 — Red and blue mean direction only; nothing else on the site uses them
**2026-09-18.** Red = better than average / went up; blue = worse / went down. The `held` chips in the
Change log used to be blue for "held" and red for "didn't hold", a third meaning for the same two
colors on the same page. They are now neutral (dark fill = held ≥ 50%, outline = didn't). Any new
status indicator should follow the same rule.

## D35 — Jargon is defined once per page, not at every occurrence
**2026-09-18.** Table-header terms (`z`, `sd`, `% real`, `held`, `carry`, `reliability at n₀`)
get a tap/hover definition via `term()` in `app.js`, one per table header. The `% real` chip
repeats on every percentile row, so it is defined once in the legend instead. Keep the set small:
a term earns a popover only if it appears in the UI with no room to explain itself.

## D36 — Supersedes D25's drawing rule: raw percentile shown only when shrinking moves it 5+ points
**2026-09-18.** D25 drew every row twice (solid = shrunk, dashed outline = raw). On the 85–98%-real
swing and discipline rows the two are indistinguishable, so the outline was clutter on most of the
page and the distinction only mattered on a few rows. Now the solid bar is the shrunk percentile
everywhere; where |raw − shrunk| ≥ 5, a hatched band in the row's color extends to the raw value
and the number reads "74 was 98". D25's substance is unchanged: the headline bar is always the
shrunk one, and the raw figure is never shown alone.

**Would be wrong if:** readers miss that small shrinks happen at all. Lower the threshold, don't
bring back the outline on every row.

## D37 — The Player check verdict is conservative by rule, and never says buy or sell
**2026-09-18.** The card (`renderCard`/`cardVerdict` in `app.js`) compares a player's last 2/4/6
weeks with his strictly-earlier season and returns one of: too early (< 25 PA per half-month in the
window), no baseline, steady (results within ±.040), hot, or cold. "How much will stick" comes
from the What-carries model on its own 30-day window when the player qualifies, otherwise from the
measured streak ladder (14% / 27% / 43%, FINDINGS 2026-09-18; hitters, hot streaks only). Below
35% carry the verdict says "most of it is likely noise" / "expect most of it to come back".

Two rules are deliberate: a real change in an input (swing, stuff) is listed and pointed to but
never moves the verdict (D27), and the carry percentage is only shown for gaps of ±.040 or more,
because as a ratio it is meaningless on a small gap (a −.022 gap produced "−185% carry").

**Rejected:** buy/sell language, and letting a confirmed swing change upgrade a hot streak.
**Would be wrong if:** the 2027 test of S32 (hard-hit-backed streaks) or a pitcher breakout study
shows an input that does predict persistence — then it earns a place in the verdict.

## D38 — The breakout study gets its own tab, and its case studies are picked by rule
**2026-09-18.** The two-week breakout result (FINDINGS 2026-09-18) now has a Breakouts tab
(`#p-break`), fed by a static file: `python3 breakouts.py --export web/data/breakouts.json`. It
shows the stick-rate ladder (2 wk / 30 d / 45 d), earned vs. lucky with the bootstrap CI, 2026 in
grey and unpooled, and nine case studies. It is hitters only and ignores the Type/Season menus,
and it says so on the tab.

The case studies are chosen **by a fixed rule**: in each of 2023, 2024 and 2025, the three
distinct hitters with the largest xwOBA jump during a qualifying two-week hot streak. In other
words, the most convincing "he's earned it" cases, whatever happened next. Choosing
memorable cases by hand would let the outcome pick the examples, and a page arguing that
streaks mislead can't do that itself.

**Rejected:** hand-picked stories (e.g. a famous breakout that stuck next to one that didn't),
and a balanced set of stuck vs. faded cases, which would misstate the base rate.
**Would be wrong if:** the export's rule starts surfacing the same player repeatedly across
seasons, or readers take nine cases as the evidence instead of the ladder above them.
Re-run the export whenever `breakouts.py` thresholds or the shards change; the file doesn't
refresh itself.

## D39 — The Breakouts tab defaults to a career baseline with a significance filter
**2026-09-18.** At the user's request, the Breakouts tab now leads with streaks measured against
career-to-date wOBA (since 2023, ≥ 300 PA), hot **and** cold, and keeps only windows with
|z| ≥ 2. The noise counted is from both the window and the baseline, with the per-PA variance
0.2258. The original earlier-season study (D38) is still one menu choice away, because the landing
page and the Player check quote its numbers (14% / 27% / 43%), and those figures stay correct for
the question they answer.

Case studies in the career view follow the same kind of rule as D38: per season (2024, 2025) and
direction, the three distinct hitters with the largest xwOBA move in the streak's own direction.

**Rejected:** replacing the earlier-season study outright. That would have left the landing page
and the card quoting numbers the tab no longer shows. Also rejected: a fixed-size threshold
(e.g. ±.080) for the career view. It would ignore that 35 PA and 105 PA carry very different
noise.
**Would be wrong if:** the 2015–2022 backfill lands. Then "career" should mean the real career,
and the 2023 season can join the headline years.

## D40 — Player check lists who is hot or cold now, using the card's own comparison
**2026-09-18.** The Player check tab opens with a "Who's hot or cold right now" board: every player
whose last 2/4/6 half-month blocks (the card's "Recent stretch" menu) sit away from his own
earlier-season rate, by default only where |z| ≥ 2 (sampling noise in both the window and the
baseline, per-PA variance 0.2258), or optionally any move of .040+. Minimums match the card: 25
PA per half-month in the window and 100 before it. Clicking a name opens his card below.

It deliberately uses the **earlier-season** baseline, not the career baseline of D39. The card's
verdict is built on the earlier-season comparison, and a name on the list must never open a card
that calls him "Steady".

**Rejected:** a career-baseline list, which would disagree with the card it links to.
**Would be wrong if:** the card's verdict moves to a career baseline. Then the list moves with it.

## D41 — The Player check summary is given the card's verdict and told to explain it
**2026-09-18.** Until now the card's AI summary used the Percentiles evidence (metric rows only),
with the base rule "prefer the measurement over the outcome". It never saw the card's verdict, so
it could contradict it. Reported case: Seiya Suzuki's card said "Cold — and more of it may stick
than usual" while the summary said his contact was more stable than his results. The card now has
its own view (`card`, `prompts/card.md`). Its evidence carries the verdict headline, explanation
and carry-model numbers (also shown in the evidence panel's note), and the prompt says to explain
the verdict and name any tension, never to overrule it.

**Rejected:** dropping the summary from the card, or loosening the verdict to match the summary.
The verdict already includes xwOBA through the carry model, so the rule-based call is the more
complete one.
**Would be wrong if:** readers find the summary merely restating the headline. Then it should
lead with the tension instead.

## D42 — Hot or cold requires two tests: vs. earlier this season AND vs. his usual level
**2026-09-19.** At the user's direction ("a great player and a new player should not be treated
the same"), the Player check verdict and the hot/cold list now call a stretch hot or cold only if
it differs from **both** (1) his rate earlier this season (unchanged, D37/D40) and (2) his *usual
level* from prior seasons, with |z| ≥ 2 against the second.

*Usual level* (`usualLevel` in `app.js`, data from `history.py` → `web/data/history.json`): his
last three prior seasons (Savant season expected-stats leaderboards), weighted 1 / .8 / .6 by
recency (Marcel's 5/4/3), then regressed toward that season's league wOBA by k = σ²/τ² PA. τ is
**measured** in history.py over full-time seasons (≥ 300 PA/BF): hitters .026, pitchers .025, so
k ≈ 330 / 370. The level's uncertainty, τ·sqrt(k/(n+k)), enters the z along with window noise. A
player with no prior MLB season gets the league mean with sd τ. So it takes a bigger move to
call a newcomer hot or cold, and a star climbing out of a slow start reads "back to his usual
level", not "hot".

Passing only test 1 now gives a neutral verdict ("Better than earlier this season — but not
beyond his usual level"). The hot/cold list names these players in a footnote.

**Rejected:** a raw career average (no regression): it treats 150 PA and 1,800 PA the same.
Also rejected: one pooled baseline mixing this season and prior seasons, which can't say *which*
comparison a stretch fails.
**Would be wrong if:** aging makes the prior level systematically stale (no age term yet). Or
if τ from full-time seasons (a selected population, smaller than the .035 across all hitters)
over-regresses part-timers. Also: the Breakouts study, What carries and the Change log still use
the earlier-season baseline only; re-running Breakouts with the dual test is the natural next
step once the 2015–2022 history is loaded (`python3 fetch_history.py`).

## D43 — The product is called True Talent, not Stretch Finder
**2026-09-20.** Renamed across the site, the build scripts and the docs. "True talent" is the
sabermetric term for the quantity every view on the site is actually estimating — what a player
is, underneath the sample noise — so the name states the product's claim instead of describing
its interface.

Names rejected: *Baseline* and *Regression* collide with vocabulary the site already uses in
prose ("his earlier-season baseline", "regressed toward league average"), which would have made
sentences ambiguous. *Ballast* and *Warning Track* read as metaphor first and require explanation.

Not renamed: this repository directory (`~/Projects/statcast-dashboard` is hard-coded in the
launchd plist — see CLAUDE.md), the Vercel project `edm16/statcast-dashboard`, and its
`*.vercel.app` URL. Renaming either breaks the scheduled refresh or the live link for no user-
visible gain; the displayed name is what readers see. Also left alone: the dated entries in
DECISIONS.md and the artifact rows in HANDOFF.md, which record what things were called when
they were built.

**Would be wrong if:** a custom domain is bought. Then the domain should match the display name.

## D44 — Supersedes D43: the product is called Statcast Reality Check
**2026-09-20.** "True Talent" lasted a few hours: it is a term of art, which makes it read as
jargon to anyone outside baseball analytics, and as a brand it claims more than the site
delivers. The name is now literal about the subject with a little stance about the treatment.

Consequences beyond a string swap:
- The masthead chip that read `STATCAST` was removed. The name already says it, and the pill on
  the right of the masthead already carries `2023–2026` (or the build time, in the app).
- The app's page title lost its doubled word: now "Statcast Reality Check — shrunk to what is
  real", not "… — Statcast, shrunk to what is real".
- The report downloads as `statcast-reality-check-technical-report.html`.
- `make_og.py` sets the wordmark and a `2023–2026` chip, so `web/og.png` is rebuilt by re-running it.

Everything D43 said about what is *not* renamed still holds: the repo directory, the launchd
plist path, and the Vercel project stay `statcast-dashboard`.

## D45 — `site/` was rebuilt from `web/`, and the build now resolves its own paths
**2026-09-20.** Two sessions of work (the Player check and Breakouts tabs, D37–D42; the NDJSON
streaming transport, D31; the landing-page redesign; the D44 rename) had been written straight
into `web/`, which is build output. `site/` could not regenerate any of it: `site/body.html` had
four tabs against the deployed six, and the strings `p-card` and `p-break` appeared in no tracked
file. Running `python3 site/mksite.py` would have silently deleted the newest work in the repo.

The fix was to invert the build rather than re-type the output. `mksite.py` turns `body.html`'s
script into `app.js` through sixteen ordered literal `str.replace` calls, so the chain inverts by
walking it backwards with the arguments exchanged. Everything else — the CSS split across
`head.html`, `mkmock.py` and `SITE_CSS`, the prompts, `api/summary.js`, the landing page — is a
literal that could be lifted from the output and put back in its source.

**Acceptance test, and the only one worth having here:** build `site/` and compare against a
snapshot of `web/` taken before any change. All sixteen generated files came back byte-identical.
`addendum.html`, which had no generator at all, is now produced from the shared chrome and differs
from the hand-made file only by one HTML comment and three blank lines; normalising whitespace and
comments makes it identical. The two artifact builds (`mkdash.py`, `mkmock.py`) were re-run and now
carry six tabs, having silently shipped four.

Three latent bugs surfaced on the way and are fixed:
- **`mksite.py` read its inputs relative to the caller's cwd.** `python3 site/mksite.py` from the
  repo root — the command HANDOFF.md documents — died on `open("head.html")`, and
  `cd site && python3 mksite.py` wrote a whole site into `site/web/`. Paths are now anchored to
  `__file__`, so the documented command works and there is only one output directory.
- **The build overwrote `web/og.png`** with a 1×1 placeholder on every run. The real 1200×630 image
  comes from `make_og.py`. The placeholder is now written only when the file is absent.
- **`str.replace` fails silently.** A build whose patterns stop matching produces a plausible file
  with a feature missing. All sixteen patterns are asserted to match exactly once by the inverter;
  that check should move into `mksite.py` itself.

**Rejected:** hand-editing `web/` and back-porting later (it is what caused this, and the debt grew
from two tabs to four files in two sessions); and retiring `site/` to edit `web/` directly, which
would have left `mkdash.py` and `mkmock.py` — and so both published artifacts — unbuildable.

**Would be wrong if:** a future page legitimately needs chrome that `head()`/`mast()` cannot
express. The addendum already strains it with `og_title` and `current=`; a third such page is the
signal to give the shells a real template rather than more keyword arguments.

## D46 — Head to head answers with a probability, and ships its own scoring record
**2026-09-20.** A seventh tab: pick two players and a window, get P(A outperforms B).

**Why a probability and not a projection.** The obvious build is a rest-of-season projection, and
the project's own numbers forbid it: R² ≈ 0.06 at one month against a 0.264 ceiling, Marcel tied
with 48 Statcast features (FINDINGS 2026-09-12). Printing "we project .341" would contradict the
evidence and break D37's rule that the site never issues a buy or a sell. Ordering a *pair* is a
different question — only the sign of the gap must clear the noise — and it calibrates well
(FINDINGS 2026-09-20). So the tab asks the question the data can answer.

**The calibration table is part of the view, not an appendix.** This is PRODUCT.md #1, the
prediction ledger, built by backtest rather than by waiting: `matchup.py` replays every block
boundary of 2023–2026, predicts from strictly prior data, and scores against what happened. A
reader can check what "62%" has historically meant before believing this one. It needs no stored
user activity and no database, which is why it could ship at all.

**The uncertainty split is the product.** Talent / drift / sampling are kept separate all the way
to the screen because the shares (sampling 63%, talent under 5%) are the finding: two clearly
different players are close to a coin flip over a fortnight, and stretching the window barely
helps because drift grows as √t while sampling falls as 1/n.

**Playing time is an input, not a forecast.** A first version projected it from the last four
blocks and gave Aaron Judge 2 PA a fortnight, his recent blocks of a part-finished season being
empty. The default is now the rate over blocks he actually appeared in, in an editable box. That
is not a cop-out: FINDINGS 2026-09-12 found playing time alone outpredicts xwOBA, so it is the
largest lever on the page and belongs with the reader, who may know about an injury.

**Rejected:** a live ledger writing each visitor's matchup to a server and scoring it a month
later. It needs storage the site does not have, would take two seasons to say anything, and the
backtest answers the same question today with three thousand times the sample. Worth revisiting
only as a public commitment device, which is a different product.
**Also rejected:** naming a favourite without the probability attached; and reading the estimated
gap as a predicted margin, which the per-view prompt forbids in as many words.

**Would be wrong if:** the PA floors are hiding the failure mode. Injuries and demotions remove a
player from the sample instead of scoring against the forecast, so every forecaster here is
graded only on players who kept playing. A version that scored a benching as a loss would be more
honest and would probably calibrate worse.

## D47 — Every tab states its question, how to read it, and what it can't tell you
**2026-09-20.** At the user's direction ("the purpose of each page should be immediately clear…
slightly more verbose and less technical but still using some technical terms").

Three changes, applied to all seven tabs:

**A question under the page title.** The `<h1>` carried only the tab's name, which says nothing.
Each tab now shows one plain question — *"Where did he really rank over these dates?"*, *"Which of
these two is better from here?"* These are the landing page's own wording, reused verbatim so a
reader arriving from `/` sees the sentence they clicked. Set in `show()` in `body.html` rather than
in the masthead block, because that block exists only in the deployed build and the two artifact
builds need it too.

**A fixed three-slot explainer.** Previously each tab improvised: some carried their limits in a
`defbox`, some in the lede, some nowhere. Now every tab has *What this answers* (one sentence,
always visible), *How to read it*, and *What it can't tell you*. The third slot is the one that
was missing or buried, and it is the site's whole stance — so it is now structural rather than
editorial. The existing prose was re-bucketed, not rewritten; only the missing limits are new.

**Register.** wOBA, percentile, reliability, sample size and probability stay in the visible lede.
Φ, σ², τ, Spearman–Brown and Brier moved behind the fold. The rule from D35 — define jargon once
per page — now has a place to live.

**Rejected:** a tooltip or glossary layer. It hides the limit behind a hover, and the limit is the
product.

## D48 — The global Type/Season control is a status strip, not another card
**2026-09-20.** The site-wide filter rendered through the same `.ctrl` component as every
per-tab control: identical card, border, radius and padding, distinguished only by a 10px caption.
On the Change log that produced three visually identical boxes, one of them global. It also sat
above the `<h1>`, so the page set a filter before it said what it was.

It is now a `.gbar`: no card, no radius, rules above and below, tinted, sitting under the title.
It states its own state — *"Showing hitters · 2026 season · applies to every tab"* — instead of
captioning itself, and the per-tab `.scope` captions drop to `--ink3` so the page has one loud
label rather than four competing ones.

**The part that was a correctness bug, not styling.** Breakouts ignores Type and Season entirely.
Its own footnote said so — while the two menus stayed fully live, so a reader could switch to
Pitchers there and watch nothing happen. The controls now actually `disable`, carry
`aria-disabled`, and the bar explains why. The footnote that duplicated this is gone.

**Would be wrong if:** a future tab ignores only *one* of the two menus. `GLOBAL_IGNORED` is keyed
per panel with a single message and would need splitting per control.

## D49 — Head to head defines its claim, and shows how each estimate was reached
**2026-09-20.** The first version put a bare "80% Aaron Judge" on screen. Reviewed as not rigorous
enough, which was right: **"outperforms" was never defined anywhere on the page.**

- The claim is now spelled out: *"finishes the next month with the higher wOBA of the two"*, the
  inverse for pitchers, and ties stated as counting for neither.
- The variance bar is captioned with the spread it divides up (the middle-80% range of the wOBA
  difference), because shares alone invite "60% of *what*?".
- **Each player's estimate is broken into its sources** — this season's rate and PA, his usual
  level and its span, and the weight each supplied, as a bar. That split *is* the shrinkage, and
  showing it makes the number arguable instead of oracular. Same move the Percentiles tab makes by
  drawing the bar twice. A thin or absent prior-season history is called out inline.
- "Estimated gap · 86 pts" became "Estimated talent gap · .086", with the difference between an
  estimate and an observation stated: neither player has hit this, and it is not a predicted margin.
- The calibration table's unlabelled `±` column is now "margin of error", buckets are shown as
  ranges, and **the row matching the probability currently on screen is highlighted**.
- **The tab flags its own unreliable range.** Where the backtest says the estimator missed by more
  than two standard errors — the .85 band, where it was right 77% of the time on 60 matchups — the
  page says so above the table. A tool called Reality Check should run one on itself.
- Brier score is glossed in the one place it appears.

**Rejected:** a confidence interval on the probability itself. It would be read as a second
probability and the honest version needs the estimator's own model error, which is not measured.
The calibration table answers the same question with data instead.

## D50 — Head to head takes an as-of date, scores itself when the window has elapsed, and ships one calibration table per horizon
**2026-09-20.** The tab had a forward window but no standing point: the estimate always summed
every block of the season, so it could only ever look forward from today.

**Three changes, and the second was not planned.**

**An as-of date.** `vsTalent(r, through)` and `vsRate(r, through)` now sum strictly up to the
selected block. Blocks 0 and 1 are not offered — under a fortnight into a season there is nothing
to stand on and the estimate is just the prior-season level.

**Scoring, which the as-of date unlocks for free.** If the chosen window has already been played,
the outcome is sitting in the same shard, so the tab shows the prediction against what actually
happened, marked right or wrong. That is `PRODUCT.md` #1's prediction ledger, one matchup at a
time, with no storage and no waiting — and it teaches better than the aggregate table, because
the reader watches an 85% call lose. The copy is careful that one result settles nothing: a
calibrated 70% is *supposed* to be wrong three times in ten.

**A calibration table per horizon, because the old one was wrong for three of the four.**
Calibration is not stable across the window (FINDINGS 2026-09-20): at 15 days the estimator says
57% and delivers 51%; at 90 days it says 74% and delivers 87%. The tab had been showing the
30-day table whatever the reader picked, which overstated its accuracy at two weeks and
understated it at three months. `matchup.py` now runs every horizon the tab offers and writes them
under one `horizons` key; the tab selects the matching one.

**Not conditioned on the as-of date.** Measured before deciding: splitting the 30-day panel at the
season midpoint gives Brier .2373 early against .2381 late, mean(actual − said) +0.002 against
−0.006. No systematic effect, so adding the dimension would only thin the buckets.

**Rejected: precomputing the matchups.** The question that prompted this was whether to precompute
overnight or reach for an API key. Neither. Nothing about a matchup is precomputed now — it is two
block sums, a precision-weighted combine and one normal CDF, on data already in the browser, and
an as-of date only changes which blocks are summed. Precomputing would mean 386 hitters → 74,305
pairs × 12 dates × 4 horizons = 3.6M cells for one season and player type, a few hundred MB across
all four seasons against a 187 KB first paint. The cheap path and the only feasible path are the
same one. An API key remains relevant only to the prose summary, which never auto-generates (D33).

**Rejected: fixing the drift term now.** The calibration flip says `2σ₁²t` is the wrong shape, not
the wrong constant. Fitting `t^α` or an OU reversion to four curves drawn from one overlapping
panel, with 2026 already a development set, is how the last holdout died. Backlogged as S33 with a
pre-registration requirement.

**Would be wrong if:** readers take the single scored outcome as the verdict on the estimator
rather than as one draw. The wording fights this; if it turns out not to, the reveal should show
the running record across the dates they have tried instead of the latest one alone.

## D51 — September stays on the Head to head tab, labelled by what it can support
**2026-09-20.** A season ends in September, so the last as-of dates have no full window after
them. The first fix cut the list off where the whole window still fit — which removed September
entirely, and with it both the freshest data and the question a reader in-season actually has:
*who is better from here?* That is the blunt fix, not an elegant one.

Every date is back, each labelled with what can be done with it:

| state | in the picker | behaviour |
|---|---|---|
| full | `Aug 15` | forecast, scored against what happened |
| partial | `Aug 30 · partly played` | forecast stands; interim outcome, marked as such |
| live | `Sep 15 · live` | a real forecast with nothing yet to score it against |

The **default** lands on the newest fully-scoreable date, so the outcome panel is populated on
first paint rather than never — which was the actual complaint behind "September has no
forecasts". The note under the controls says which of the three states you are in, and in the
live case says what the honest forward question in September is: the real window is *next
season*, and whether the end of one season predicts the next is open (backlog S34, and P11–P13
sealed in PREREGISTRATION.md).

**Rejected:** letting the horizon silently shrink to fit ("rest of season" becoming two weeks).
It answers a different question under the same label, and it would mis-key the calibration table,
which is selected by the nominal horizon.

**A bug class, not a bug.** Restoring the dates surfaced the third instance of the same fault:
an early return leaving a previous render's text on screen — here a season change left 2026's
headline and claim under a 2023 error. Clearing is now centralised in `vsBlank()`, called once at
the top of `renderVs`, rather than remembering the right subset per branch. Also found: for 2023
the tab cannot work at all, because `history.json` starts at 2023 and every player collapses to
league average. It now says so once, at season level, and points at `fetch_history.py`.

## D52 — The carry board is ordered by what survives, not by what is largest
**2026-09-20.** The board ranked every qualifying hitter by |gap| — how far his last month sits
from his own earlier-season rate. Over ~50–100 PA that ranks players mostly on their own noise:
the largest gaps belong to the smallest samples having the wildest month. A tool whose entire
purpose is to warn against reacting to short samples was opening with the short samples that had
moved most, which is the error it exists to prevent.

The default is now **expected next month** — how far from his usual level the model still expects
him to be — which is the quantity the tab is actually about. Two alternatives are offered:
*how surprising the move is* (|z|, the gap over the error two windows of that size produce on
their own) and *the raw size of the move*, which is kept because removing it hides the comparison
rather than making it. Each ordering carries a one-line note; the raw-gap note says plainly that
it puts the least trustworthy rows on top. A `z` column is now in the table, so the ordering is
inspectable rather than asserted.

It changes the board materially: sorted by gap, Cal Raleigh (+.246) leads and Andruw Monasterio
(−.202) is second; sorted by what survives, Monasterio drops out of the top four entirely, because
20% carry on a big gap is a smaller real move than 49% carry on Patrick Bailey's +.179.

**Rejected:** dropping the raw-gap option. The point is to show that the orderings disagree.

## D53 — Reliability is published with an interval, and it is not re-derived by the code that uses it
**2026-09-20.** Every shrunk percentile is `50 + ρ(raw − 50)` and every `% real` chip is ρ, all
published to three decimals with no indication of precision — then Spearman–Brown projected to
other sample sizes, carrying the unstated error along.

`reliability.py` bootstraps each ρ over player-seasons and writes `web/data/reliability-{kind}.json`.
The client merges it into `REL` and shows it in the planner's table as a 95% CI column and on each
chip as a tooltip. It loads off the critical path: without the file the site behaves exactly as
before.

**Two decisions inside this one.**

*It recomputes rather than re-implements.* `reliability.py` reads the shipped shards and rebuilds
the same odd/even split-half estimator, and `--check` asserts the point estimates match what
`blocks_all.py` wrote (largest deviation 0.0009). A file putting error bars on someone else's
number must not be free to drift from it.

*It is called from the renderers, not `setKind`.* The natural home was `setKind`, which is one of
the sixteen functions `mksite.py` rewrites wholesale — the edit would have been silently dropped
from the deployed build and kept working in the artifact builds. This is the failure mode CLAUDE.md
warns about, met in practice. A first attempt in `show()` failed differently: `show()` runs once at
boot before `K` is assigned, so a deep link painted with no intervals until the first tab switch.

**Would be wrong if:** readers read the interval as the uncertainty on a player's percentile. It is
the uncertainty on the *column's* reliability — a property of the metric, not the man (D25).

## D54 — Method prose lives in the addendum; a view carries only what you need to read it
**2026-09-20.** At the user's observation that the dashboard had become too dense.

**The measurement, after one false start.** A first count put Head to head at 2,667 visible words
and the whole tool at ~14,000. That was inflated roughly 2.5× by counting `<option>` text: the
player pickers hold 386 names each. Excluding form controls and collapsed `<details>`, the real
figure is Head to head **1,063** visible words against Percentiles 494, Player check 719, Planner
342. So this was never a site-wide density problem — it was one tab, the newest one, and the one
built over the last several turns.

**How it got there.** Every critique in this session was answered by adding a paragraph — the
claim line, the as-of note, the outcome block, the shrinkage ledgers, the variance note, expanded
tile subtitles, the self-check warning, a tripled calibration note. Each was individually
justified. None was answered by making something already present carry more weight. The result
was 992 words of prose around about thirty numbers, with the answer at y=422 and 2,079px of
justification beneath it.

**The rule now.** A view carries what a reader needs to judge the number in front of them. Method
— how an estimate is constructed, why a design choice was made, where it is known to be weak —
belongs in `addendum.html`, which already existed for exactly this and said so in its own lede:
*"the caveats that already govern the tool, collected in one place instead of scattered across
footers."*

**Absorbed rather than pasted.** The 224-word "How the probability is built" defbox and the
methodology half of the calibration note were rewritten into the addendum in its own voice and
sequence, not moved as blocks. The page now runs: what "% real" means → how precisely that figure
is itself known → significance vs. size → the noise ceiling → how a matchup is worked out →
holdout status → corrections. Every section gained an anchor so a view can link to the paragraph
that explains it. Head to head went 1,063 → **708** visible words and 2,501 → **1,964px**.

The new `#reliability` section also gave D53's bootstrapped intervals a written home, which they
did not have.

**Rejected:** deleting the caveats. They are the product. **Rejected:** a generic "read more" —
each pointer names what is on the other end, so following it is a choice rather than a gamble.

**Would be wrong if:** readers do not follow the link, and the caveat that used to be unavoidable
becomes one nobody sees. The single most decision-relevant line stays on the view for that reason
— "this is the estimator's record on other matchups, not a margin of error on this one" is still
inline, because it governs how the table above it should be read.

## D55 — The answer goes above the fold; the space around it is what gets cut
**2026-09-20.** Following D54: word count was never the site-wide problem, but height was. On a
758px viewport the answer sat **below the fold on four of seven tabs** — Percentiles 806px, Head to
head 868px, What carries 926px — because 446px of masthead, title and global bar preceded every
panel, and each panel then opened with a collapsed explainer and a control block before any data.
The summary sidebar was never the constraint: it is 248px on every tab while the main column runs
467–1,045px.

Nothing was deleted. Four structural changes:

1. **The explainer moved below the content on all seven tabs.** D47's question line under the page
   title now states each tab's purpose, so the lede no longer has to sit above the answer repeating
   it — and it was costing 116px of the fold on every tab to do so.
2. **The global bar is one row.** Controls first, then a short "applies to every tab" and the
   counts. The label had restated the type and season the selects already display. 106 → 70px.
3. **What carries leads with the board.** The four R² tiles describe the *model*, not the players,
   so they moved below the table they qualify. Answer 926 → 450px.
4. **Head to head's control block lost its two explanatory lines.** The as-of note moved beside the
   outcome block it describes; the playing-time note became a tooltip on the two inputs it is about.
   265 → 194px.

Plus a tighter vertical rhythm (`.wrap` 30→22, `.top` 22→14, `.panel` 22→16, and less padding on
`.use`).

**Result: every tab's answer is now above the fold** — Planner 423, Breakouts 442, What carries
450, Head to head 486, Change log 508, Player check 530, Percentiles 601.

**Three bugs surfaced, two of them mine from this change and one from much earlier.**
- Deleting the playing-time note removed the `var endsIn` declaration that shared its comment
  block, so `renderVs` threw straight after drawing the headline. The headline and claim rendered
  and everything below them was blank — a failure that looks like a layout problem, not a crash.
- The script that moved each explainer found a panel's closing `</div>` by searching backwards to
  the next panel. For the *last* panel there is no next panel, so it found `.wrap`'s closing div and
  parked the explainer outside every panel.
- **Pre-existing, and worth knowing about:** since the Head to head tab was first built, the page's
  own `<footer>` had rendered *above* its panel. The tab was inserted before `.wrap`'s closing div,
  which is after the footer, so on that one tab the methodology footnote sat between the global bar
  and the controls. Nobody saw it because every screenshot of the tab was taken scrolled down.

**Rejected:** clamping ledes or controls with `max-height`/`overflow`. That hides content by
accident rather than placing it on purpose, and it breaks on the first long player name.

**Would be wrong if:** a first-time reader needs the explainer *before* the answer to read the answer
correctly. The question line is the bet that they don't; the explainer is still one click away,
directly below.

## D56 — Every streak verdict is judged over one fixed horizon, not the next equal window
**2026-09-20.** At the user's direction: judging a two-week streak against the next two weeks
"compares one noisy thing to another." Measured before changing anything (FINDINGS 2026-09-20):
right about the per-streak verdicts — at two weeks, two-thirds of the "stuck" calls were luck — and
not about the aggregate share kept, which averages the follow-up noise away.

`breakouts.py` now scores every streak over a **fixed 60-day horizon** (`H = 4` half-months,
`--horizon`), the same for every streak length, and only if that full horizon exists in the season.
Previously the yardstick grew with the streak, so a 15-day streak and a 45-day one were not even
measured against the same thing. `kept`, `stuck`, "back to baseline", the earned-vs-lucky bootstrap
and every case-study verdict now use it. The old equal-window figure is kept in the table as
"old: next window", so the change is visible rather than asserted.

Each streak now carries a `fwd_status`: `ok`, `too_late` (the horizon runs past the season) or
`few_pa` (hurt, benched or optioned). The last two are counted and disclosed, not silently
dropped, and a case study that is too late reads "Too late to score" instead of being given a
verdict.

**Kept consistent with it:** the Streak forecast tab's cross-reference now quotes the new figures;
the summary component's evidence packet and its prompt now define `kept` on the fixed horizon,
since otherwise the model would have described the new numbers using the old definition.

**Deliberately not changed:** Player check's hard-coded `LADDER` rates (14 / 27 / 43%). It scores
streaks happening *now*, in September, and the new fixed-horizon figures describe early- and
mid-season streaks, which keep more. The all-streaks next-window rate is the more honest one for a
live September streak. An aggregate rate is also exactly where follow-up noise does not bias.

**Rejected: rest of season.** Mixes horizons and worsens survivorship.

**Would be wrong if:** the late-season exclusion matters more than it appears. It removes 171 of
766 career-view streaks; if late streaks behave very differently for a reason worth knowing, the
tab is now answering a narrower question than its title.

## D57 — Tabs are named for what they answer, and one name is used everywhere
**2026-09-20.** At the user's direction: "Percentiles" was confusing. It named the chart, not the
question — and the question under the page title (D47) already said what each tab was for, so the
name had nothing left to do.

| id | was | now |
|---|---|---|
| `p-stretch` | Percentiles | **Luck-adjusted rank** |
| `p-changes` | Change log | **Real changes** |
| `p-carry` | What carries | **Streak forecast** |
| `p-break` | Breakouts | **Streak history** |
| `p-planner` | Sample-size planner / "Planner" | **Sample-size planner**, in both places |

Player check and Head to head kept their names. The two streak tabs are deliberately paired —
*forecast* for current players looking ahead, *history* for past streaks and what they did — because
"What carries" and "Breakouts" gave no hint that one is live and the other is a study, and
"Breakouts" suggested a list of current breakouts, which it never was.

Renamed in the tab strip, the masthead nav (which also sets each page's `<h1>`), the landing page's
kickers, buttons and prose links, the addendum, the global bar's message, and every prose
cross-reference between tabs. Code identifiers (`renderBreakouts`, the `p-*` ids) did not change,
so deep links still work. The strip and the nav are now checked to carry identical labels; they had
disagreed ("Sample-size planner" / "Planner").

Also fixed while here: the landing hero said "Four tools", its button "See the four tools", and the
section beneath "Five tools", against seven tabs. The count is gone from the hero, which is where it
kept going stale; the section's "Five tools" stays, because it sits directly above the five cards it
counts.

**A cost:** the longer names pushed the masthead's timestamp onto a second line (56 → 86px). The
pill now shows the date only, with the full build time in its tooltip, and nav links lost 3px of
side padding. Back to one row at 56px.

## D58 — Head to head is scored against the best naive rule, not against a coin
**2026-09-20.** Comparing against "always say 50%" is a bar any ranking clears, and the two other
comparators on the record weren't naive — they turned a gap into a probability with this
estimator's own variance model, so they shared its assumptions. The record now also scores four
naive rules per horizon (`matchup.py`, `slice_baseline`), each fitted leave-one-season-out, and
the tab's scoring note says which of three cases a horizon is in, instead of quoting a Brier score:

- **no demonstrable skill** — not significantly better than a coin (hitters, 15 days). The note
  says to read the number as a lean, not a forecast.
- **beats a coin but not a simple rule** — names the rule that does as well (pitchers, 15 days).
- **beats the best simple rule** — and says how much of the way that rule alone gets.

This is the same move as D17 (grade against the ceiling, never 1.0) pointed the other way: grade
against the floor that is actually hard to beat, never against zero skill.

**Rejected:** tuning the estimator until it clears the 15-day hitter bar. That is the pre-registered
drift question (S33), and fitting to it on these seasons is what that entry exists to prevent.

**Would be wrong if:** a reader takes "beats the best simple rule" as "is good". The addendum puts
the margin next to it on purpose: 64–82% of the skill is available without any of this machinery.

## D59 — The two published artifacts built from the site source are retired
**2026-09-21.** At the user's direction, ahead of the restructure in `docs/SPEC-restructure.md`.
Stretch Finder (`mkdash.py`, all four seasons inlined, no LLM) and Stretch Finder Deployed
(`mkmock.py`, 2026 only, stored LLM responses) were deleted from the artifact gallery. Both were
built from the same `site/body.html` as the deployed site, so a restructure would have meant
either rebuilding them or freezing them at an old layout, and neither was worth the upkeep.

Removed with them: `site/mkdash.py`, `site/mkmock.py`, and `site/profiles.json`, which only
`mkmock.py` read (`profiles.py` and `report_profiles.py` read a different file, `output/profiles.json`).
`mksite.py` had been reading the summary panel's CSS out of `mkmock.py`; that CSS now lives in
`mksite.py`, and the rebuilt site was verified byte-identical before the scripts were deleted.

**Not deleted:** the other Statcast artifacts in the gallery — Signal, Noise and the Luck Gap;
Signal and Noise in Statcast; Statcast Atlas; What We Learned and What We Got Wrong; and others.
None is built from this source.

**A consequence worth taking.** `body.html` still carries the artifact-era scaffolding — the
`<script id="D">__DATA__</script>` placeholder and the sixteen `str.replace` rewrites in
`mksite.py` that turn an inline-data client into a fetching one (D45). With only one build left,
that indirection has no job, and the restructure is the natural moment to write the client for the
site directly and delete the rewrites — which removes the silent-no-op hazard CLAUDE.md warns about.

## D60 — Seven tools become two tabs: Player and Metric, plus Method
**2026-09-21.** At the user's direction ("the dashboard is cluttered… it scares the user off").
Specified in `docs/SPEC-restructure.md`; this records what was built and why it was built this way.

**The layout.** A reader starts from a player or a metric, not from knowing which of seven tools
answers their question, so the tools became *sections* inside two tabs:

- **Player** — the verdict (was Player check) → How he ranks → What changed → Compare to…
- **Metric** — How much data is enough → Who moved → Who's hot or cold → Streak forecast →
  Do streaks last → How well it predicts
- **Method** — the addendum page, now the third masthead item

**Moved, not rewritten.** Each old panel was split into its top-level blocks with a real HTML
parser and the blocks reassembled into sections. Every section kept its old element ids — the
sections are still called `p-card`, `p-vs`, `p-carry` — so the seven renderers, which address their
own elements by id, did not change. What changed is what counts as shown: one `isShown(section)`
replaced about twenty checks that assumed one panel per tab, several of them by bare index
(`active===4`). The three panels that mixed one player with the league were split: the player part
went to Player, the league board to Metric.

**The metric is global.** Metric joined Type and Season in the global bar, because both tabs use
all three. The planner's and the change log's own metric pickers are now driven by it and hidden,
which removes two controls that could disagree with it.

**Gating, and where it does not apply.** The metrics are not interchangeable (spec §5): the change
log tracks nine *input* metrics and never wOBA, while streaks, hot/cold and head to head exist only
on wOBA. On the **Metric** tab a section the selected metric doesn't support keeps its label and one
line saying why, and folds. On the **Player** tab nothing is gated — at the user's clarification,
his streak and matchup always show, marked "on wOBA", whatever metric is picked; "What changed"
shows every change he made with the selected metric floated first.

**Old links keep working.** `#p-vs`, `#p-carry`, `#p-card?k=bat&id=…` are in the wild. Each maps to
its new tab and scrolls to its section. A name on the Metric tab's hot/cold board opens that player
on the Player tab; the matchup's verdict links to its full scoring record on Metric.

**One summary per tab**, not one per section — mounted on the verdict (Player) or the planner
(Metric). Sections that don't host it drop the empty right-hand column.

**Bugs met and fixed on the way:** the first paint rendered the tab without going through `show()`,
so the question line was blank and deep links didn't scroll; the planner filled its own metric
options only on first render, so a sync that ran before it silently failed; and a CSS rule nested
`:has()` inside `:has()`, which browsers reject without complaint, so an empty control row stayed
visible.

**Kept, against the spec:** the global Type / Season bar. The spec proposed removing it, but with
two tabs that both need Type, Season and now Metric, a shared bar is exactly the right shape.

**Supersedes:** D47's per-tab questions (now one per tab), D48's per-tab disabling of the global bar
(no tab ignores it any more; the one fixed study says so in its own section), and D57's tab names
(now section names).

## D61 — Surface stats come from the same half-month blocks, appended to the shard (2026-09-21)

**Context.** The restructure feedback asked for the Player tab to show a player's full surface line
(games, hits, homers, slash line), plus his current team and position. None of that was in the shards.

**Decision.** `blocks_all.py` now counts the fields per block itself and appends them to each block's
array. Hitters get `ab, h1, h2, h3, hr, ibb, hbp, sf, sh, ci, g`; pitchers get `h, hr, ibb, hbp, g`.
Rows also carry `tm` (the team in the player's latest game) and `pos` (the fielding slot with the
most games; DH for a hitter who never fielded, P for a pitcher). The fields are appended rather than
inserted, so every existing field index is unchanged and nothing that reads a shard by position
breaks. The client builds a "Season line" section at the top of the Player tab, with two rows: the
full season and the selected recent window. Both come from the same blocks as the rest of the
analysis, so the surface line and the analysis cannot disagree about which games count.

**Rejected alternatives.**
- Pulling season lines from a separate leaderboard fetch. That would give a second source, which
  could disagree with the blocks, and it can't produce a recent-window row.
- Fixing the existing `k` field to also count `strikeout_double_play`. That would shift every
  K%-based number already published and every reliability figure. It stays as it is, and the page
  says strikeouts can run one or two short.

**Also in this change.** `blocks_all.py` had been failing on every scheduled refresh, because it
assumed `~/snap.db`, which exists only in the sandbox. It now uses `STATCAST_DB` if set, then
`~/snap.db` if it exists, then `data/statcast.db`, and always opens the database read-only. It
also now publishes its shards and `blocks_index.json` into `web/data/`. Nothing had done that
before, so the live shards only changed when someone copied them by hand.

## D62 — Each tab is chosen by analysis, not by metric; the second tab becomes League (2026-09-21)

**Context.** D60 put a global Metric picker next to Type and Season and stacked every section on
each tab. The user clarified that they wanted the Player tab to pick a *player and an analysis*,
and the other tab to pick *an analysis*, not a metric.

**Decision (the user chose each of these).**
- Each tab has a row of pill buttons, one per analysis, and only the chosen analysis renders.
  - Player tab: The verdict, How he ranks, What changed, and Compare to….
  - League tab: How much data is enough, Who moved, Who's hot or cold, Streak forecast, Do
    streaks last, and How well it predicts.
- The buttons are built from each section's own `.psec-k` label, including the "on wOBA" chip, so
  a button and its section can't drift apart. The label is hidden inside the section.
- The global Metric picker is gone. The two analyses that take a metric (the planner and Who
  moved) have their own visible pickers again. Each keeps its value across a type switch when
  both player types have that metric.
  - How he ranks and What changed show every metric for the player, so they need no picker.
  - The wOBA-only analyses are labelled rather than gated, so D60's metric gating (`GATE`,
    `gateMetric`) is removed.
- The Season line always shows on the Player tab, above the button row.
- "Metric" is renamed "League" in the tab strip, the masthead nav, the page title and the landing
  links. The element ids (`#p-metric`, `#t-metric`) are unchanged, so old links still work.
- The URL hash is the open analysis (`#p-carry`, `#p-vs`…), so every old per-tool link opens its
  analysis on the right tab. `RENDER` maps an analysis to its renderer, and a tab render draws
  only what is open.
- The AI summary follows the open analysis where it has a builder. It stands down where there is
  none (What changed, Who's hot or cold, How well it predicts) instead of showing an empty panel.

**Supersedes:** D60's global Metric picker, its metric gating, and the "Metric" tab name.

## D63 — A user walk-through: Season line spans seasons, plus eight fixes (2026-09-21)

The user asked for a pass through the UI as a user would see it. Their one named change: the
Season line should include previous seasons and sit above the analysis.

**Season line.** It is now the Player tab's header, directly under the player picker and above
the analysis row. The player's name is the heading, followed by team and position. The table has
one row per season from 2023 on, with the team for that season, then a total row across all
seasons, then the recent stretch. The earlier seasons come from a new `lines.py`, which sums each
player's shards per season into `web/data/lines-{bat,pit}.json` (about 150 KB each).
`blocks_all.py` runs it as its last step. The open season is always summed live from its own
shard, so it can't lag the rest of the page. Seasons before 2023 are not shown: `history.json`
goes back to 2015 but holds only PA and wOBA, and a table where most cells are empty for those
years would read as missing data.

**Fixes found by clicking through.**
1. The change tables coloured Δ and z by the sign of the change, so a rise in chase% or K% showed
   red, which means "better" everywhere else on the site. They now colour by `METRICS[].hi`, the
   same rule How he ranks uses.
2. The verdict's "All his percentiles →" and "His change log →" links still called
   `show(0)` / `show(1)` from the seven-tab layout. One did nothing and the other jumped to the
   League tab. They now open How he ranks and What changed.
3. How he ranks had its own From/Through dates and ignored the Recent stretch picker right above
   it. It now starts from that stretch, and dates you pick by hand hold until the stretch or
   season changes.
4. Compare to…'s result box read "Alex Bregman finished ahead, Alex Bregman .405 to …" with a
   date range of "Sep–Sep 30". It now names the winner once and uses the block's start date.
5. The inputs labelled "A plays" / "B plays" are now labelled with the players' names and the unit.
   "1 points" is now "1 point". The "Enough to prove it" tile, when no sample could ever
   decide, showed a bare dash followed by a sentence fragment; it now says "Never".
6. How well it predicts, on the League tab, marked "this matchup" from whatever was last open
   on the Player tab, and used that matchup's horizon with no control to change it. It now has
   its own Looking forward picker and no matchup marker.
7. A player link that also changed the player type (e.g. `#p-card?k=pit&id=…` opened while
   viewing hitters) switched the data but stayed on the League tab. It now opens the Player tab.
8. The "What this answers" box moved from the bottom of each analysis to the top, so the
   question comes before the answer.

**Not changed, noted.** The verdict still repeats the player's name in its own heading, right
under the new Season line header. I left it because the other analyses' headings carry the date
range and PA count, and removing only the name would leave them inconsistent.

## D64 — Recent stretch belongs to The verdict only (2026-09-21)

The user pointed out that the "last 30 days" picker sat above the Season line, which covers whole
seasons, even though only The verdict really uses it. It now lives in The verdict's own controls.
- The Season line lost its recent-stretch row and shows only seasons plus the total.
- How he ranks keeps its own From/Through dates and no longer follows the picker.
- The "All his percentiles →" link still opens it on the verdict's window, since that jump is
  explicit.
- The picker stays in step with the hidden `#pc-win`, which The verdict reads, and with the
  League tab's hot/cold stretch.

**Supersedes:** D63 fix 3, and D63's recent-stretch row in the Season line.

## D65 — The technical report is laid out as a paper, with analyses tiered by relevance (2026-09-21)

The user asked for the report (`output/full_report.html` → `web/report.html`) to read more like a
scientific paper, with less relevant analyses grouped as tertiary.

**Structure.** Title block, then:
- Abstract and keywords.
- 1 Introduction (with the status-tag key), 2 Data, 3 Methods (3.1–3.5).
- **4 Primary analyses:** 4.1 calibration table, 4.2 persistence (slumps), 4.3 forecasting,
  4.4 Marcel, 4.5 where measurement wins.
- **5 Secondary analyses:** 5.1 the wOBA–xwOBA gap, 5.2 the count, 5.3 platoon splits, 5.4 park
  bat-tracking.
- **6 Tertiary analyses:** 6.1–6.4 pitching orthodoxy, 6.5 the 2026 strike zone, 6.6 choking up.
- 7 Discussion (limitations, open questions), References, and Appendix A (the errata, formerly
  §11).

**How the tiers were assigned.** Primary means the dashboard's estimates depend on it directly:
"% real", the stretch verdict, and shrinkage toward a baseline. Secondary means it qualifies or
extends those results. Tertiary means it is outside the dashboard's scope, and most of these are
nulls.

**What changed in the text.**
- New: the abstract (every figure in it is taken from the body), one-paragraph introductions for
  each tier, a paragraph explaining the tiers, the references list and its seven bracketed
  citations, table numbers, and one missing caption (the trade-off table).
- Section cross-references were renumbered. A script check confirmed no stale "section N"
  remains, and a word-count diff confirmed no body text was dropped (only old headings and the
  old contents list).
- Titles changed: the report is now "Skill, Luck and Forecasting in Statcast Data, 2023–2026",
  with "What we learned, and what we got wrong" as its subtitle. Four section headings were
  renamed to fit the new structure.
- The findings' own wording was not rewritten.

**Not done.** The report's content still stops at its 13 September issue. It does not include
later results in FINDINGS.md, such as the naive-baseline comparison for head-to-head (D58) or
the longer-horizon streak verdicts. The transform was a one-off script (not kept in the repo);
`output/full_report.html` is now the source, and `publish_report.py` publishes it as before.

## D66 — The report is a v1: current findings, caveats, and no retractions (2026-09-21)

The user asked for the report to carry the latest findings. Midway through, they added: "I also
don't think we need to publish retractions anywhere, just caveats. This is a v1."

**Added from FINDINGS (18–21 Sep).**
- 4.2: intervals on reliability.
- 4.4: the streak studies (the length ladder, the career baseline with significant streaks, the
  longer follow-up).
- 4.8: head to head (calibration, calibration by horizon, the naive prior).
- 5.5: whether per-PA variance is constant, presented as a check on the constant, not as a
  retraction.
- §2: surface stats, the team and position fields, and a Data caveats box.
- §3.5: the 20 September pre-registration addition.
- New limitations and open questions.
- Two results that previously lived only in the errata are now stated as findings: chase rate
  moves with results rather than ahead of them, and a monthly bat-speed change is 34% signal.

**Removed as retraction framing.**
- The "what we got wrong" subtitle and the abstract's error count.
- The errata appendix.
- In 5.1, "the explanation we published and withdrew". It is now a plain result: only popups are
  biased, the gap is unexplained, and a caveat notes that the stored `woba_value` column would
  suggest a ground-ball gap.
- In 6.5, the "confident, wrong answer". It is now a methods box on why the zone is measured in
  absolute height.
- The status tag "retracted". "Prediction failed" stays, because a pre-registered prediction that
  isn't borne out is a result.

**Removed from the site.** The Method page's "every error caught" caption and "caveat and
retraction" meta description, and "Retracted before it was built" in the Streak forecast.

**The one numeric caveat carried in the text.** The count table's absolute values and the
forecasting R² comparisons predate the corrected wOBA numerator. The Data caveats box says so, and
says why the comparisons still stand (a near-uniform offset). Neither was re-run.

**Supersedes:** D65's Appendix A and its subtitle.

## D67 — Analyses get descriptive names; colour carries strength and correctness (2026-09-21)

**Names.** The user found "The verdict" unclear and asked for better names throughout. The ids
and hashes are unchanged, so every link still works.

| was | now |
|---|---|
| The verdict | Is his recent form real? |
| How he ranks | Luck-adjusted percentiles |
| What changed | Swing & approach changes |
| Compare to… | Head-to-head odds |
| How much data is enough | Sample size needed |
| Who moved | Biggest skill changes |
| Who's hot or cold | Hot & cold right now |
| Streak forecast | Streak carry forecast |
| Do streaks last | Streak history study |
| How well it predicts | Head-to-head track record |

Mentions of the old names in the explanatory text, the landing cards and the report were updated
to match.

**Colour.** There are two separate scales, so neither colour means two things.
- **Better / worse:** the site's existing red = better, blue = worse, now with intensity. `heat()`
  fills a cell more strongly as the evidence strengthens: |z| in the change tables and the hot/cold
  board, the size of the expected gap in the Streak carry forecast. The "% real" chips fill with
  the accent colour in proportion to reliability.
- **Right / wrong:** new `--right` (green) and `--wrong` (red) tokens, used only where something is
  judged correct.
  - The Head-to-head odds outcome box turns green ("✓ Called it") or red ("✗ Missed").
  - The track record's win-rate cells are green within their margin of error and red outside it,
    with "on target" / "off" chips.
  - The change tables' "held" chip is solid green when the change held, pale green when partly
    held, and red when it reversed.
- The head-to-head probability itself deepens in colour the further it is from 50%.

**Where the uncertainty comes from** is now "Why the odds are this close to 50%". It has a
one-line explanation above the bar, and plainer labels: not knowing their true talent / talent
shifting over the window / ordinary luck over the next ~N PA. Luck is purple, because red now
means both "better" and "wrong".

## D68 — Career lines from the Stats API, a scoreable carry board, more naive priors, a summary on every Player analysis (2026-09-21)

**Season line → whole career, official.** `fetch_careers.py` pulls MLB-only year-by-year lines
from statsapi.mlb.com for every player in the shards, into `web/data/careers-{bat,pit}.json`
(about 300 KB each, around 20 seconds). It runs in `run_pipeline.py` before matchup.py. A traded
season uses the API's combined row, with both teams listed.
- Hitter columns: G PA AB R H 2B 3B HR RBI BB SO SB AVG OBP SLG OPS.
- Pitcher columns: G GS W L SV IP H HR BB SO ERA WHIP K% BB%.
- The block-summed line from D63 stays as a fallback for a player not yet fetched.
- Checked against published lines: Judge 2024 has 171 SO and 58 HR; Skubal 2024 has 192.0 IP and
  228 K. Official lines fix the strikeout-double-play undercount, but only in the display.
- wOBA left the Season line, because the official lines don't carry it.

**Streak carry forecast: any 30-day window, not only the latest.**
- The window *length* stays fixed at 30 days, because the coefficients were fitted and
  pre-registered on W = 2 only. Refitting for 15 or 45 days would be a new specification.
- For a past window the board adds what happened the following month, and a right/wrong chip for
  whether the model or "the streak continues" was closer.
- A scorecard counts the model's wins across every qualifying player. For example, for the window
  ending Aug 15, 2026, the model was closer for 139 of 210 players, with an average miss of .051
  against .068.
- 2023–2025 windows are flagged as in-sample.

**Head-to-head naive priors.** Last season, career, and Marcel were added to the slice baselines,
and the League track record now shows every rule with a right/tie/wrong verdict. Result in FINDINGS
2026-09-21: Marcel ties the estimator for hitters and loses for pitchers.

**Summary on every Player-tab analysis.** Swing & approach changes gained a builder (it reuses the
`changes` prompt). The four League analyses that already had one keep theirs; Hot & cold right now
and Head-to-head track record still have none.

**Cost display fixed.** Both `api/summary.js` and `serve.py` priced Haiku 4.5 at Sonnet rates
($3/$15 per million tokens), overstating each summary's cost three times over. They are now $1/$5.

## D69 — The summary points to its evidence by layout (2026-09-21)

The summary's idle text said "the evidence below", but the summary sits to the right of its
analysis. It now says "to the left" in the side-by-side layout and "above" below 1000px, where the
summary stacks under the analysis. Two spans are toggled by the same media query as `.split`, so
the wording can't disagree with the layout.

## D70 — "held" uses a fixed 60-day follow-up (2026-09-21)

The user asked for `held` to use a longer follow-up, like the streak study. It now measures the
share of a move still present over the next four half-month blocks, whatever the window length,
with a floor of 40 of the metric's own denominator (`HELD_BLOCKS` in body.html).

The cost is that moves from the last 60 days of data show no verdict and are counted in the
footnote instead. The following were updated to the new definition:
- the explainers and the tooltip
- the sort label
- the pending note
- the `changes` summary prompt
- the summary builders' notes
- the landing figures (46%, and the three example rows)

FINDINGS 2026-09-21 has the before/after figures.

## D71 — The player picker and the Season line share one compact card (2026-09-21)

The user found the player picker and the career table too wide as two full-width strips. They are
now one card (`.phead`) holding the picker, the player's name and meta, and the table. The card is
sized to its content, not the page: about 895 of 1,148px for a hitter, and narrower for a pitcher,
whose table has fewer columns. Its table cells are tightened (5px 8px). A labelled "Analyses" break
(a rule, extra space, and a small caption) now separates the player header from the analysis
buttons.

## D72 — Every analysis gets a standalone "What this answers" line (2026-09-21)

The user found the one-liner for "Is his recent form real?" vague ("pulling the other views into a
single read"), and asked for every one-liner to make sense on its own.
- All seven existing "What this answers" lines were rewritten to say concretely what the analysis
  tells you, and to what or whom.
- The three analyses that had none now have one: Swing & approach changes, Hot & cold right now,
  and Head-to-head track record. They use a plain box (`.use.static`) with nothing to expand.
- The four method boxes also got clearer one-liners, and two headings were renamed:
  "Spearman–Brown, run backwards" became "How the sample sizes are calculated", and "z, sd, and
  held — what each one is for" became "What z, sd and held each tell you".
- The carry box's "what failed on the way there" became "which extra inputs were tested and found
  not to help" (D66: no retraction framing).
- Only the "What this answers" box (`.use.ans`) moves to the top of an analysis now; method boxes
  stay at the bottom.

## D73 — On the Player tab the picker is the heading; a key-numbers summary tops the Season line (2026-09-21)

**Picker.** The user wanted the player selection higher and bigger, as the focal point. On the
Player tab the page title is hidden and the picker takes its place.
- It's a large serif select, underlined in the accent colour with a chevron, showing the player's
  name only; the PA count is stripped from the option text.
- The team and position line sits under it.
- `body[data-tab]`, set in `show()`, switches this per tab. The League tab keeps its ordinary
  title.

**Key-numbers summary.** A "Summarize his key numbers" button sits at the top of the Season line
card. It sends the table exactly as drawn (every season, the career row, the formatted cells) to
`/api/summary` as a new `line` view, with its own prompt: compare the selected season with his
career and recent seasons, then describe the career's shape, with no causes and no projections.
It is its own small component with its own abort, because the main summary panel is one shared
node that resets on every redraw and would cut this summary off mid-stream. It keeps one summary
per player and season in memory.

**Not verified end to end.** No `ANTHROPIC_API_KEY` is set on this Mac, so locally `serve.py`
answers with its no-key message. The request shape, the view whitelist (`api/summary.js` and
`serve.py`) and the error display were checked; a generated summary was not.

## D74 — The header picker, toned down (2026-09-21)

D73's display-size picker (46px, full-width underline) was "absurdly big". It is now a bordered
select at 22px serif, with a card background, a small chevron, a 280px minimum width and an accent
border on hover. It still sits in the heading position on the Player tab, but reads as a clear
control rather than a banner.
