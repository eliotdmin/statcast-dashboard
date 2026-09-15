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
