# Pre-registration, sealed 2026-09-15

Written before the 2027 data exists. Nothing below may be edited except to record an outcome.

## Why this file exists

The 2026 season entered this project as a temporal holdout and has since been scored dozens of
times (D28). That is not misconduct, it is the ordinary way a holdout dies: every specification
you try and reject is a degree of freedom you spent, and after enough of them the "out-of-sample"
number is an in-sample number wearing a costume. The standard fix in fields that take this
seriously — ClinicalTrials.gov since 2005, the AEA RCT registry since 2013, Registered Reports in
psychology since 2013 — is to write the prediction down first, in public, with the analysis plan
attached, so the result cannot be reverse-engineered from the outcome.

## The frozen specifications

All models are OLS on the panel built by `streaks.py --part validate`, 30-day windows
(W = 2 half-month blocks), floors 60 / 80 / 60 PA, baseline = strictly prior blocks of the same
season, target = wOBA in the following 30 days. Coefficients are refit on 2023-2026 and scored
once on 2027. No tuning, no floor changes, no metric substitutions.

```
M1  y ~ w + w_base
M2  y ~ w + w_base + x + x_base
M4  y ~ w + w_base + x + x_base + in_level + in_delta
```

## The predictions

| # | prediction | fails if |
|---|---|---|
| **P6** | M2 beats M1 on 2027 by at least +0.015 R2 | delta < +0.015 |
| **P7** | M4 does **not** beat M2 by a significant margin; the 95% paired-bootstrap CI on R2(M4) − R2(M2) contains zero | the CI excludes zero in either direction |
| **P8** | M2's 2027 R2 falls below its 2026 figure of 0.0335 | 2027 R2 >= 0.0335 |
| **P9** | The hitter wOBA − xwOBA gap replicates again: mean standardized gap in 2026→2027 is positive and within [+0.15, +0.40] | outside that interval |
| **P10** | Window-to-window persistence of input deltas in 2027 stays in [+0.30, +0.65] for all nine input metrics | any metric falls outside |

P8 is the uncomfortable one and it is the point of the file. If 2026's 0.0335 was partly the
product of having looked at 2026 many times, the clean number should come in lower. A prediction
that your own headline figure will shrink is the only kind that costs anything to make.

## Analysis plan

`streaks.py --part validate --window 2` run once on the 2027 panel, paired percentile bootstrap
with 4,000 resamples for P7, seed 7. Outcomes recorded below, whatever they are.

## Outcomes

| # | result | recorded |
|---|---|---|
| P6 | — | |
| P7 | — | |
| P8 | — | |
| P9 | — | |
| P10 | — | |

---

# Addition, sealed 2026-09-20

Appended, not edited: everything above was sealed 2026-09-15 and is untouched. This section adds
one prediction that could not be written earlier because the question did not exist yet.

## Why this one is pre-registered rather than backlogged

Backlog S34 lists five hypotheses about whether the end of a season says anything about the next
one. Four can be tested now. This one cannot: it needs an age interaction, and block-level data
covers only 2023–2026 — three season transitions, one of them a development set (D28). It is also
the most attractive of the five, which is exactly the combination that gets a result tuned into
existence. So it is written down now, before the data to test it exists.

## The claim

Marcel's age adjustment is two hard-coded league-wide constants, and removing it costs 0.062 of
R² (FINDINGS 2026-09-12) — so age carries real weight, applied bluntly. Aging is a *within-season*
trend, and a season average blurs it. If a hitter is declining, the decline should show up late in
the season before it shows up in the next season's total, and Marcel cannot see it.

## Frozen specification

Population: hitters aged 32 or older on Opening Day of season Y, with at least 300 PA in Y and at
least 300 PA in Y+1. Control group: hitters aged 27 or younger on the same footing.

```
late_delta = wOBA over the final 45 days of Y  -  wOBA over all strictly earlier blocks of Y
residual   = actual wOBA in Y+1  -  Marcel projection for Y+1 (tuned as in marcel3.py)

model:  residual ~ b * late_delta        fit separately in each age group
```

Marcel is refit on seasons before Y only. No other covariate, no tuning, one look.

## The predictions

| # | prediction | fails if |
|---|---|---|
| **P11** | Among hitters 32+, `b` is positive with a 95% bootstrap CI excluding zero | the CI contains zero, or `b` is negative |
| **P12** | `b` is larger among the 32+ group than among the 27-and-under group, and that difference's 95% CI excludes zero | the CI contains zero, or the younger group's `b` is larger |
| **P13** | Adding `late_delta` to Marcel improves R² for the 32+ group by at least +0.02 | the gain is under +0.02 |

P12 is the one that matters. P11 alone could be true for reasons that have nothing to do with age
— a late-season slump is partly real for anyone, at any age, which is what the persistence ladder
already says. The age-specific claim is the only one that would tell us something Marcel does not
already know, and it is the one most likely to fail.

## When it may be run

Not before six season transitions of block-level data exist — 2023→2029 at current accumulation,
or sooner if the 2015–2022 pitch-level backfill is ever run. Running it on three transitions and
reporting the result would make this file decorative.

## Analysis plan

Paired percentile bootstrap over players, 4,000 resamples, seed 7. Run once. Outcomes recorded
below whatever they are.

| # | result | recorded |
|---|---|---|
| P11 | — | |
| P12 | — | |
| P13 | — | |
