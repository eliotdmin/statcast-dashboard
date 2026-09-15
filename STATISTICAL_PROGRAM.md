# The statistical program

*Consolidated 2026-09-15. This document is about the statistics only — the estimators, the
quantities they estimate, what has been measured, what has failed, and what remains open. No
product, no engineering, no interface. It supersedes nothing; `FINDINGS.md` remains the
append-only log and this is its structured index.*

---

## 0. Scope and notation

Four seasons of Statcast pitch-level data, 2023 through 2026-09, 2.84M pitches. Units of analysis
range from the pitch to the player-season. Everything below is observational; there are no
interventions and one natural experiment (the 2026 ABS zone).

```
X       an observed rate for one player over one window
T       true talent over that window — the average over infinite replays of it
e       everything else: opponents, park, defence, sequence, which pitches arrived
n       sample size (PA, batters faced, swings, batted balls — always stated)
rho     reliability, var(T)/var(X)
sigma²  per-PA outcome variance of wOBA = 0.2258  (sd 0.475 per plate appearance)
```

---

# PART I — THE MEASUREMENT MODEL

## 1.1 The single decomposition

```
X = T + e ,   E[e] = 0 ,   cov(T, e) = 0     =>     var(X) = var(T) + var(e)
```

Every estimator in this project is a way of getting at one of those three terms. The assumption
that does the work is `cov(T, e) = 0` — that better players are not systematically luckier. It is
approximately true for batted-ball outcomes and badly false for anything containing team context
(wins, RBI, and, for a pitcher, wOBA-against, which contains his defence).

## 1.2 Reliability, and the three quantities that share the name

**This is the most important conceptual distinction in the project, and conflating two of them
caused a retraction.** There are three different things called "reliability" here:

| # | quantity | question it answers | bat speed | wOBA |
|---|---|---|---|---|
| **A** | reliability of a **level**, within-season split-half | is the *ranking* of players real? | .974 | .479 |
| **B** | signal share of a **year-over-year change** | is a player's *season-to-season move* real? | 85% | 68% |
| **C** | signal share of a **month-over-month change** | is a player's *in-season move* real? | **34%** | — |

A and C differ by a factor of nearly three for the same metric. A level can be pinned down
precisely while a change in it is almost entirely noise, because a change is a difference of two
noisy quantities and the noise adds while the signal partially cancels. The project asserted
"bat speed is reliable at ten swings, therefore monthly bat-speed tracking works." That inference
is invalid and was retracted (§7.2 of `FINDINGS.md`).

Formally, for independent windows of size `n1` and `n2`:

```
var(observed change) = var(true change) + var(e1) + var(e2)
signal share         = var(true change) / var(observed change)
```

`var(true change)` is typically far smaller than `var(T)` — talent moves slowly — while the noise
term roughly doubles. Both effects push the change's reliability below the level's.

## 1.3 What reliability buys, and what it does not

**Buys, 1 — a decision rule.** Because `b = cov(T,X)/var(X) = var(T)/var(X) = rho`, the reliability
*is* the regression coefficient. `T_hat = mu + rho·(X − mu)` is not a heuristic; it is the
conditional expectation under joint normality and the best linear estimator regardless.

**Buys, 2 — a design constraint.** Inverted, `rho(n) = t` solves for the `n` a question requires.

**Buys, 3 — a common axis.** mph and wOBA-points are not comparable; their reliabilities are.

**Does not buy — validity.** A scale that always reads ten pounds heavy has perfect reliability.
Arm angle has `rho = .999` and is a poor measure of "did the delivery change," because it averages
across pitch types: change the mix, move the number, delivery untouched. High reliability with low
validity is the more dangerous failure because the number looks authoritative.

**Is population-dependent.** The same metric on 300 major leaguers and 300 random adults has
identical `var(e)` and different `var(T)`, hence different `rho`. A reliability without its
population and its `n` is meaningless.

---

# PART II — THE ESTIMATORS

## 2.1 Split-half correlation = reliability

Two independent measurements of the same `T`: `X1 = T + e1`, `X2 = T + e2`, `cov(e1,e2) = 0`.

```
        cov(X1,X2)        var(T) + cov(T,e2) + cov(e1,T) + cov(e1,e2)     var(T)
r  =  --------------  =  --------------------------------------------  = --------  = rho_half
      sqrt(v1 · v2)                      var(X1)                          var(X1)
```

Every cross term dies. A correlation you can compute equals a variance ratio you cannot. Two
splits are used in this project and they are not identical:

- **odd/even half-month blocks** within a season (`blocks_all.py`, 1,572 hitter-seasons, mean 207
  PA per half) — the basis of everything in the current tooling;
- **odd/even event index** within a player-season (`stabilization`, 1,264 hitter-seasons) — the
  basis of the stabilization table.

They disagree slightly (bat speed .974 vs .978, wOBA .479 vs .448) because the windows and the
qualifying samples differ. **The block split is the more conservative and the more honest**,
because its two halves are separated in time and therefore share less of whatever is not talent.

## 2.2 Spearman–Brown

Averaging `k` independent replications leaves `var(T)` alone and divides `var(e)` by `k`:

```
                var(T)                 1                      k · rho_0
rho(k) = ------------------- = --------------------- = ---------------------
          var(T) + var(e)/k     1 + (1-rho_0)/(k·rho_0)   1 + (k-1)·rho_0
```

Two uses: `k = 2` corrects a half-season split to a full season (`rho = 2r/(1+r)`); `k = n/n0`
projects to any other sample size.

**Validation.** Predicts month-to-month wOBA reliability .15 against .135 measured; bat speed .94
against .919 measured. Both optimistic in the same direction by a similar margin — consistent with
the constant-`T` assumption failing, which is exactly the direction it should fail.

**Assumptions and where they break.** Exchangeability of the replications (April opponents are not
September opponents) and constant `T` inside the window (a hitter who rebuilds his swing in June
violates it outright). Both push true reliability *below* the projection.

## 2.3 Shrinkage

```
T_hat = mu + rho·(X − mu)          pct_shrunk = 50 + rho·(pct_raw − 50)
```

For a *change* rather than a level, with a per-observation standard error:

```
d_hat = d · var_true / (var_true + se²)
```

The canonical reference is Efron & Morris (1977), who shrank 18 hitters' first-45-at-bat averages
toward the group mean and beat each player's own average by ≈3.5× in total squared error,
including for the player who finished best.

**Marcel is shrinkage in disguise.** Adding `R` plate appearances of league average means the
fraction of a player's own record that survives is `P/(P+R)` — exactly the reliability of a sample
of size `P` when `R = var(e)/var(T)` in PA units. Tuning `R` *is* estimating a reliability.

## 2.4 The standard error of a within-player change

```
var_noise(n)  = var_league_observed(n) · (1 − rho(n))
var_noise(n2) = var_noise(n1) · (n1/n2)                  [noise scales as 1/n]
se            = sqrt(var_noise(n1) + var_noise(n2))
z             = (rate_now − rate_before) / se
```

Thresholds in use: `|z| ≥ 2.5` real, 1.5–2.5 weak, below 1.5 noise.

## 2.5 Effect size, which is a different question

```
delta_sd = (rate_now − rate_before) / sd_league_observed
```

`z` asks *could noise have done this*. `delta_sd` asks *would anyone notice*. They come apart in
both directions and either alone misleads:

- Arm angle, `rho = .999`: a 0.9° drift clears `z = 2.5` and is 0.07 sd. Unambiguous, meaningless.
- A strikeout rate falling 4.2 points over 242 batters faced: `z = −1.06`, `delta_sd = 0.6`. The
  honest statement is "he may well have changed this much and this sample cannot tell you."

The same distinction appears earlier in the project as "Peterson's release extension moved 0.05 ft
and Holmes's 0.01 ft, both statistically real."

## 2.6 Ceilings

The target of a forecast is itself `T + e`, so a perfect forecast of `T` scores far below 1.0.

```
R²_max = var(T) / var(T + e) ,   var(e) = E[sigma² / n_target]
```

Three ceilings exist in the project and they are **not the same quantity**:

| ceiling | definition | value |
|---|---|---|
| **realistic** | forecaster knows talent, cannot foresee drift | **0.264** (87 PA target) |
| **oracle** | also foresees drift; unreachable by construction | 0.425 |
| **block-panel** | var(T)/var(observed) on the 30-day panel | **0.2854** (96 PA target) |

Variance components behind the first two: var(baseline talent) .001190, var(one month's drift)
.000726, var(noise at 87 PA) .002588. An earlier, superseded version reported .186 at 60 PA
because it omitted the drift term; both numbers circulated for a day before reconciliation.

**Rule: never report R² without its ceiling.** 0.0335 against a ceiling of 0.2854 is 12% of what
exists, not 3% of a perfect score.

## 2.7 Inference machinery

- **Temporal holdout**, not random split. League conditions change annually (§7.4), so a random
  split lets the model see the future.
- **GroupKFold by player** inside the training years, or the model learns player identity in one
  fold and is scored on the same player in another.
- **Paired percentile bootstrap**, 3,000–4,000 resamples, same rows for both models. Unpaired
  intervals are far wider because the models' errors are highly correlated.
- **Bonferroni** where a family of tests is defined in advance (ten counts → α = 0.005).
- **Pre-registration** where an effect, not a measurement, is at stake. Reliability estimation is
  explicitly exempted: "this measures reliability, not an effect, so there is nothing to fish for."

---

# PART III — WHAT HAS BEEN MEASURED

## 3.1 Reliability of levels (split-half, Spearman–Brown, 2023–2026)

| hitters, n₀ = 207 PA | rho | pitchers, n₀ = 176 BF | rho |
|---|---|---|---|
| swing length | .982 | arm angle | .999 |
| bat speed | .974 | extension | .997 |
| attack angle | .961 | fastball velo | .997 |
| whiff% | .917 | spin rate | .994 |
| chase% | .909 | whiff% | .812 |
| exit velo | .865 | zone% | .801 |
| K% | .861 | K% | .742 |
| xwOBA | .691 | xwOBA against | .534 |
| wOBA | .479 | wOBA against | .389 |
| sweet-spot% | .370 | edge% | .228 |

**The ordering is the substantive result.** Instrument-measured quantities at the top;
outcome-accumulated quantities at the bottom. wOBA, on which the entire public discourse runs, is
below half.

## 3.2 The same fact as a sample-size requirement

Plate appearances to reach a target reliability (Spearman–Brown solved for `n`;
`k = t(1−p)/(p(1−t))`):

| metric | ρ=.5 | ρ=.7 | ρ=.8 | ρ=.9 |
|---|---|---|---|---|
| swing length | 4 | 9 | 15 | 34 |
| bat speed | 6 | 13 | 22 | 50 |
| attack angle | 8 | 20 | 34 | 76 |
| whiff% | 19 | 43 | 75 | 168 |
| exit velo | 32 | 75 | 129 | 290 |
| K% | 33 | 78 | 133 | 300 |
| hard-hit% | 45 | 105 | 180 | 404 |
| xwOBA | 93 | 216 | 371 | 834 |
| wOBA | 225 | 524 | 899 | **2,023** |
| sweet-spot% | 353 | 823 | 1,411 | **3,176** |

The `(1−t)` in the denominator makes the last column diverge: .70 → .90 is 3.9× the sample, not
1.3×. A season is ~600 PA, so wOBA needs three and a half seasons to be a 90%-real ranking.

Detection mode, the same decomposition rearranged as a power calculation:

```
n = n₀ (1−rho) var(n₀) ((z_{α/2} + z_β) / delta)²        [known baseline]
n = C / (1 − C/m)                                         [baseline of size m]
```

with no solution when `C ≥ m` — the baseline itself is too noisy, and the answer is to lengthen
the baseline rather than watch longer. Worked values: a pitcher's 1.0 mph velocity loss is
detectable in **26 batters faced**; a hitter's 1.0 mph bat-speed gain needs **369 PA** and is
undetectable against a 300-PA baseline; a 2° attack-angle change needs 215 PA; a 30-point wOBA
change needs 1,962 PA.

## 3.3 Signal share of year-over-year changes (222 hitters, 250+ PA both seasons)

| metric | sd observed | sd noise | **sd true** | signal share |
|---|---|---|---|---|
| bat speed | 1.10 | 0.43 | **1.01** | 85% |
| xwOBA | .0276 | .0146 | **.0234** | 72% |
| swing% | 3.05 | 1.67 | 2.55 | 70% |
| wOBA | .0356 | .0200 | **.0294** | 68% |
| chase% | 3.36 | 2.14 | 2.59 | 59% |
| whiff/sw% | 3.04 | 2.06 | 2.23 | 54% |
| BB% | 2.47 | 1.84 | 1.65 | 44% |
| K% | 3.45 | 2.71 | 2.13 | 38% |
| exit velo | 1.49 | 1.19 | 0.90 | 37% |
| hard-hit% | 4.61 | 3.93 | 2.42 | 27% |
| GB% | 4.35 | 3.93 | **1.86** | **18%** |

League-wide version (`calibration.json`) extends this: swing length 87%, edge seen 6%,
**sweet-spot% 0%**. Pitchers: arm angle 100%, extension 100%, velo 99%, spin 97%, down to
**BB% 1%, edge% 1%**.

**Consequence.** "+.040 of wOBA is a big move" is now quantified: against a true spread of .0294
that is 1.4 sd, above the 90th percentile of genuine movers. The project's earlier hand-set
practical floor of .015 was far too generous.

## 3.4 Signal share of month-over-month changes

| metric | signal share |
|---|---|
| arm angle | 97% |
| fastball velocity | 96% |
| swing length | 43% |
| bat speed | **34%** |
| swing% | 26% |
| chase% | 25% |
| whiff/sw% | **18%** |

Monthly resolution is usable for pitcher mechanics and close to useless for hitter discipline.

## 3.5 Persistence of within-player changes (2026, 30-day windows)

Correlation of a player's delta in window *t* with his delta in window *t+1*, against a common
prior baseline:

| metric | r | metric | r |
|---|---|---|---|
| attack angle | +.58 | chase% | +.50 |
| swing length | +.53 | whiff% | +.46 |
| bat speed | +.50 | BB% | +.43 |
| exit velo | +.42 | K% | +.37 |
| hard-hit% | +.39 | | |

Of 1,423 moves past `|z| = 2` with a following window, **47% held at least half their magnitude.**

## 3.6 Mean reversion

Monthly `d(wOBA)` mean-reverts at **−0.51 ± 0.026**: half of any month's movement is given back
the next month, mechanically. Any in-season alerting on monthly splits must account for this.

---

# PART IV — THE FORECASTING PROGRAM

## 4.1 The descriptive / reliable / predictive triangle

| metric | describes the month | repeats next month | predicts next month |
|---|---|---|---|
| wOBA | 1.000 | 0.135 | 0.065 |
| xwOBA | 0.747 | 0.321 | 0.136 |
| fitted model | 0.485 | **0.665** | **0.205** |

**The better a metric describes the period that happened, the worse it forecasts the next one.**
This is the organising fact of the whole program, and it is a direct consequence of §1.1: a
perfect description includes `e`, and `e` does not persist.

## 4.2 Q1 — does xwOBA beat wOBA for forecasting? **Yes, everywhere.**

Fit 2023–2025, scored once on 2026, 10,287 hitter-months:

| window | n | wOBA R² | xwOBA R² | edge |
|---|---|---|---|---|
| 1 month | 1,085 | **−0.0038** | 0.0153 | +0.019 |
| 2 months | 856 | 0.0366 | 0.0732 | +0.037 |
| 3 months | 318 | −0.0074 | 0.0297 | +0.037 |
| season → season | 213 | 0.1194 | 0.1274 | +0.008 |

Replicated in an independent design: 12 of 12 season × window combinations, bootstrap intervals
excluding zero in all 12, partial β on xwOBA 0.16–0.43.

**Two structural findings inside this.**

1. **Once you know xwOBA, wOBA is negative information.** Fitting `next ~ b1·wOBA + b2·xwOBA`
   within input-PA buckets, `b1` is negative in every bucket above 55 PA: −0.022, −0.104, −0.075,
   −0.041. The current 30-day carry model reproduces this: `w` = −0.018, `x` = +0.228.
   **Caveat that must travel with it:** wOBA and xwOBA correlate ~0.6–0.7, so a negative partial
   coefficient is a textbook suppression pattern. It is *not* evidence that beating your xwOBA is
   bad. It is evidence that xwOBA carries the signal and the residual carries the noise.
2. **A failed prediction, unexplained.** xwOBA's edge over wOBA was predicted to decline
   monotonically with window length. It is humped — peaking at 2–3 months, nearly vanishing over a
   full season. No mechanism (backlog S20).

## 4.3 Q2 — can anything beat xwOBA?

One-month horizon, 2026 holdout, incremental feature sets:

| feature set | k | ridge | GBM |
|---|---|---|---|
| wOBA only | 1 | −0.003 | −0.012 |
| xwOBA only | 1 | 0.015 | 0.007 |
| + contact quality | 10 | 0.024 | 0.014 |
| + discipline | 18 | 0.030 | 0.027 |
| + context & playing time | 39 | 0.044 | 0.049 |
| + swing geometry | 48 | 0.043 | **0.057** |

**The uncomfortable control: playing time alone scores 0.0316 — double xwOBA's 0.0153.** Removing
it costs the full model a fifth. This is the manager's private information about a player's health
and role, not a hitting skill, and it should be reported separately rather than buried in a
feature set.

Sort-spread version (2026 hitter-months, realised next-month wOBA spread between top and bottom
fifth): what he just hit **.0098**, xwOBA .0228, the fitted model **.0406**. wOBA is also badly
*calibrated*: its bottom fifth claimed .247 and then hit .329.

## 4.4 The Marcel benchmark — the models draw, and the drawing is the finding

One-month horizon, 2026 holdout, 3,000-sample bootstraps, with two fairness corrections made
*against* the project's own models (Marcel's regression constant tuned on the training years;
models re-run on the same weighted history):

| forecaster | R² | 95% |
|---|---|---|
| this month's xwOBA | 0.015 | [−.016, +.044] |
| **Marcel, tuned** | **0.058** | [+.016, +.098] |
| 48 Statcast features, current window | 0.057 | [+.013, +.097] |
| weighted Statcast history, 19 features | 0.062 | [+.017, +.105] |
| everything combined | 0.060 | [+.016, +.103] |

48-feature minus Marcel = **−0.002 [−0.039, +0.033], P(model better) = 0.46**. Everything minus
Marcel = +0.002, P = 0.55. Every head-to-head gap straddles zero.

Season level, n = 245: Marcel tuned **0.164**; a shrunk average of past xwOBA **0.166** (P = 0.53,
a tie); Marcel classic (R = 1200) 0.075; a 20-feature GBM **−0.060**, worse than predicting league
average for everyone (gap −0.228, P = 0.00), on 267 training seasons.

**Marcel+ decomposition — the only free lunch found:**

| step | R² | vs classic | P |
|---|---|---|---|
| Marcel classic (R = 1200) | 0.0745 | — | — |
| built on xwOBA history | 0.0770 | +0.0038 | 0.53 |
| **+ regress harder (R = 3000)** | **0.1640** | **+0.0928** | **0.97** |
| + structural gap adjustment | 0.1516 | +0.0798 | 0.93 |

One constant more than doubles R². The past→future correlation of a hitter's weighted record is
only **0.40**, so the classic constant badly under-regresses. Marcel's age adjustment is also real:
removing it costs 0.062 (P = 0.01).

**Where Statcast does win — thin track record.** Monotone across four history quartiles:

| prior history | n | Marcel | model | gap | P(model better) |
|---|---|---|---|---|---|
| least | 272 | 0.007 | 0.056 | **+0.049** | **0.94** |
| second | 271 | 0.042 | 0.052 | +0.011 | 0.65 |
| third | 271 | 0.117 | 0.105 | −0.014 | 0.31 |
| most | 271 | 0.048 | 0.008 | −0.040 | 0.11 |

By age, only 22–25 has a CI excluding zero (+0.065 [+.003, +.125], P = 0.98). **With 4 age buckets
× 4 history quartiles = 8 tests, one CI excluding zero at 5% is what chance produces.** Recorded as
a hypothesis for 2027, not a finding. A correction is attached: "expected metrics beat track record
for young players" is **not** supported — xwOBA alone loses to Marcel in *every* age bucket. The
supportable claim is that a rich measurement model beats a track-record forecast where the track
record is thin, and loses where it is thick.

## 4.5 The 30-day panel (current tooling)

Windows of two half-month blocks stepping through each season; baseline = strictly prior blocks;
target = the following window. Fit 2023–2025, scored on 2026 (3,884 train / 1,044 test):

| model | 15d | 30d | 45d |
|---|---|---|---|
| M1 recent wOBA + prior wOBA | −0.001 | 0.0038 | 0.0072 |
| M2 + xwOBA (current and prior) | 0.0222 | 0.0335 | 0.0385 |
| M3 + input levels | 0.0313 | 0.0297 | 0.0395 |
| M4 + input **changes** | 0.0302 | 0.0301 | 0.0351 |
| ceiling | 0.277 | 0.285 | 0.245 |

**M4 − M2 never excludes zero:** +0.0079 [−0.0023, +0.0178] at 15 days, −0.0034 [−0.0176, +0.0097]
at 30, −0.0033 [−0.0238, +0.0166] at 45. The 15-day sign points where theory predicts —
corroboration should matter most where the results sample is smallest — and is not significant.

Effect size of the input-change composite: **+0.004 of wOBA per standard deviation.** Splitting hot
streaks by whether the body corroborated moves the carry rate from 27% to 32%, gap CI
[−12%, +22%], P(gap > 0) = 0.73.

**The paradox to keep.** Those same input changes persist strongly (§3.5, r = .37–.58) and do not
move next month's wOBA. Persistence of an input and predictive power for an outcome are different
properties, and the second requires the input to be *large in outcome units*. It is not: a full
standard deviation of body change is worth four points of wOBA, against a wOBA noise sd many times
that at monthly samples.

## 4.6 Pitchers

Next-season wOBA-against (426 train, 193 test):

| predictor | R² |
|---|---|
| wOBA against | 0.1263 |
| **xwOBA against** | **0.1695** |
| K% and BB% only | 0.1558 |
| xwOBA + K% + BB% | **0.1866** |

xwOBA-against beats wOBA-against by 34% relative — a much larger edge than the hitter version. And
**K% and BB% alone nearly match expected wOBA using no batted-ball data at all**, which is a clean
reproduction of DIPS (Voros McCracken, 1999) on modern data.

30-day panel for pitchers: M1 0.0292, M2 0.0512, ceiling 0.3537 (14% of it).

**xERA carries no information beyond xwOBA.** Savant's own glossary: "a simple 1:1 translation of
xwOBA, converted to the ERA scale." A monotone rescaling. True ERA is not reconstructible from the
archive at all, because earned-versus-unearned is a scorer judgement not present in the data.

---

# PART V — THE LUCK GAP (wOBA − xwOBA)

The project's one genuinely open empirical question, and the one with the longest error history.

**Within a season the gap is noise.** Split-half reliability of the gap itself: **.164** (hitters),
**.213** (pitchers).

**Across seasons, for hitters, it is a small real trait.** Season-to-season correlation of the gap
across three independent year pairs: **+0.267, +0.302, +0.238** (corrected values; the pre-
correction figures were +0.291, +0.280, +0.272 — the finding is robust to the `woba_value` fix).
For pitchers the same quantity is **+0.104, −0.021, +0.161** — i.e. nothing. A hitter trait, not a
pitcher trait, which is itself informative.

Magnitude: sd of the gap ≈ **.019** at season scale; .042 / .031 / .026 at 1 / 2 / 3 months.
Persistent over-performers across 3+ seasons: Altuve +.048, Friedl +.048, Paredes +.040.
Under: S. Perez −.024, Soto −.021, Conforto −.021.

**What explains it: almost nothing, and the two mechanisms proposed have both failed.**

- Batted-ball profile regression, 849 player-seasons with 300+ PA: multiple **R² = 0.133**. The
  largest single predictor is **average exit velocity at −0.335** — hard-hit hitters
  systematically *underperform* their xwOBA. ~87% unexplained, and that is an upper bound on luck,
  not an estimate of it, because park, defence faced and speed are all absent.
- **Retracted mechanism 1** — ground balls and reached-on-error. Appeared to explain the gap
  (ground balls +.0234 per batted ball, "52% of it is reached-on-error"). Killed entirely by the
  `woba_value` correction: the corrected ground-ball gap is **+.0008**. The mechanism was measuring
  the project's own numerator.
- **Retracted mechanism 2** — the same effect used as a projection adjustment. Correlation of
  prior GB rate with the current season's gap: **−0.002 train, +0.113 test**. Magnitude check:
  .0234 per grounder × .09 sd of GB rate × .65 BIP/PA = **.0014 of wOBA per sd**, against a gap sd
  of .0188 — **7.3% of the gap's spread**. Adding a player's own prior gap is actively harmful
  (−0.181, P = 0.01).
- **Not a disguised mechanical change.** Bat-speed change 2025→2026 against the 2026 gap, 222
  hitters: **r = −0.036 [−0.167, +0.096]**. Null.
- Sprint speed is **effectively null**: −0.00093 wOBA per ft/s, R² = 0.0034, n = 389, F ≈ 1.3,
  p ≈ 0.25. Across the full 22.1–30.5 ft/s range that is ~8 points of wOBA.

**What survives.** xwOBA over-rates popups by 17.6 points (7% of balls in play, so small). The
persistent hitter gap is real, replicated three times, and **unexplained**.

**Candidate explanations, none tested:** xwOBA is blind to spray angle, park, defensive
positioning and a hitter's own ability to beat out grounders. Any of these could be the persistent
trait. The EV coefficient's sign (−0.335) suggests defenders position for hard contact, or that
xwOBA over-credits the top of the EV range.

---

# PART VI — THE PITCH-LEVEL PROGRAMS (a set of credible nulls)

These matter statistically because they are the project's best examples of **nulls that are
believable**, and of the design feature that makes a null believable.

## 6.1 Sequencing: changing the pitch does not help

League, count-baselined, 525,900 paired pitches: repeating beats changing by **+0.58 runs per 100,
95% [+0.44, +0.71]**. Largest in even counts (+0.97) and two-strike counts (+0.92). Pitchers
already change about two thirds of the time.

**The positive control.** Within pitcher, each against himself in the same count, 360 pitchers:
**+0.563 [+0.425, +0.702]** — essentially identical to the pooled estimate, so the effect is not
composition. This result exists explicitly to license the nulls around it: *a null is uninformative
unless the design can be shown to detect something.*

**And the precision limit is stated rather than assumed:** the design detects ~0.56 runs/100 at
this sample; it says nothing about 0.15. A formal power calculation has not been done and would
replace this reasoning by analogy.

**Individual pitchers: not identifiable.** One starter-season ≈ 2,900 pitches, se ≈ 1 run per 100 —
nearly twice the league effect size. Of five 2025 innings leaders, one cleared at 95%, which is
what chance produces. Persistence across seasons: **r = −0.069 [−0.249, +0.116]**, 115 pitchers.

## 6.2 Pitch selection by count: between-pitcher selection, not skill

League level, 2025: fastballs beat offspeed in every count with 0 or 1 strike and lose in every
2-strike count, no exceptions. The 2-2 gap is **−0.80** runs/100.

**Pre-registered within-pitcher test: the finding did not survive.** The 2-2 gap within pitcher is
**+0.12 [−0.21, +0.45]** across 351 pitchers. The league-level −0.80 was almost entirely
between-pitcher selection. With Bonferroni across ten counts (α = 0.005), only 1-2 survives
(+0.44 [+0.19, +0.70]). Persistence of any per-pitcher gap: 2-2 **r = +0.03 [−0.14, +0.20]**.

Conclusion as written: *there is no per-pitcher pitch-selection recommendation supportable from
three seasons of public data.*

## 6.3 Two more clean nulls, and one canonical artifact

- **Tunnelling.** 340k swings; excess whiff by release-point gap: −0.14 / +0.14 / +0.08 / −0.24 pp.
  No ordering. (Caveat: release distance is not trajectory separation at the commit point.)
- **Arsenal breadth does not blunt the times-through-the-order penalty.** The TTO penalty itself is
  real and within-pitcher (+0.0094 → +0.0146 from pass 1 to pass 3, +24 points). Slope of penalty
  on effective arsenal size, 337 starter-seasons: **−0.0027 ± 0.0040**, null.
- **Velocity decay — keep as the teaching case.** Between pitchers, steeper decay predicts a
  *smaller* late penalty, **r = +0.905 across quintiles**. Within pitcher, 8,250 starts:
  **+0.0031 ± 0.0024**, null. Monotone across five bins and still entirely selection.

## 6.4 Counts: the count matters about twice as much as the hitter

Range of wOBA across the 12 counts reached: **.351** (.2074 at 0-2 to .5580 at 3-0). Range across
286 hitters with 1000+ PA: **.185**. Ratio **1.89×**; on standard deviations, .0992 vs .0247 = 4×.
The first strike is the most expensive event in baseball: 0-0 → 0-1 costs −.048, 0-1 → 0-2 another
−.068.

(The absolute wOBA values in that table are ~6–9 points high pending the `woba_value` re-run; the
relative structure and the 1.89× ratio are unaffected.)

## 6.5 The ABS natural experiment

Between-catcher spread in extra strikes per 1000 taken pitches: 16.58 (2023), 15.54, 13.80,
**10.57 (2026)**. The pre-registered prediction — that framing spread would collapse under
automation — was **wrong in its premise**: 2026 is a challenge system, not full automation, and the
rule should have been checked before the prediction was written.

**Pre-trend correction.** The raw drop is 31% against the 2023–2025 average, but the series was
already falling ~1.4 units a season. Extrapolation predicts 12.41 for 2026 against 10.57 observed,
so the portion plausibly attributable to ABS is roughly **15%, not 31%**. Reporting the raw drop
would have doubled the effect. This is a four-point interrupted time series with one post-period —
the weakest version of that design.

---

# PART VII — THE ERROR TAXONOMY

Eleven documented errors. What makes them useful is that they are **not eleven different mistakes**
— they are seven recurring failure modes. This is the most transferable content in the project.

### Type 1 — Denominator mismatch
*The luck-gap strikeout regression.* Full wOBA (strikeout = 0) compared against xwOBA measured on
contact only. Manufactured a large negative gap for every high-strikeout hitter; the regression
then "explained" the gap with the strikeout rate that had created it. **r = −0.748, R² = 0.719**,
entirely an artifact.
**Signature:** an R² far above anything else in the domain.

### Type 2 — Circularity / outcome-derived predictors
*The gap explanation, first version.* `gb_single` was the top explainer at **R² = 0.246**. A ground
ball that finds a hole *is* both a `gb_single` and a positive gap — the same event on both sides.
Its own split-half reliability is .193. Fixed by splitting predictors into ante-hoc versus
outcome-derived: honest ante-hoc R² is **0.034** at one month, 0.137 at three.
**Signature:** a predictor whose definition contains the outcome's definition.

### Type 3 — Definition mismatch in a provider column
*`woba_value` is not wOBA.* It credits field_error at 0.900, fielders_choice at 0.900, a dropped
third strike at 0.700 — it tracks *whether the batter reached base*. Every wOBA in the repo was
inflated ~9 points; the corrected numerator restricts to
`events IN ('single','double','triple','home_run','walk','hit_by_pitch')` and reconciles to Savant
within +.002 / +.003.
**Signature:** a systematic offset with correlation ~0.99 against a published version. That is a
definition mismatch, not noise — chase the events, not the arithmetic.
**Standing rule:** any metric computed from pitch-level columns is first reconciled against an
independent published version of the same metric for the same players.

### Type 4 — The ruler changed
*`sz_top` redefined in 2026.* Distinct league-wide values: 321,120 (2024), 353,643 (2025),
**390 (2026)** — MLB replaced a per-pitch operator estimate with a per-batter formula. The first
zone analysis, measured relative to `sz_top`, reported the top of the zone **expanding +32.8pp**.
Redone in absolute feet it had **contracted −23.5pp**.
**Signature:** a distinct-value count that collapses between seasons.
**Standing rule:** any cross-season analysis is measured in absolute physical units.

### Type 5 — Leakage
*The project's own Marcel benchmark.* `hist_sums(b, y, thru=99)` included the season being
forecast. Reported **R² = 0.575** with the tuner driving the regression constant down to **200**.
True value **0.164**.
**Signature:** a baseline performing implausibly well, *combined with* tuning that says "barely
regress." Leaked data makes a player's own record look far more predictive than it is.

### Type 6 — Between-group variation mistaken for a within-group effect
*The 2-2 pitch-selection finding* (league −0.80 → within-pitcher +0.12 [−0.21, +0.45]) and
*velocity decay* (between-pitcher r = +0.905 across quintiles → within-pitcher +0.0031 ± 0.0024).
**Signature:** a clean monotone pattern across bins of a variable players *choose*.
**Standing rule:** every cross-sectional claim gets a within-unit version before it is believed.

### Type 7 — Testing something adjacent to the claim
Four distinct instances, and the most insidious category because nothing looks wrong:

- **Detectability substituted for the claim.** "Chase rate is a fast-moving signal" was scored yes
  because chase *changes were detectable*. The claim was that chase *leads* production. Within
  hitter, 1,119 month-triples: `d(chase)_t → d(wOBA)_{t+1}` = **+0.046 ± 0.036 (null)**;
  `d(chase)_t → d(wOBA)_t` = **−0.370 ± 0.041 (real)**. Coincident, not leading. Rescored no.
- **Reliability of a level substituted for reliability of a change.** Bat speed 85% signal at
  season scale, **34%** month over month. The recommendation that "bat speed works monthly, even
  weekly" was superseded.
- **Significance substituted for magnitude.** Changes judged by clearing their own error bar plus a
  hand-picked practical floor "which was an opinion." Baty's GB% **−10.38 raw → −1.72 believable**
  once shrunk by 18% signal share.
- **A maximum statistic reported as a test statistic.** The Vientos changepoint `t = 2.1` is the
  *maximum* t over ~57 candidate split dates. The date is a reasonable estimate of where a change
  happened; it is not evidence that one did. A valid version bootstraps the max statistic.

### Ancillary — bookkeeping failures with statistical consequences
Offseason-straddling month pairs counted 2025-09 → 2026-04 as a monthly change (and produced the
largest "monthly" move in the Mets analysis). A corrupted database under-reported its own row count
by 23,523 pitches with no error raised. `estimated_woba_using_speedangle` is populated on
strikeouts, walks and HBP while `xBA` and `xSLG` still follow the old NULL convention — two columns
in the same row disagreeing, which silently counted strikeouts as balls in play.

---

# PART VIII — THREATS TO VALIDITY, WITH DIRECTION

| # | threat | direction | addressed? |
|---|---|---|---|
| T1 | **Split halves are not independent.** Odd and even half-months share opponents, park, weather, and the same underlying injury. Any positive residual correlation inflates `r` and therefore every `rho`. | **inflates all reliabilities** | No. Both independent checks came in below the projection (.135 vs .15; .919 vs .94), which is this bias's signature. |
| T2 | **Spearman–Brown extrapolated ~7× outside where it was measured** (fit at 207 PA, used at 30). | unknown sign; constant-`T` violation deflates truth | Partially — the two validation points bracket the working range. |
| T3 | **Survivorship.** Reliabilities come from players with ~207 PA in both halves; slumping players get benched and vanish. | unknown; moves both `var(T)` and `var(e)` | **No.** Flagged in the earliest entry and never quantified. |
| T4 | **Playing time is in the feature set.** It alone scores 0.0316, double xwOBA. | inflates model R² | Ablation run (0.057 → 0.044) but kept in headline numbers. |
| T5 | **σ² = 0.2258 carries every ceiling.** | a 20% error moves every "share of ceiling" figure | No sensitivity analysis. |
| T6 | **Ceilings assume constant talent inside the target window**, which §2.2 already knows is false. | ceilings are too high, so shares-of-ceiling are too low | No. |
| T7 | **Multiple comparisons across the whole project.** 8 age×history tests; 100 tests in the Mets profile (18 "significant" appeared against ~5 expected); dozens of specifications overall. | inflates the survivors | Partially — Bonferroni where a family was pre-specified, and the expected-false-positive count is stated where it was not. |
| T8 | **The 2026 holdout has been scored dozens of times** — four specifications × four window lengths × two player types × several PA floors. | inflates every 2026 figure by an unknown amount | Now acknowledged (D28) and replaced by a sealed 2027 pre-registration. |
| T9 | **Suppression in the carry model.** Negative coefficient on recent wOBA with corr(w,x) ≈ 0.6–0.7. | not a bias in prediction; a bias in *interpretation* | Flagged here; was previously quoted without the caveat. |
| T10 | **No park, opponent, defence or aging adjustment anywhere** except Marcel's age bump. | unknown | No. |
| T11 | **Bat speed is measured at contact**, so "faster swings produce better outcomes" is partly "swings that connect well are recorded as fast." The within-hitter version does not fix it. | inflates the bat-speed→outcome relationship | Acknowledged; the whiff result is clean because bat speed there is measured on misses too. A causal version needs intended swing speed, which is not public. |
| T12 | **Bat speed is park-dependent.** Home−road sd 0.23 mph, cross-park correlation +0.456 — a shared installation effect. Against a true YoY spread of 1.01 this is not negligible for small changes. | adds a non-talent component to every bat-speed comparison | Measured, not corrected. |
| T13 | **The `woba_value` correction was not fully propagated.** The Marcel conclusions "stand" on the argument that R² comparisons are near-invariant to a near-constant additive offset in the target. **Not re-run.** | unknown, probably small | **Outstanding debt.** |

Two numeric inconsistencies remain unreconciled in the log and should be resolved before anything
is compiled: the gap's standard deviation is quoted as **.0191** in one entry and **.0188** in
another; Baty's shrunk GB% appears as **−1.72** in one entry and **≈ −1.9** in another.

---

# PART IX — OPEN QUESTIONS, RANKED BY ANSWERABILITY

**Answerable with data already on disk:**

1. **What explains the persistent hitter gap?** Add park (home team of the game) and sprint speed
   to the gap regression; if exit velocity survives, residualise the gap on it. Test whether the
   trait is spray angle. This is the project's best open question.
2. **Why is xwOBA's edge over wOBA humped in window length rather than monotone?** No mechanism.
3. **Does a *change* in bat speed predict a change in production?** Stated repeatedly as "the
   untested step" and still untested. §4.5 gives a partial answer for a composite; the single-metric
   version has not been run.
4. **Quantify survivorship (T3).** Compare reliabilities computed on the full sample against those
   computed on players who also appear in the following season.
5. **A formal power calculation for the sequencing design**, replacing the current reasoning by
   analogy from the positive control.
6. **Bootstrap over the max statistic** for any changepoint claim.
7. **Whether opponents adjust in dimensions other than pitch mix** — location within the zone is
   already on disk.
8. **A sensitivity analysis on σ² (T5).**

**Answerable only with data not yet obtained:**

9. Steamer / ZiPS benchmark — requires a manual pre-season CSV export. The continuously-updated
   `steameru` files must not be used: they already incorporate the season being forecast and would
   reproduce the leakage of Type 5 exactly.
10. Umpire IDs from StatsAPI, to test whether umpire-to-umpire variation fell in parallel with
    catcher framing (the deterrence prediction).
11. Pitcher fixed effects in the framing model, to establish whether the residual spread is catcher
    skill at all.
12. `era` / `xera` backfill — blocked, and in any case xERA is a monotone rescaling of xwOBA.

**Not answerable with public data:**

13. Any causal claim about bat speed, which requires intended swing speed rather than speed at
    contact.
14. ERA decomposition, because earned-versus-unearned is a scorer judgement absent from the archive.

**Sealed for 2027** (`PREREGISTRATION.md`): P6 (M2 beats M1 by ≥ +0.015), P7 (M4 does not beat M2),
**P8 (M2's 2027 R² comes in below its 2026 figure of 0.0335)**, P9 (the gap replicates in
[+0.15, +0.40]), P10 (input-delta persistence stays in [+0.30, +0.65]).

---

# APPENDIX — MEASURED CONSTANTS

**Variance components.** σ² per PA = 0.2258 (sd 0.475). Month-to-month skill drift sd = .0381.
True talent spread across 670 hitters sd = .0345. var(baseline talent) .001190, var(one month's
drift) .000726, var(noise at 87 PA) .002588.

**Ceilings.** Realistic 0.264; oracle 0.425; block-panel 0.2854 (hitters, 96 PA), 0.3537
(pitchers). By PA per month: .144 (40), .186 (60), .243 (100), .336 (250), .395 (600) — this last
series omits drift and is superseded by 0.264.

**Regression constants.** Marcel weights 5/4/3. Classic R = 1200; tuned R = 3000; leaked version
chose R = 200. Past→future season correlation of a weighted record: 0.40. Monthly `d(wOBA)` mean
reversion −0.51 ± 0.026. League-average gap constant +.0066.

**Gap.** sd ≈ .019 season, .042 / .031 / .026 at 1 / 2 / 3 months. Split-half .164 (hitters), .213
(pitchers). Year-pair correlations +0.267 / +0.302 / +0.238 (hitters), +0.104 / −0.021 / +0.161
(pitchers).

**Platoon.** Mean advantage +0.0311 wOBA; observed spread .0414, noise .0217, true .0353, signal
share 72% — i.e. 28% of any published platoon leaderboard's spread is noise.

**Instrumentation.** Bat speed clamped at exactly 88.0 mph in all four seasons; ~0.5% of values
under 20 mph are failed reads. Bat tracking begins July 2023 (announced May 2024; Savant
back-processed). Home−road bat speed sd 0.23 mph, exit velo 0.46 mph, cross-park correlation +0.456.

**Framing.** Between-catcher sd in extra strikes per 1000 taken pitches: 16.58 / 15.54 / 13.80 /
10.57. Pre-trend ≈ −1.4 per season; counterfactual 2026 = 12.41.

**Scale.** 2.84M pitches; 2.07M paired pitches; 525,900 count-baselined pairs; 340k tunnelling
swings; 10,287 hitter-months; 16,228 within-season month pairs; 8,250 starts; 1,264 hitter-seasons
(stabilization); 1,572 hitter-seasons and 1,789 pitcher-seasons (block split-half); 849
player-seasons at 300+ PA (gap regression); 709,492 PA reaching 0-0.
