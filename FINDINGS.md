# Findings

A dated log of what has been tested, what the number was, and what it does and
does not show. Append; do not rewrite. A finding that turns out wrong gets a new
entry that supersedes the old one, with both left visible — the record of what
was believed and why is the point.

Every entry follows the same shape: **Question / Result / What it shows / What it
does not show / Next.**

---

## 2026-09-10 — Does xwOBA actually predict better than wOBA?

This is the premise the entire dashboard rests on, and it had never been run.

**Question.** Out of sample, does period-1 xwOBA predict period-2 wOBA better
than period-1 wOBA does?

**Result.** Yes, in 12 of 12 season × window combinations, with bootstrap
intervals excluding zero in every one.

| season | Δr @15d | @30d | @45d | @60d | β partial range |
|---|---|---|---|---|---|
| 2023 | +0.059 | +0.061 | +0.101 | +0.054 | 0.16 – 0.33 |
| 2024 | +0.085 | +0.073 | +0.087 | +0.087 | 0.25 – 0.36 |
| 2025 | +0.089 | +0.098 | +0.104 | +0.137 | 0.22 – 0.43 |

**What it shows.** Contact quality carries information beyond what a player's own
results already told you. `β partial` is the standardized coefficient on xwOBA1 in
`wOBA2 ~ wOBA1 + xwOBA1`, so it is free of the shared-term coupling that makes
naive versions of this test look impressive when nothing is there. At 0.22–0.43
it is a real independent contribution.

**What it does not show.** That the future is predictable. The absolute
correlations are 0.10–0.33 — contact quality beats results at forecasting a
short window, and a short window is still mostly noise. Read the dashboard as
"who is mispriced," not "who is about to break out." Survivorship bias remains
uncorrected: benched players vanish from period 2.

**Next.** Re-run including 2026 once the season completes. Consider whether the
150 PA gate is right; metrics stabilise at different rates and one threshold
cannot be correct for all of them.

---

## 2026-09-10 — How large is the speed effect on the luck gap?

The README asserts that fast hitters persistently out-hit their xwOBA and that
the model will keep flagging them as regression candidates. That assertion had
never been measured.

**Question.** How much of a hitter's luck gap is explained by sprint speed?

**Result.** Coefficient −0.00093 wOBA per ft/s, R² = 0.0034, n = 389 (2026 only).
Across the full observed range of 22.1 to 30.5 ft/s that is about **8 points of
wOBA between the slowest hitter in baseball and the fastest**. With n=389 and
that R², the coefficient is not statistically distinguishable from zero
(F ≈ 1.3, p ≈ 0.25). The largest correction to any player's z-score is 0.17,
and seven of the ten largest movers are catchers.

**What it shows.** The sign is right — faster hitters do have more negative luck
gaps. The magnitude is far smaller than the README implies, and below the noise
the flagging threshold operates in.

**What it does not show.** That the effect is absent. One partial season,
range-restricted (the slowest players do not reach 150 PA), and fitted as a
straight line when the relationship may only exist in the 29+ ft/s tail.

**Next.** Backfill sprint speed for 2023–2025 (`backfill.py` now does this) and
refit on four seasons. If the coefficient stays this small, delete
`outlook_adj` rather than carrying an unused feature. The README's companion
claim about shift-beaters is separately untested and the 2023 rule change gives
a natural experiment.

**Status.** `outlook_adj` is computed and displayed but NOT used for flagging,
pending the four-season refit.

---

## 2026-09-10 — Does changing the pitch make it harder to hit?

**Question.** Is a pitch harder to hit when it differs from the pitch before it?

**Result.** No — the reverse. Changing the pitch is worth **0.60 runs per 100
less** to the pitcher than repeating it, and produces **1.26 fewer whiffs per
100**, across 2.07M paired pitches, holding the count fixed.

The count was the obvious confound and it is not the explanation: adjusting for
it makes the gap *wider* than the raw comparison. The penalty roughly doubles in
two-strike counts (1-2: −1.13, 2-2: −1.07). It survives conditioning on what the
previous pitch did — negative after a ball (−0.65), a called strike (−0.52), a
foul (−0.23), and a whiff (−0.66).

Two supporting cuts: whiff rate on offspeed following a fastball peaks at a
6–11 mph velocity drop and declines beyond it, so bigger gaps do not help more;
and consecutive fastballs get *more* effective, not less (first −0.32,
second +0.32, third +0.43 rv/100).

**What it shows.** A robust description: in four seasons, pitches that repeat
outperform pitches that change, within every count and every previous-pitch
outcome.

**What it does not show.** That any given pitcher should repeat more. Sequence is
chosen, not assigned. Pitchers with one dominant pitch repeat it, and those
repeats are good because the pitch is good. Pitchers already change about two
thirds of the time, so observed repeats are the ones they were most confident in.

**Next.** The causal question needs within-pitcher variation — compare a pitcher
to himself, holding count and previous outcome fixed. The useful question is not
"should pitchers mix more" but **"are there specific pitchers who mix too much"**,
which this database can answer and which is a genuinely novel angle.

---

## 2026-09-10 — Three data conventions that were silently wrong

Each of these came from an integrity check that asserted textbook behaviour and
failed against the actual database. None were known when the check was written.

**xwOBA now carries non-contact events.** `estimated_woba_using_speedangle` is
populated on PA-ending strikeouts (0.000), walks (0.698) and HBP (0.729) — the
long-standing public understanding is that it is NULL there. Consequence: a null
check is no longer a batted-ball filter; use `type = 'X'`. `analyze.is_bip` was
using the null check and was counting strikeouts as balls in play. `xBA` and
`xSLG` still follow the old convention, so two columns in the same row disagree.
Verified consistent across all four seasons, so there is no cross-season break.

**Bat tracking exists from July 2023.** Zero rows before 2023-07, then continuous
coverage. The public announcement was May 2024; Savant back-processed the 2023
second half. Distributions are indistinguishable across seasons (mean bat speed
69.6 in 2023 vs 69.5 in 2024), so the older data is usable. Two artefacts: the
maximum is exactly 88.0 mph in all four seasons, which is a clamp rather than a
physical limit, and ~0.5% of values fall under 20 mph, which are failed reads.

**The strike zone changes definition in 2026.** `sz_top`/`sz_bot` were
operator-set per pitch through 2025 and are ABS-defined from batter height from
2026. Distinct `sz_top` values: 348,556 in 2025 against 390 in 2026. Every
zone-derived metric — zone rate, chase rate, called-strike rate, edge command,
catcher framing — has a **measurement** discontinuity at 2026, not a behavioural
one. Framing value should collapse toward zero in 2026 by construction. This is
the most dangerous thing in the dataset for anyone pooling seasons.

---

## 2026-09-10 — Data completeness

2.84M pitches, 2023 through 2026-09-09, regular seasons verified per team at 162
games. 2024 shows 2,429 games, which is correct: HOU @ CLE on 2024-09-29, the
regular-season finale, was rained out and never made up.

A corrupted database under-reported its own row count by 23,523 pitches with no
error raised — counts and most queries still worked. `PRAGMA quick_check` now
runs after every scheduled refresh for exactly this reason.

---

## 2026-09-10 — Does a pitch play differently depending on what preceded it?

**Question.** Within the 2025 season, is a pitch's run value different after each
other pitch type, once the count is removed? And do the highest-workload
pitchers change pitches more than is good for them?

**Method.** Every (previous pitch, this pitch, count) cell is compared against
what that same pitch type is worth in that same count league-wide:
`expected = sum over counts of n(cell,count) * baseline(pitch,count) / n(cell)`.
The count is the dominant confound — pitchers go to the breaking ball ahead and
back to the fastball behind — so a delta of zero means the sequence told you
nothing the count did not.

**Result — league.** Repeating beats changing by **+0.58 runs per 100**, 95%
interval **[+0.44, +0.71]**, across 525,900 paired pitches. The gap is largest in
even counts (+0.97) and two-strike counts (+0.92), smallest when the hitter is
ahead (+0.37).

The extremes of the matrix are one-sided. Best: `ST→FC` +0.96, `CU→CH` +0.62,
`FS→FS` +0.61, `SL→SL` +0.55. Worst: `KC→FF` −1.37, `CH→ST` −0.98, `CH→SI` −0.97,
`FS→FF` −0.92. Seven of the eight best are repeats or offspeed-to-offspeed;
**every one of the eight worst is a return to a fastball after an offspeed pitch.**

**Result — individual pitchers.** The five 2025 innings leaders, each measured
against himself:

| pitcher | IP | repeat rate | gap | 95% interval | verdict |
|---|---|---|---|---|---|
| Logan Webb | 204.0 | 32.6% | +0.19 | [−1.72, +2.10] | not distinguishable |
| Garrett Crochet | 202.0 | 29.7% | −0.20 | [−2.21, +1.81] | not distinguishable |
| Cristopher Sánchez | 200.3 | 41.6% | +3.68 | [+1.83, +5.54] | repeats too little |
| Carlos Rodón | 194.0 | 32.7% | +0.79 | [−1.21, +2.80] | not distinguishable |
| Tarik Skubal | 192.7 | 26.5% | −0.42 | [−2.46, +1.61] | not distinguishable |

**What it shows.** The league effect is real and precisely estimated. The
direction contradicts the coaching orthodoxy, and it concentrates exactly where
that orthodoxy is loudest — the two-strike putaway pitch.

**What it does not show.** Two things, and the second is the important one.

It is not causal. Sequence is chosen, not assigned; a pitcher repeats a pitch he
likes that day. Within-pitcher comparison removes the between-pitcher confound
and nothing else.

**And it does not identify individual pitchers who mix too much.** One season is
roughly 2,900 pitches for a starter, which puts the standard error on his gap
near 1 run per 100 — nearly twice the league effect size. Four of five intervals
straddle zero. Sánchez separates, but with five pitchers tested one clearing at
95% is about what chance produces, so that is a hypothesis rather than a result.
**Anyone reporting a single-season per-pitcher sequencing number without an
interval is reporting noise.**

**Next.** Pool 2023–2025 for per-pitcher estimates, which roughly halves the
standard error and would make a real leaderboard possible. 2026 must stay out
until the ABS strike-zone change is accounted for. Then the interesting split:
Skubal and Crochet trend negative (changing works for them) while Sánchez trends
strongly positive — if that holds up over three seasons, the mechanism is
probably arsenal quality, and the question becomes whether the league effect is
just pitchers whose second-best pitch is not worth going to.

---

## 2026-09-10 — Which pitch is right in which count?

**Question.** Within each count, does pitch type matter, and does the answer
change as the count changes?

**A trap to name first.** Run value per 100 averages ~0.00 in EVERY count. That
is construction, not a finding: `delta_run_exp` measures the change from the
pre-pitch state, so within a fixed count the average across all pitches is
necessarily near zero. All the signal is in differences BETWEEN pitch types
within a count, never in the count's own average.

**Result.** Fastballs (FF/SI/FC) beat offspeed in every count with 0 or 1 strike,
and lose in every count with 2 strikes. No exceptions in 2025.

| count | fastball | offspeed | gap | FB share |
|---|---|---|---|---|
| 0-0 | +0.05 | −0.06 | +0.11 | 60.9% |
| 1-0 | +0.09 | −0.12 | +0.21 | 60.2% |
| 2-0 | +0.10 | −0.24 | +0.34 | 71.0% |
| 0-1 | +0.12 | −0.12 | +0.24 | 50.3% |
| 1-1 | +0.21 | −0.18 | +0.39 | 50.5% |
| 2-1 | +0.30 | −0.46 | +0.76 | 58.9% |
| 3-1 | +0.23 | −0.67 | +0.90 | 77.0% |
| 0-2 | −0.08 | +0.05 | −0.13 | 42.5% |
| 1-2 | −0.08 | +0.05 | −0.12 | 43.9% |
| **2-2** | **−0.42** | **+0.38** | **−0.80** | **48.7%** |
| 3-2 | −0.07 | +0.28 | −0.35 | 62.6% |

Best pitch by count follows the same shape: sinker early (1-0 +0.41, 2-1 +0.56),
changeup and splitter with two strikes (0-2 CH +0.38, 1-2 FS +0.53, 2-2 CH +0.53).

**What it shows.** The fastball/offspeed decision flips at the second strike, and
the flip is monotone in strikes. 2-2 is the largest gap in the table in either
direction while carrying a nearly even mix — compare 3-1, where a similar-sized
gap comes with a 77/23 mix. If any count is systematically mispriced, 2-2 is the
candidate.

**What it does not show.** These are AVERAGE values of pitches actually thrown,
not the MARGINAL value of throwing one more. A pitcher goes to the changeup in
2-2 when he can command it that day; the ones who cannot, do not. So the offspeed
number partly measures selection into the pitch, and the marginal changeup — the
one added by overriding the pitcher's own judgment — is worth less than the
average one. The gap's size and the even mix make it testable, not proven.

**Next.** The marginal-versus-average problem is the whole question. A
within-pitcher design helps: for pitchers who throw both in 2-2, compare their
own results, and see whether those who lean fastball there underperform their own
offspeed. If the effect survives that, it is a real recommendation rather than a
description of who throws what.

---

## 2026-09-10 — Pre-registered: does pitch choice by count survive a within-pitcher test?

**Pre-specified before looking**, because by this point the data had been cut a
dozen ways and every additional cut raises the chance of a lucky threshold
crossing:

* **H1** Within a pitcher, offspeed outperforms his own fastball in 2-2.
* **H2** The gap is a persistent property of the pitcher — his 2023-24 gap
  predicts his 2025 gap.

**Result — H1: the 2-2 finding does not survive.** Within pitcher, in the same
count, offspeed beats fastball in 2-2 by **+0.12 [−0.21, +0.45]** across 351
pitchers. Not distinguishable from zero. The league-level −0.80 gap reported
earlier the same day was **almost entirely between-pitcher selection**: pitchers
with a good changeup throw it in 2-2, and they are better pitchers. Compare a
pitcher to himself and it disappears. That earlier entry's "average is not
marginal" caveat did not merely qualify the finding — it consumed it.

One count does survive multiple-comparison correction across the ten tested
(Bonferroni α = 0.005):

| count | gap (OS − FB) | 95% CI | z | survives |
|---|---|---|---|---|
| **1-2** | **+0.44** | [+0.19, +0.70] | 3.38 | **yes** |
| 3-2 | +1.00 | [+0.18, +1.83] | 2.38 | no |
| 1-1 | −0.26 | [−0.50, −0.03] | −2.17 | no |
| 0-1 | −0.19 | [−0.37, −0.02] | −2.13 | no |
| 2-2 | +0.12 | [−0.21, +0.45] | 0.71 | no |

**Result — H2: no persistence, in any count.** Fitting 2023-24 and testing 2025,
the correlation of a pitcher's own gap between periods is never distinguishable
from zero: 2-2 r = +0.03 [−0.14, +0.20]; the largest anywhere is 2-1 at +0.20
with an interval spanning zero. **There is no per-pitcher pitch-selection
recommendation supportable from three seasons of public data.** Between-pitcher
differences in this gap are noise.

---

## 2026-09-10 — The sequencing effect DOES survive the same test

The obvious objection to the morning's headline — repeating beats changing by
0.58 runs/100 — is the confound that just destroyed the 2-2 result: maybe
pitchers who repeat more are simply better. Run within pitcher, each man against
himself in the same count, pooled 2023-2025:

**+0.563 runs per 100, 95% [+0.425, +0.702], 360 pitchers.**

Essentially identical to the pooled estimate. The effect is **not** composition.

**Why this pairing matters more than either number alone — it is a positive
control.** A null is uninformative unless the design can be shown to detect
something. Had every test returned null, "no effect" and "no power" would be
indistinguishable. This result is the known-positive: same design, same database,
comparable samples, clearly non-zero.

The precise claim it licenses is narrower than "the 2-2 effect is zero". It shows
the design detects an effect of about 0.56 runs/100 at this sample size. It says
nothing about 0.15. So the honest statement of the 2-2 result is that any true
within-pitcher effect there is **smaller than about +0.45** — the upper bound of
its own interval — not that it is absent. A formal power calculation would
replace this reasoning by analogy; it has not been done.

**But it still does not vary by pitcher.** Persistence of a pitcher's own gap,
2023-24 → 2025: **r = −0.069 [−0.249, +0.116]** across 115 pitchers. No evidence.

**So the actionable claim is a blanket rule, not a list.** "Repeat more often"
is supported league-wide and within pitcher; "these specific pitchers mix too
much" is not, and cannot be from this data. The original open question — *are
there pitchers who mix too much* — is answered: **not identifiably.**

**What would change this.** The effect is ~0.5 runs/100 and one starter-season
carries a standard error near 1.0. Detecting individual variation needs either
many more seasons per pitcher, or a lower-variance outcome than run value —
whiff rate on the pitch would be a candidate, since it is binary and per-pitch
rather than heavily tailed.

---

## 2026-09-10 — The nastiest individual pitches, 2023-2025

1,162 pitcher-pitch combinations with 600+ thrown.

**By run value per 100:** Tyler Holton sinker +3.35, Gabe Speier 4-seam +2.77,
Ryan Helsley slider +2.73, Mason Miller slider +2.66, Cade Smith 4-seam +2.47.

**By whiff per swing:** Fernando Cruz splitter **57.7%**, Josh Hader slider
56.2%, Spencer Strider slider 52.7%, Blake Snell curve 52.1%.

**What it shows.** Very little, until it is checked against something external.
The names at the top were originally described here as "independently famous",
which was asserted from prior knowledge rather than read from a source — and
validating a pipeline against your own priors is not validation. Cruz's splitter
does hold up on inspection (Reds Content Plus, April 2024, "the best pitch in the
league"; Pinstripe Alley, Feb 2025). The others are unchecked.

The real check is mechanical and not yet done: pull Savant's own whiff-rate
leaderboard and reconcile it pitch by pitch against these numbers. Until that
runs, treat this as output, not as a verified end-to-end test.

**What it does not show.** Reliever bias is severe and unadjusted: relievers
appear in one-inning bursts against favourable matchups, and eight of the top
ten by run value are relievers. Run value per 100 also rewards pitches thrown in
low-leverage spots. A usable "best pitch" list needs a starter/reliever split and
a leverage adjustment; this one is a raw leaderboard.
