# Research backlog

Candidate studies, each with an honest read on whether this database can answer
it. Ordered by (novelty × feasibility × statistical power).

**Before running any of these: write the hypothesis and the holdout into
`FINDINGS.md` first.** The one clean result of 2026-09-10 came from
pre-registering; the one that died came from looking first.

Legend: ✅ answerable with what is on disk · ⚠️ answerable with a derivation or a
redesign · ❌ needs data we do not have.

---

## 1. ABS as a natural experiment (2026)

The strike zone changed from operator-set to height-derived in 2026. That is an
exogenous rule change with a hard date — the only causal identification
available in this dataset, and the one thing here that thirty front offices have
not already studied to death, because the season is still running.

| sub-question | status | needs |
|---|---|---|
| Does catcher framing value collapse? | ✅ | `plate_x/z`, `description`, `fielder_2` (catcher id) |
| Does the run value of a called strike become less variable? | ✅ | `delta_run_exp`, `description` |
| Do pitchers stop nibbling at the edges? | ⚠️ | see the trap below |
| Do umpire-specific effects vanish? | ❌ | `umpire` is a dead column — StatsAPI |

**THE TRAP.** You cannot measure distance from the zone using `sz_top`/`sz_bot`,
because those columns ARE the thing that changed — operator-set through 2025,
ABS-derived after. A pitch "two inches above the zone" means something different
on either side of the boundary, so any trend you find is partly the ruler moving.
Define your own fixed geometric zone and measure against that. The same applies
to `zone`, which Savant derives from those columns.

This generalises: **a rule change often changes the measuring instrument too, and
separating those is most of the work.**

**Power note.** Pre-period is three seasons, post-period one partial season.
Enough for framing; thin for anything needing seasonal stability.

## 2. Which metrics stabilise fastest ✅

Split-half reliability at increasing sample sizes for exit velocity, barrel rate,
bat speed, swing length, whiff rate, chase rate and xwOBA. Every input is on
disk.

**Why it matters more than it sounds.** `MIN_PA = 150` is currently one number
applied to every metric, which `DECISIONS.md` already flags as blunt. If bat
speed stabilises at 50 swings while xwOBA needs 300 PA, the dashboard can flag a
breakout two months earlier than it currently can. That is a forecasting edge,
and forecasting is where public data still competes — unlike prescription, which
competes against the pitching coach.

Public work here mostly cites reliability numbers that predate bat tracking
entirely, so the newest columns are unstudied.

**Asymmetry to plan around:** bat-tracking metrics start July 2023, so their
curves rest on ~3.2 seasons against 4 for exit velocity. Do not compare their
standard errors as though the samples matched.

## 3. Arm angle change points ✅

`arm_angle` is per-pitch and 95–99% populated in all four seasons. Detect
pitchers whose slot shifts more than ~5° mid-season, then ask what happens after.
Slot changes are deliberate (a mechanical fix) or involuntary (an injury tell),
and either answer is worth having. The column is recent enough that little public
work exists.

**The constraint is not data, it is the comparison.** A slot change and a
performance change can share a cause. Use a within-pitcher before/after with a
placebo window.

## 4. Times through the order: fatigue or familiarity? ✅

The penalty is established; its cause is not. `n_thruorder_pitcher` is a column;
cumulative pitch count within a game is not, but it is a window function over
`(game_pk, pitcher)` ordered by `(at_bat_number, pitch_number)`.

The identification is the appealing part: TTO and pitch count are correlated but
not collinear — long innings and quick innings break them apart — so you can hold
one fixed and vary the other.

## 5. Platoon splits by pitch SHAPE rather than handedness ✅

Does a sweeper's platoon split exceed a slider's, holding velocity constant?
`pfx_x`, `pfx_z`, `stand`, `p_throws`, `delta_run_exp` are all present. Remember
to flip `pfx_x` by pitcher handedness or the effect cancels.

## 6. Squared-up and blast rate, derived ⚠️

`bat_speed`, `release_speed` and `launch_speed` are all present from July 2023 —
enough to compute squared-up yourself. Savant's exact formula is not in their CSV
documentation, so you would be defining an approximation; say so. The interesting
question does not depend on matching them: does a swing-quality measure
independent of outcome stabilise faster than xwOBA?

## 7. Swing plane versus pitch height ⚠️ — as posed, broken

`attack_angle` is populated on BALLS IN PLAY, not on swings. You observe a
hitter's swing plane only when he made contact, so the whiffs — exactly where
"vulnerable up in the zone" would show — are systematically absent. That is
selection on the outcome and controls do not fix it.

**The workable version** uses `bat_speed` and `swing_length`, which are populated
on swings including misses, as the swing-shape proxies. Different question,
answerable data.

## 8. Velocity decline as an injury leading indicator ❌ (half)

`release_speed` is there; IL stints are not. StatsAPI.

## 9. Shift restrictions (2023) ❌

Needs 2021–2022 as the pre-period. Not downloaded.

---

## What unlocks the most, cheapest

1. **StatsAPI** (`statsapi.mlb.com`, free, documented) — umpires, weather,
   lineups, IL stints. The single highest-value external addition, and it
   unlocks two backlog items outright.
2. **Sprint speed 2023–2025** — one command; `backfill.py` already fetches it.
3. **2015–2022 backfill** — one overnight run, ~3.6 GB. Unlocks the shift and
   pitch-clock experiments. Note the 2020 Trackman→Hawk-Eye instrument change:
   spin and movement are not comparable across that seam, though exit velocity
   and launch angle broadly are.

---

## Queue as of 2026-09-11 (pre-registered: write the predicted direction BEFORE querying)

### S10 — Consequences of the 2026 zone change  *(highest value)*
The zone lost its top (-23.5pp at 3.4-3.6 ft) and gained its bottom (+10.5pp at 1.4-1.6 ft).
Large, recent, exogenous, well measured — the closest thing to a natural experiment in this data.
**Predictions, recorded before running:** (1) pitchers in the top tercile of vertical approach angle
/ high-fastball usage lose more 2026-vs-2025 xwOBA-against than the bottom tercile; (2) low-ball
and sinker-heavy pitchers gain; (3) tall hitters gain relative to short hitters. Power: whole
league, both seasons. Data: fully available.

### S11 — Real tunnel separation at the commit point
Today's null used release-point distance, which is a proxy. Project both pitches forward ~23 ft
using release position + velocity + acceleration vectors (all present), measure separation there,
redo within pitcher. **Prediction:** still null, but the test is only honest once this is run.

### S12 — Within-hitter two-strike adjustment
Does a hitter's own 2K performance improve in seasons he shortens up more? Settles whether the
between-hitter correlation found today is causal or a marker of bat control. Needs 3+ seasons per
hitter; 2023-2026 supports it.

### S13 — Holdout: replay all of 2026-09-11 on 2023-2024
Everything today was fit and read on 2025-2026. The scripts are parameterised by year. Cheap.
**Prediction:** two-strike effect and platoon signal share replicate; the TTO/arsenal null and the
tunnelling null replicate; nothing new appears.

### S14 — Is monthly mean reversion (-0.51) constant?
If it varies by hitter or by point in season, it is exploitable. If it equals the value implied by
the monthly noise share, it is mechanical and merely a warning label. Cheap, already have the panel.

### S15 — Park sensor vs park physics
Bat speed should not vary with air density; exit velocity should. The ratio per park separates
instrumentation from environment. Coors is the control. Feeds a park adjustment that everything
else should then use.

---

## Added 2026-09-12, from the forecasting study

### S20 — Why is xwOBA's predictive edge humped rather than declining?
Edge over wOBA: +.019 (1mo), +.037 (2mo), +.037 (3mo), +.008 (season). I predicted monotone decline.
The 3-month row has the smallest test sample (318). **Re-run at weekly resolution**, where a season
yields ~26 windows instead of 6, to see whether the hump is real or an artifact of month granularity.

### S21 — Is the model's edge better shrinkage, or better information?
Compare the 48-feature model head-to-head against a two-parameter model: xwOBA shrunk optimally given
its own sample size. If most of the gain is shrinkage, the deliverable is a formula, not a model.

### S22 — Benchmark against Marcel
Nothing here has been tested against a public forecaster. Marcel (3-year weighted average + regression
+ age) is ~30 years old, trivial to implement, and is the standard floor. **A model that beats xwOBA
but loses to Marcel has achieved nothing, and I currently do not know which side of that line this is
on.** Highest-priority validation item in the repo.

### S23 — Rest-of-season is the right target, not next month
Every model here predicts next month. Roster decisions need rest-of-season, which is a less noisy
target and therefore has a higher ceiling. One line of code.

### S24 — Backfill sprint_speed 2023-2026
Currently 552 rows, one season. Every name on the persistent-gap over-performer list is fast
(Altuve, Friedl, Turner, Rafaela, Perdomo). Sprint speed would convert the best circumstantial
finding in the repo into a direct measurement, and also unblocks T5 of the batted-ball program.

### S25 — Does the playing-time signal survive conditioning on health?
Lineup frequency out-predicting exit velocity is either managerial private information or an artifact
of injuries and platoons. Condition on consecutive healthy months and on a fixed lineup slot.

### S26 — Run the whole thing for pitchers
Every result so far is hitters only. Prior: lower ceiling, larger xwOBA edge, since pitchers control
batted-ball outcomes far less than hitters do.

### S22 — CLOSED 2026-09-12. Marcel benchmark run; result is a draw (see FINDINGS).
Superseded by S27-S30 below.

### S27 — Benchmark against Steamer and ZiPS
Marcel is the floor, not the standard. Both are considerably stronger and neither has been tried.
Honest expectation: they beat everything currently in this repo.

### S28 — Is the season-level failure sample size, or the features?
A 20-feature GBM at R2 = -0.060 on 267 training seasons is textbook overfitting, but that is a story,
not a test. Backfill 2015-2022 (~5x the training set) and re-run. Note the asymmetry: exit velocity
exists from 2015, **bat tracking does not exist before 2024**, so swing-geometry features can never
have a long runway and may be permanently unusable at season scale.

### S29 — The low-history win: the project's only real niche, barely explored
Model beats Marcel by +0.049 (P=0.94) in the bottom quartile of prior history, monotone across all
four buckets. Narrow prospective test: hitters inside their first 200 career PA, Statcast-only
forecast vs full regression to league mean (all Marcel can offer them).

### S30 — If the value is in the shrinking, build the shrinker, not the model
A shrunk average of past xwOBA ties Marcel exactly. That suggests the deliverable is two numbers —
a per-metric regression constant and a weighting scheme — not a model. Easier to trust, easier to
ship, and it makes the interactive instrument simpler rather than more complex.

### S27 — UPDATED 2026-09-12. Steamer/ZiPS benchmark is blocked on a manual export.
FanGraphs gates CSV export behind membership. What is needed, exactly:
  1. fangraphs.com/projections with **type=steamer** (NOT steameru — the update variant already
     contains 2026 and would leak), stats=bat, pos=all, Page Size = Infinity -> Data Export
  2. same with **type=zips**
  3. drop both CSVs in the repo; only need Name / Team / PA / wOBA
Then `marcel5.py` scores them on the same 245-hitter 2026 test set as Table 7.
A reimplementation of their published methodology is NOT a substitute — it would be my strawman of
their method, in the opposite direction from the strawman I avoided by tuning Marcel.

### S31 — Replicate the 22-25 age result prospectively on 2027
O5 emerged from a post-hoc split (8 segments tested). Its CI excludes zero but it is a hypothesis,
not a finding, until it survives a season it did not generate.

### S32 — Resolve the reliability tension in the residual
wOBA-xwOBA has within-season split-half reliability 0.164 but correlates +0.29 with itself across
seasons, three year-pairs running. The lower-bound argument for odd/even splits does not comfortably
cover a gap that size. A variance-components model (player / season / residual) would settle it.

### S32 — Do hot streaks backed by rising hard-hit rate stick better? (pre-register for 2027)
`breakouts.py` found hard-hit-backed hot streaks kept 7–13 points more of their gain than
hard-hit-down streaks at 15/30/45 days in 2023–25, significant at none after multiple comparisons,
and 2026 did not reproduce it (FINDINGS 2026-09-18). Write the prediction down before 2027 data
exists — e.g. "at 30 days, hard-hit-up streaks keep at least 8 points more than hard-hit-down" —
and test once.

### S33 — Fix the head-to-head drift term, and pre-register the fix before fitting it
The matchup estimator treats true talent as a random walk, `var(drift) = 2σ₁²t` with σ₁ = .0381
per month. Measured 2026-09-20: it is calibrated at 30 days, **over**confident at 15 (says 57%,
delivers 51%) and **under**confident at 60 and 90 (says 74%, delivers 80% and 87%). The sign flips
with the window, which says the √t shape is wrong rather than the constant.

Two candidates, both cheap to fit and both easy to fool yourself with:
- **`t^α` with α fitted.** The flip implies α < 0.5. One parameter.
- **Ornstein–Uhlenbeck**, `var = (σ₁²/θ)(1 − e^{−2θt})`, which is flat-ish early and saturates
  late — the right qualitative shape for talent that reverts rather than wanders. Two parameters.

**Why this is a backlog item and not a patch.** There are exactly four horizons, all evaluated on
the same overlapping panel, and 2026 is a development set (D28). Fitting one or two parameters to
four calibration curves drawn from the same 3,000 pairs is how a holdout dies — and this project
has already recorded one dying that way. The honest sequence is: pick the functional form on
2023–2025 only, write the predicted 2027 calibration down in `PREREGISTRATION.md` before the
season exists, then score once.

**Can it answer?** Probably. The signal is large (a 13-point calibration miss at 90 days is not
subtle) and the direction is consistent across every bucket at both extremes. The risk is that
drift is not the guilty term at all — σ² may be understated at short windows for reasons that have
nothing to do with talent moving — so the pre-registration should name a test that distinguishes
them, e.g. whether the short-window miss survives conditioning on games played in the window.

Until then the site ships a calibration table per horizon and shows the matching one (D50), so the
error is disclosed rather than hidden.

### S34 — Does the end of a season tell you anything about the next one?
A late window is the most recent evidence and the least reliable, and those pull in opposite
directions. Five sub-questions, in the order they should be asked. Hitters; the window is the
**final 45 days**, not "September" as a calendar fact (persistence ladder 14% / 27% / 43% at
15 / 30 / 45 days, FINDINGS 2026-09-18).

**H1 — The late window alone is far worse than the full season.** wOBA needs 225 PA for ρ = 0.5;
45 days is ~150 PA against a season's 600. Near-certain, and it is the null the rest must clear.

**H2 — It adds nothing incremental to the full season, for outcomes.** Regress season Y+1 wOBA on
(full-season Y wOBA, final-45-day Y wOBA). Predicted: the late coefficient is indistinguishable
from zero and plausibly **negative** — conditional on the season total, a hot finish means the
earlier months were relatively worse, and part of the heat is luck owed back (the "once you know
xwOBA, wOBA is negative information" result, 2026-09-12). This is the offseason analogue of D27.

**H3 — The inputs carry real signal across the offseason, and it still does not pay.** Bat speed
is ~90% reliable at 50 PA, so a late window measures it almost perfectly while measuring wOBA
barely at all. Two predictions, deliberately split: late-window bat speed **beats** the season
average at predicting next season's *bat speed* (likely true, pure reliability), and that edge
**does not** carry into next season's *wOBA* (likely null). Worth running precisely because both
halves are informative — it would be the offseason twin of the paradox already on the carry tab,
where input changes persist at r ≈ .5 and forecast nothing.

**H4 — Any gain concentrates in players without a track record.** The measured niche is the
least-history quartile (+0.049, P = 0.94, 2026-09-12). A late window is a rounding error against
three prior seasons and a large share of everything known about a call-up. Close to mechanically
true — weak prior, so the likelihood weighs more — so the test is whether it is large enough to
act on, not whether it exists.

**H5 — The confounds may sink it.** Roster expansion means late-season lineups face call-up
pitching; contenders rest regulars while eliminated teams play prospects; and playing time, the
single strongest predictor in the panel (0.0316, double xwOBA), is exactly what September
distorts. Undisclosed injury is the same unmeasured explanation already flagged for sticky slumps,
and IL data is still not in the database. A pitcher-quality control is not optional here.

**Can it answer?** Only partly, and the constraint is data rather than method. Block-level data
covers 2023–2026, so there are **three season transitions**, one of which (2025→26) is a
development set (D28). Roughly 220–250 hitters clear 60 PA in Sep/Oct each year. `fetch_history.py`
extends *season totals* to 2015 but not block-level data, so a longer panel needs the 3.6 GB
overnight backfill. H1, H2 and H3 are answerable at this size; H4 is underpowered.

**Design constraint, from this project's own failure.** At season level a shrunk average of past
xwOBA ties Marcel (.166 vs .164) while a 20-feature GBM scores **−0.060**, worse than predicting
league average, on 267 training seasons. Anything here must be a one- or two-parameter addition to
Marcel. A feature dump is already known to lose.

H6 of this set — late-season decline as an early aging signal — is not listed here because it
cannot be tested at the current panel size and has therefore been pre-registered instead.
