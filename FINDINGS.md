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

---

## 2026-09-11 — How many events before a metric means anything?

**Question.** Split-half reliability by sample size for every metric the
dashboard could use. Nothing to pre-register: this measures reliability, not an
effect, so there is nothing to fish for.

**Method.** For each player-season and sample size n, take the first 2n events,
split by odd/even index (balances within-season trend and opponent quality far
better than first-half/second-half), correlate half-means across players, and
correct with Spearman-Brown. Reported at r = 0.5, the conventional stabilisation
bar, and r = 0.7, because 0.5 gets quoted as though it were high when it means
half the observed spread is still noise. 2026 excluded — chase rate depends on
`zone`, which the ABS change redefines.

| metric | r = 0.5 | r = 0.7 | unit |
|---|---|---|---|
| swing length | ≤5 | ≤5 | swings |
| pitcher velocity | ≤5 | ≤5 | fastballs |
| arm angle | ≤5 | ≤5 | pitches |
| **bat speed** | **≤5** | **10** | **swings** |
| exit velocity | 15 | 50 | batted balls |
| launch angle | 20 | 50 | batted balls |
| barrel rate | 20 | 75 | batted balls |
| whiff rate | 20 | 60 | swings |
| hard-hit rate | 25 | 60 | batted balls |
| chase rate | 30 | 75 | out-of-zone pitches |
| pitcher whiff rate | 50 | 125 | swings against |
| **xwOBA** | **100** | **250** | **PA** |

**What it shows.** A 25-to-50-fold spread in how much evidence each metric needs.
Bat speed is trustworthy after roughly ten swings — two or three games. xwOBA
needs 250 plate appearances for the same confidence, which is most of a season.
The physical measurements (bat speed, swing length, velocity, arm angle) are
essentially player traits read off a sensor; the outcome measures are contested
events with a hitter, a pitcher and a defence in them.

**The design implication, which inverts the current dashboard.** `analyze.py`
gates everything at MIN_PA = 150 and treats contact quality as *corroborating
evidence* for an xwOBA-driven signal. The reliability ordering says that is
backwards: at 150 PA xwOBA has barely cleared r = 0.55, while the swing metrics
were trustworthy two months earlier. **Swing metrics should be the trigger and
xwOBA the confirmation.**

**What it does not show.** Reliability is necessary, not sufficient. A metric can
be perfectly reliable and still useless for forecasting if it does not move with
outcomes — swing length is reliable at five swings precisely because it barely
varies. The untested step is whether a CHANGE in bat speed predicts a change in
production. That is the next study, and it is the one that would actually justify
rewiring the signal.

Sample sizes thin at the top of the grid: only 34 hitters reach 500 batted balls
in a season, so the r values at n ≥ 250 rest on few players.

---

## 2026-09-11 — Did catcher framing collapse under ABS? (pre-registered, and wrong)

**Pre-specified.** If the strike zone became automated in 2026, the spread
between catchers in extra strikes gained should collapse toward zero.

**Method.** Extra called strikes versus expectation, where expectation is the
same season's own strike rate for an identical bucket of location (0.1 ft grid),
count and batter side. The zone is a FIXED geometric box in every season, never
`sz_top`/`sz_bot` — those columns are themselves what changed, so using them
would confound the rule change with the ruler change. Between-catcher standard
deviation, in extra strikes per 1000 taken pitches.

| season | catchers | SD | best | worst | range |
|---|---|---|---|---|---|
| 2023 | 39 | 16.58 | +28.5 | −30.6 | 59.1 |
| 2024 | 40 | 15.54 | +38.8 | −23.8 | 62.6 |
| 2025 | 39 | 13.80 | +28.7 | −28.5 | 57.2 |
| 2026 | 28 | 10.57 | +21.7 | −19.6 | 41.2 |

**The hypothesis was wrong, and knowably so.** 2026 is an ABS **challenge**
system, not full automation — each team gets a limited number of challenges and
the umpire still calls nearly every pitch. Framing was never going to collapse.
The rule should have been checked before the prediction was written; it took one
search afterwards.

**What actually happened is more interesting.** Framing spread fell 31% against
the 2023-2025 average — but it was already falling: 16.58, 15.54, 13.80 is a
steady decline of about 1.4 units a season. Extrapolating that pre-trend predicts
12.41 for 2026 against 10.57 observed, so the portion plausibly attributable to
ABS is roughly **15%, not 31%**. Reporting the raw drop would have doubled the
effect.

**A mechanism worth testing:** a challenge system can suppress framing without
automating anything, by deterrence — the most egregious framed calls are exactly
the ones a hitter will challenge, so the return on stealing a strike falls even
though the umpire still makes the call.

**What it does not show.** Causation. This is a four-point interrupted time
series with one post-period, which is the weakest version of that design. And the
residual spread is not necessarily catcher skill: the model controls location,
count and batter side but **not the pitcher**, so a catcher who receives
command-heavy pitchers still looks good.

One thing cuts in the finding's favour: 2026 is a partial season, so each catcher
is measured on fewer pitches, which should INFLATE the observed spread through
noise. The decline survives a bias pushing the other way.

**Next.** Add pitcher fixed effects. Get umpire IDs from StatsAPI and test
whether umpire-to-umpire variation fell in parallel — under the deterrence story
it should.

---

## 2026-09-11 — Applying the stabilisation result: Mets hitters, 2025 vs 2026

**Question.** Not "what is the Mets' reliability curve" — reliability is a
correlation ACROSS players, so a 15-man roster would give a correlation on n=15
and mean nothing. The usable question is which year-over-year changes are large
enough to believe, given what each metric's reliability implies.

**Method.** Per player, per season, mean and standard error; change reported with
SE(delta) = sqrt(sd_a²/n_a + sd_b²/n_b). Team assigned from the half-inning (the
batting team is the away team in the top half).

**Result.**

| metric | changes distinguishable from zero |
|---|---|
| bat speed | **3 of 7** |
| exit velocity | 1 of 7 |
| xwOBA | **0 of 7** |

| hitter | bat speed 2025 → 2026 | 95% CI |
|---|---|---|
| Mark Vientos | 69.16 → 71.87 (**+2.71**) | [+1.91, +3.52] |
| Francisco Lindor | 69.02 → 70.75 (**+1.72**) | [+1.00, +2.45] |
| Juan Soto | 70.93 → 69.81 (**−1.12**) | [−2.06, −0.19] |

**What it shows.** The stabilisation result made concrete: identical players,
identical seasons, and the metric alone decides whether a change is visible.
Every xwOBA change on this roster is inside its own error bars.

One pattern worth following: Francisco Alvarez lost 2.82 mph of exit velocity
(the only significant EV change) while his bat speed held flat at +0.30. Swing
speed unchanged, contact quality down — that points at timing or approach rather
than strength, which is a different diagnosis and a different fix.

**What it does not show.** That any of these changes matter. Bat speed is
measured precisely; whether +2.71 mph of it produces runs is the untested link,
and it is the same gap flagged in the stabilisation entry. Detecting a change is
not the same as knowing it is worth something.

**A trap this hit.** The first run printed bare player IDs because `name_of()`
looked up `pitches.player_name` — which is the PITCHER's name on every row
regardless of grouping, exactly as `DATA_DICTIONARY.md` warns in bold. Batter
names come from `expected_stats`. The documentation was right and was not read.

---

## 2026-09-11 — Does a faster swing produce better outcomes?

**Result — league, batted balls (2023-2025).** Monotone in everything, then a
ceiling.

| bat speed | n | exit velo | distance | xwOBA | barrel |
|---|---|---|---|---|---|
| 57-59 | 4,574 | 75.9 | 106 ft | .240 | 0.2% |
| 66-68 | 41,393 | 85.7 | 153 ft | .304 | 2.7% |
| 72-74 | 67,030 | 91.4 | 180 ft | .392 | 10.1% |
| 78-80 | 18,216 | 94.6 | 193 ft | .486 | 18.1% |
| 81-83 | 5,573 | 94.3 | 190 ft | .488 | 18.5% |

**Result — the contact tax does not appear.** Whiff rate against bat speed is
essentially FLAT across the entire normal range: 23.1% at 63-65 mph, 23.4% at
66-68, 24.8% at 72-74, 24.2% at 78-80. The folk belief that selling out for
power costs contact is not visible here. (Whiff rates above 70% at 30-45 mph are
emergency and checked swings, which are slow *because* they are defensive —
reverse causation, not a finding.)

**Result — within hitter.** A hitter's own faster-than-usual swings, z-scored
against his own season: xwOBA .294 at z = −1, .367 at z = 0, .444 at z = +1, and
.442 at z = +2. Monotone to +1, flat after.

**What it does not show — and this is severe.** `bat_speed` is measured AT
CONTACT. A mistimed swing is recorded as slower AND produces worse contact, so
much of this is "swings that connect well are recorded as fast" rather than
"swinging fast causes good contact". The within-hitter version does not fix it;
it is the same mechanism inside one player. The whiff result is the cleanest of
the three, because bat speed there is measured on misses too.

A causal version needs intended swing speed, which is not in public data.

---

## 2026-09-11 — What explains wOBA minus xwOBA besides luck? (and a self-inflicted artifact)

**The first answer was wrong, from a trap this repo documents in bold.** The
first run compared full wOBA — which scores a strikeout as zero — against xwOBA
measured ON CONTACT ONLY. That manufactures a large negative gap for every
high-strikeout hitter, and the regression then dutifully "explained" the gap with
the strikeout rate that created it: correlation −0.748, R² = 0.719. It looked
like a major finding. It was an accounting error.

**Corrected**, with xwOBA computed per plate appearance (non-contact events
folded in at their linear weight, as `analyze.pa_level` does), across 849
player-seasons with 300+ PA:

| predictor | correlation with gap |
|---|---|
| avg exit velocity | **−0.335** |
| line-drive rate | −0.090 |
| ground-ball rate | +0.063 |
| pull rate | +0.060 |
| strikeout rate | −0.048 |
| avg launch angle | +0.003 |

**Multiple R² = 0.133.** Standard deviation of the gap = .0191 wOBA.

**What it shows.** About **87% of the gap is not explained by batted-ball
profile**, which is a real if partial vindication of the dashboard's decision to
treat it as luck. But it is not pure noise: **hard-hit hitters systematically
underperform their xwOBA** (−0.335). Candidate explanations, none tested here —
xwOBA may over-credit the top of the exit-velocity range, or hard contact may be
caught more often because defenders position for it.

**What it does not show.** That the residual is luck. Park, defence quality
faced, and sprint speed are all absent from this regression and all plausibly
systematic. 87% unexplained is an upper bound on luck, not an estimate of it.

**Next.** Add park (the game's home team), and sprint speed once 2023-2025 is
backfilled. If exit velocity survives those controls, the dashboard should
residualise the gap on EV — the same correction attempted for speed in D7, on a
predictor that is actually large.

---

## 2026-09-11 — Mets: within-player change and how they are pitched

**Soto's bat-speed decline is concentrated, not uniform.** By strike count,
2025 → 2026: 0 strikes **−2.50 mph** (distinguishable), 1 strike −0.31, 2 strikes
−1.38. He is swinging materially less hard in the count where he would normally
be most aggressive. Cells are 175-415 swings, so only the 0-strike change clears
its error bars.

**Vientos's gain looks like a mid-season retooling.** Strongest split of his 2026
season falls at **2026-06-16**: 71.82 → 73.42 mph, with swing length moving
7.42 → 7.59 ft in the same direction. His 2025 baseline was 69.16, so the gain
came in two steps.

⚠️ **The t = 2.1 on that split is not a valid test.** It is the MAXIMUM t over
about 57 candidate split dates, and the maximum of many statistics has a far
higher critical value than a single one. The date is a reasonable estimate of
where the change happened; it is not evidence that a change happened. A proper
version needs a bootstrap over the max statistic.

**Nobody adjusted how they pitch to any of it.** Fastball share against Soto:
53.7 / 50.8 / 52.6 / 51.9 across 2023-2026. Against Vientos: 50.8 / 47.2 / 48.9 /
48.5 — no visible response to a 2.7 mph bat-speed gain. Team-wide: 57.2 → 54.6.
Lindor's edge rate moved 27.7% → 29.5%.

One oddity worth a second look: NYM hitters saw MORE fastballs with runners on in
2026 (54.1%) than in 2025 (52.4%), while their bases-empty share was identical at
55.0% in both years.

**Mets pitchers — three real mechanical changes.**

| pitcher | arm slot 25→26 | velo 25→26 | arsenal |
|---|---|---|---|
| Nolan McLean | 28.6 → 32.3 | 95.1 → 95.4 | ST −14pp, FF +7pp |
| Clay Holmes | 43.3 → **38.5** | 93.7 → 93.1 | SL −11pp, SI +9pp |
| Sean Manaea | 14.7 → 15.6 | 91.7 → 91.0 | **FF −23pp, SI +19pp** |
| Kodai Senga | 44.6 → 46.4 | 93.7 → **95.9** | FF +11pp, FC −7pp |

Holmes dropped his slot nearly five degrees and swapped slider for sinker;
Manaea replaced almost a quarter of his four-seamers with sinkers; Senga added
2.2 mph. These are descriptive — no test that the changes caused anything.

---

## 2026-09-11 — Full change profiles, and the hypothesis scorecard

**Scope.** Mets only, and that is an interpretation: "go down the line" implies a
roster, and a comprehensive per-player profile for the ~250 league hitters above
600 combined PA would not be readable. `profiles.py --team` makes the league
version one flag away, but it wants to be a filterable tool rather than a report.

Five hitters at 600+ PA combined, six pitchers at 100+ IP, each across decisions,
mechanics, results and how they are pitched, every change with an interval.

**TWO WARNINGS THAT COME BEFORE ANY NARRATIVE.**

*Multiple comparisons.* Twenty metrics across five hitters is 100 tests at 95%,
so about five "significant" results are expected from chance alone. Eighteen
appeared, and 24 of 78 for pitchers — so there is real signal in aggregate, but
no single marginal result here is trustworthy on its own, and none of it was
pre-registered.

*Significance is not magnitude.* With thousands of pitches, trivial differences
clear their error bars: Peterson's release extension moved 0.05 ft and Holmes's
0.01 ft, both "real". The report marks changes below a practical floor as tiny.

**Hitters — the substantive changes.**

| player | change |
|---|---|
| Juan Soto | swing% +3.8, z-swing% +6.6, chase% +4.3, **K% −6.0**, bat speed −1.1, hard-hit% −7.5 |
| Francisco Lindor | bat speed +1.8, swing length +0.14, **pull% +7.6** |
| Brett Baty | **GB% −10.4**, swing length +0.11, 1st-pitch swing% +7.4, chase% +4.3 |
| Mark Vientos | **bat speed +2.7**, 1st-pitch swing% +7.4 |
| Francisco Alvarez | **pull% +12.7**, FB seen% +4.4, exit velo −2.8 |

Soto's is the most coherent story on the roster: far more aggressive at
everything, six fewer points of strikeout rate, and he paid in contact quality —
slower swing, seven fewer points of hard contact. A deliberate trade of power for
contact, and it matches the earlier finding that his bat-speed loss concentrates
in 0-strike counts.

**Pitchers.**

| player | change |
|---|---|
| Sean Manaea | velo −0.8, zone% −4.6, whiff% −4.9, **K% −7.1**, FF −23pp / SI +19pp |
| Clay Holmes | **arm angle −3.0°**, SL −11pp / SI +9pp / CU +7pp, wOBA against −.05 |
| Nolan McLean | **arm angle +3.5°**, zone% −5.0, ST −14pp / FF +7pp |
| Kodai Senga | **velo +2.15**, arm angle +1.7, FF +11pp |
| Huascar Brazobán | SI +14pp, xwOBA against −.05 |
| David Peterson | velo +0.5, spin +45, wOBA against +.05 |

**THE SCORECARD, and it is one-sided.**

| hypothesis | verdict |
|---|---|
| H1 Vientos step change | partial — date found, t-statistic invalid |
| H2 swing length moved with bat speed | **yes** (Lindor, Baty) |
| H3 Soto's decline is situational | **yes** |
| H6 Soto sees fewer fastballs | **no** |
| H7 team fastball share shifted | **no** |
| H8 league adjusted to Vientos | **no** |
| H9 Lindor sees more edge pitches | **no** |
| H10 different mix with runners on | partial |
| H14 chase rate is a fast signal | **yes** |
| H17 a pitcher changed arm slot | **yes** — the best supported |
| H18 velocity moved meaningfully | **yes** |
| H19 a pitcher rebuilt his arsenal | **yes** |

**Every mechanical hypothesis confirmed. Every "the league responded"
hypothesis failed.** Players changed considerably between 2025 and 2026 — arm
slots, arsenals, bat speeds, approach — and how they were pitched barely moved.

That asymmetry is the finding, and it has an obvious follow-up: either opponents
adjust on a longer lag than one season, or the adjustments are happening in
dimensions this measures poorly — location within the zone rather than pitch
mix. The second is testable with the location data already on disk.

---

## 2026-09-11 — How much do players actually change? Calibrating "a lot"

**Question.** A change can clear its error bar and still be ordinary. Is +.040
wOBA a big move? A standard error cannot answer that; the league-wide
distribution of year-over-year changes can.

**Method.** 222 hitters with 250+ PA in both 2025 and 2026. The observed spread
of changes overstates the real one, because every measured change carries
sampling noise:

    var(observed change) = var(true change) + var(noise)

so the real spread is `sqrt(var_obs − mean(se²))`, and the ratio
`var_true / var_obs` is the share of observed movement that is real.

| metric | sd observed | sd noise | **sd TRUE** | signal share | 90th pct |
|---|---|---|---|---|---|
| wOBA | .0356 | .0200 | **.0294** | 68% | .0377 |
| xwOBA | .0276 | .0146 | **.0234** | 72% | .0300 |
| bat speed | 1.10 | 0.43 | **1.01** | **85%** | 1.30 |
| swing% | 3.05 | 1.67 | 2.55 | 70% | 3.27 |
| chase% | 3.36 | 2.14 | 2.59 | 59% | 3.32 |
| whiff/sw% | 3.04 | 2.06 | 2.23 | 54% | 2.86 |
| BB% | 2.47 | 1.84 | 1.65 | 44% | 2.11 |
| K% | 3.45 | 2.71 | 2.13 | 38% | 2.74 |
| barrel% | 2.89 | 2.28 | 1.78 | 38% | 2.28 |
| exit velo | 1.49 | 1.19 | 0.90 | 37% | 1.15 |
| hard-hit% | 4.61 | 3.93 | 2.42 | 27% | 3.10 |
| GB% | 4.35 | 3.93 | **1.86** | **18%** | 2.39 |

**Answer: +.040 wOBA is a big move.** The true spread of year-over-year wOBA
change is .0294, so +.040 is 1.4 SD — above the 90th percentile of real movers.
The intuition was right and my arbitrary "practical floor" of .015 was too
generous.

**THE MORE IMPORTANT RESULT: the signal share IS a shrinkage factor, and it
corrects the profiles reported earlier the same day.** Given an observed change
`d` with standard error `se`, the best estimate of the true change is

    d × var_true / (var_true + se²)

For bat speed, 85% of observed movement is real, so an observed change is close
to the truth. For ground-ball rate only 18% is, so most of what looks like a
mechanical change is sampling.

Applied to the Mets profiles:

* Vientos's bat speed **+2.71 → ≈ +2.3 expected true**, roughly 2.3 true SD, a
  genuinely rare move.
* Baty's ground-ball rate **−10.38 → ≈ −1.9 expected true**. It reads as the
  most dramatic change on the roster and is mostly noise. Reported without
  shrinkage, that number would have become a story about a launch-angle
  overhaul.

**What it does not show.** The decomposition assumes the noise estimate is right
and that true change is normally distributed around zero with constant variance.
Neither is exactly true, and a genuine outlier will be over-shrunk.

**Implication for the dashboard.** Every year-over-year change it displays should
be shrunk by that metric's signal share, and the numbers above are the
coefficients. This is the same partial-pooling logic already in `proj_woba_ros`,
applied to change rather than level.

---

## 2026-09-11 — Monthly resolution: reliability of a LEVEL is not reliability of a CHANGE

**The claim being tested was mine, and it was wrong.** Having found bat speed
reliable at about ten swings, I said monthly resolution would work for it. It
does not.

League-wide month-over-month change, decomposed:

| metric | sd observed | noise | sd TRUE | signal share |
|---|---|---|---|---|
| fastball velocity | 0.62 | 0.13 | 0.61 | **96%** |
| arm angle | 1.82 | 0.31 | 1.80 | **97%** |
| swing length | 0.16 | 0.12 | 0.10 | 43% |
| bat speed | 1.39 | 1.13 | 0.81 | **34%** |
| swing% | 4.90 | 4.22 | 2.49 | 26% |
| chase% | 6.26 | 5.43 | 3.12 | 25% |
| whiff/sw% | 5.78 | 5.23 | 2.46 | **18%** |

**Why the level result did not transfer.** Two effects compound. A change is a
difference of two noisy measurements, so it carries roughly twice the noise of
either. And players barely move their bat speed from month to month, so there is
little true variation to find. A metric can be measured precisely and still have
almost nothing real to detect at that cadence.

Bat speed at season scale is 85% signal; the same metric month over month is 34%.
**Reliability of a level and reliability of a change are different quantities,
and the second is what change detection needs.**

**Result.** Monthly resolution is usable for pitcher velocity and arm angle, and
close to useless for hitter discipline and swing metrics. The earlier
recommendation that "bat speed works monthly, even weekly" is superseded.

**Mets moves that beat the league distribution** (shrunk by signal share, z
against the true-change spread): Manaea velocity −2.33 (z −3.85), Peralta arm
angle +5.53 (z +3.08), McLean arm angle +5.39 (z +3.00), Díaz velocity +1.01
(z +1.66). **No Mets hitter cleared at all.** Bichette's whiff rate appeared to
jump 15.2 points and shrinks to +4.8 — the clearest single illustration of why
raw month-over-month numbers for hitters should not be read.

**A flaw found and fixed.** The first version took consecutive months in sorted
order, so pairs like 2025-09 → 2026-04 were counted as monthly changes when they
straddle the entire offseason. Now skipped; only within-season transitions count.
Manaea's largest "monthly" move was one of these.

---

## 2026-09-11 — Calibration applied everywhere, nine exploratory studies, two retractions

### Retraction 1: the Mets profile report overstated most of its changes
The published report judged a change by (a) clearing its own error bar and (b) passing a
practical-size floor I picked by hand. (a) only tests against zero, which sample size
controls; (b) was an opinion. Replaced by `calibrate.py` -> `profiles.py` -> `report_profiles.py`:
every change is shrunk by `var_true/(var_true+se^2)` for that metric and reported in units of
`sd_true`. Biggest casualty: **Baty GB% -10.38 raw -> -1.72 believable** (GB% is 18% signal).
Vientos bat speed +2.71 -> +2.33 (z +2.30, league-extreme) survives almost intact.

### Retraction 2: H14 was scored on the wrong evidence
"Chase rate is a fast-moving discipline signal" was marked yes because chase changes were
*detectable*. The hypothesis claims chase *leads* production. Within-hitter, 1,119 month-triples:
  d(chase)_t -> d(wOBA)_{t+1}:  +0.0459 ± 0.0364   (null)
  d(chase)_t -> d(wOBA)_t:      -0.3696 ± 0.0411   (real)
Chase is **coincident, not leading**. Now scored no.
Incidental and more valuable: **monthly d(wOBA) mean-reverts at -0.51 ± 0.026.** Half of any
month's movement is given back the next month, mechanically. Any in-season alerting built on
monthly splits must account for this.

### H16, previously skipped, now run
Bat-speed change 2025->2026 vs 2026 wOBA-xwOBA gap, 222 hitters: **r = -0.036 [-0.167, +0.096]**.
The luck gap is not a disguised mechanical change. Consistent with the gap regression's R^2=0.133.

### CRITICAL DATA TRAP: sz_top was redefined in 2026
| season | mean sz_top | distinct values league-wide | distinct for one batter |
|---|---|---|---|
| 2024 | 3.408 | 321,120 | 459 |
| 2025 | 3.435 | 353,643 | 907 |
| 2026 | 3.215 | **390** | **1** |

MLB replaced a per-pitch operator estimate with a per-batter formula. **Any season-over-season
analysis measured relative to sz_top/sz_bot is comparing against a different ruler.** My first
zone analysis did exactly this and reported the top of the zone EXPANDING by +32.8pp. Redone in
absolute feet it CONTRACTED. See DECISIONS D15.

### The 2026 zone, in absolute geometry (immune to the above)
- top 3.4-3.6 ft: 41.1% -> **17.6%** called strikes (-23.5pp); 3.2-3.4 ft: -17.2pp
- bottom 1.4-1.6 ft: 42.0% -> **52.5%** (+10.5pp); 1.6-1.8 ft: +10.4pp
- outside 0.90-1.05 ft: 20.5% -> 13.0% (-7.6pp)
- **sharpness**: 20%-to-80% transition band narrowed 2.61 -> 1.90 inches (outside), 3.36 -> 2.95 (top)
Shorter, deeper, narrower, crisper. Explains the framing-spread collapse (15.5 -> 10.6 runs)
found on 2026-09-10. No challenge/overturn flag exists in the data, so this is the zone's *net*
shape under the system, not a measurement of challenge outcomes.

### TTO penalty is real; arsenal breadth does NOT blunt it
Within pitcher: pass 1 -0.0094, pass 2 +0.0025, pass 3 +0.0146 vs own average (+24 pts 1->3).
Penalty ~ effective arsenal size, 337 starter-seasons: **slope -0.0027 ± 0.0040** (null).
This is the second, stronger confirmation of the pitch-mixing null — run in the exact situation
most favourable to the hypothesis.

### Two-strike adjustment: real, universal, and associated with better outcomes
521 hitter-seasons. Mean bat speed with 2 strikes is **-1.37 mph**; **89% of hitters slow down**.
Between-hitter, those who shorten most have lower K% (r=+0.133 [+0.048,+0.217]), higher 2K wOBA
(r=-0.147 [-0.230,-0.062]), lower whiff (r=+0.102). NOT causal — within-hitter test still needed.

### Platoon split is a real trait, 72% signal
158 hitters. Mean advantage vs opposite hand +0.0311 wOBA. Observed spread .0414, noise .0217,
**true .0353**. 28% of any published platoon leaderboard's spread is noise.

### Clean nulls
- **Tunnelling**: 340k swings, consecutive different pitch types, baselined on (prev type, type,
  count). Excess whiff by release-point gap: -0.14 / +0.14 / +0.08 / -0.24 pp. Nothing, no ordering.
  Caveat: release distance != trajectory separation at commit point. Not yet computed.
- **Velocity decay**: between-pitcher says steeper decay -> SMALLER late penalty (r=+0.905 across
  quintiles) — pure selection, the "gains velo" quintile has .2497 early wOBA. **Within pitcher,
  8,250 starts: +0.0031 ± 0.0024, null.** Keep as the canonical selection-effect teaching case:
  monotone across five bins and still an artifact.

### Measurement warning: bat speed is park-dependent
Same team's hitters home vs road. Bat speed home-road sd **0.23 mph** (HOU -0.45 to TB +0.65);
exit velo sd **0.46 mph**. **Correlated +0.456 across parks** — a shared installation effect, not
hitting. Relative to a true YoY bat-speed spread of 1.01, this is not negligible for small changes.

### Full league change calibration (see output/calibration.json)
Hitters, most to least believable: swing length 87%, bat speed 85%, FB seen 72%, xwOBA 72%,
swing% 70%, wOBA 68%, z-swing 65%, 1st-pitch sw 64%, chase 59%, whiff/sw 54%, 2K swing 45%,
BB% 44%, K% 38%, barrel 38%, exit velo 37%, pull 29%, hard-hit 27%, **GB% 18%, edge seen 6%,
sweet-spot 0%**.
Pitchers: arm angle 100%, extension 100%, velo 99%, spin 97%, xwOBA-against 72%, wOBA-against 69%,
whiff/sw 49%, chase induced 39%, K% 39%, zone% 28%, 1st-pitch strike 24%, **BB% 1%, edge% 1%**.
Rule of thumb: what a player *does* is measurable in one season; what *happens to the ball* is not.

---

## 2026-09-12 — Forecasting: does xwOBA beat wOBA, and can we beat xwOBA

Panel: 10,287 hitter-months 2023-2026 (`extract_monthly.py` -> `output/hitter_months.csv`).
**Fit on 2023-2025, evaluated once on 2026. No 2026 data touched any coefficient.**
Weighted by target-window PA throughout.

### The headline, in the only units that matter
Sort 2026 hitter-months into fifths by a signal; look at what those hitters ACTUALLY hit next month.
Spread between top and bottom fifth of realised next-month wOBA:
| sorted by | spread |
|---|---|
| what he just hit (wOBA) | **.0098** |
| xwOBA | .0228 |
| the fitted model | **.0406** |
wOBA is also badly miscalibrated: bottom fifth claimed .247, then hit .329.

### Q1 — is xwOBA more predictive than wOBA? Yes, everywhere.
| window | n | wOBA R2 | xwOBA R2 | both | edge |
|---|---|---|---|---|---|
| 1 month | 1085 | **-0.0038** | 0.0153 | 0.0178 | +0.019 |
| 1 month 70+PA | 674 | 0.0032 | 0.0216 | 0.0234 | +0.018 |
| 2 months | 856 | 0.0366 | 0.0732 | 0.0717 | +0.037 |
| 3 months | 318 | -0.0074 | 0.0297 | 0.0359 | +0.037 |
| season -> season | 213 | 0.1194 | 0.1274 | 0.1305 | +0.008 |
**At one month, wOBA has NEGATIVE out-of-sample R2** — worse than assuming everyone is league average.
**I predicted xwOBA's edge would decline monotonically with window length. Wrong — it is humped**,
peaking at 2-3 months and nearly vanishing over a full season. No mechanism yet; see backlog S20.

**Once you know xwOBA, wOBA is negative information.** Fitting next ~ b1*wOBA + b2*xwOBA within
input-PA buckets, b1 is NEGATIVE in every bucket above 55 PA (-0.022, -0.104, -0.075, -0.041).
A hitter who beat his xwOBA should be marked DOWN.

### The ceiling — why R2 ~ 0.06 is most of what exists
From 16,228 within-season month pairs, E[(w1-w2)^2] = sigma^2*(1/pa1+1/pa2) + var(drift):
- per-PA outcome variance **sigma^2 = 0.2258** (sd .475 per PA)
- real month-to-month skill drift sd = **.0381**
- spread of true talent across 670 hitters sd = **.0345**
| PA/month | 40 | 60 | 100 | 250 | 600 |
|---|---|---|---|---|---|
| best possible R2 | .144 | **.186** | .243 | .336 | .395 |
At a typical 60-PA month an oracle scores .186. xwOBA's .015 is 8% of knowable; the full model's
.057 is **31%**. Always divide by the ceiling, never by 1.0.

### Q2 — can we beat xwOBA? Yes, ~4x. (1-month horizon, 2026 holdout)
| feature set | k | ridge | GBM | forest |
|---|---|---|---|---|
| wOBA only | 1 | -0.003 | -0.012 | -0.069 |
| xwOBA only | 1 | 0.015 | 0.007 | -0.037 |
| + contact quality | 10 | 0.024 | 0.014 | 0.021 |
| + discipline | 18 | 0.030 | 0.027 | 0.035 |
| + context & playing time | 39 | 0.044 | 0.049 | 0.055 |
| + swing geometry | 48 | 0.043 | **0.057** | 0.054 |

**UNCOMFORTABLE CONTROL: playing time alone scores 0.0316 — double xwOBA's 0.0153.** How often a
manager writes a hitter into the lineup predicts next month better than how hard he hits the ball.
Removing it costs the full model ~a fifth (0.057 -> 0.044). Kept in headline numbers because a real
forecaster would know it, but it is the manager's private information, not a hitting skill.

Swing geometry earns its place: bat speed carries the **2nd-largest coefficient of 22** in the
portable ridge, behind exit velocity and ahead of xwOBA.

### Descriptive vs reliable vs predictive — they trade off almost perfectly
| metric | describes now | repeats next month | predicts next month |
|---|---|---|---|
| wOBA | 1.000 | 0.135 | 0.065 |
| xwOBA | 0.747 | 0.321 | 0.136 |
| fitted | 0.485 | **0.665** | **0.205** |
The better a metric describes the month that happened, the worse it forecasts the next.

### Q3 — what explains wOBA minus xwOBA
**Within season it is luck.** Split-half (odd vs even months, 1,264 hitter-seasons 100+PA each half,
Spearman-Brown): bat speed .978, attack angle .971, whiff .924, EV .879, spray .791, xwOBA .703,
wOBA .448, **gap .164**, gb_single .193.

**Across seasons it is a small real trait.** Gap season-to-season r: **+0.293 / +0.303 / +0.274**
across three independent year pairs. Over-performers (3+ seasons): Altuve +.048, Friedl +.048,
Paredes +.040, Clement +.037, Bellinger +.033, Perdomo +.033, Rafaela +.032, Turner +.030.
Under: S.Perez -.024, Soto -.021, Conforto -.021, Bailey -.018, Tatis -.016, Vlad Jr -.016.
Fast contact hitters vs slow sluggers. **EV carries a NEGATIVE coefficient at every window**
(-.006 1mo, -.008 3mo); pull-side spray positive. xwOBA maps EV/LA to a league-average outcome, so
it over-credits the slow slugger whose hard-hit balls are caught and under-credits speed — and is
blind to direction, which is why Paredes (cheap pulled flies) is the 3rd-largest over-performer.

**CIRCULARITY I NEARLY PUBLISHED.** First run had gb_single as the top explainer, R2=.246. A ground
ball that finds a hole *is* both a gb_single and a positive gap — the same event counted twice.
gb_single's own split-half reliability is .193. Splitting predictors into ante-hoc (knowable before
the ball lands) vs outcome-derived:
| window | sd(gap) | ante-hoc R2 | outcome-derived R2 |
|---|---|---|---|
| 1 month | .042 | 0.034 | 0.189 |
| 2 months | .031 | 0.065 | 0.182 |
| 3 months | .026 | **0.137** | 0.168 |
**Answers the short-vs-long question: the gap shrinks as the window grows AND the genuinely
explainable share quadruples.** Luck averaging out, physical residue surviving.

Gap predicting future wOBA, controlling for xwOBA level: 1 month null (-0.038 +/- 0.024);
3 months **-0.107 +/- 0.054, real**. Over a real stretch, beating your expected output forecasts
giving it back.

---

## 2026-09-12 (later) — S22 answered: Marcel fights the whole project to a draw

**Marcel** (Tango 2004): weight last 3 seasons 5/4/3, regress toward league mean, age bump.
No batted-ball data, no swing tracking, ~5 lines. The line any forecaster must clear.

Two fairness corrections made AGAINST my own models before judging:
1. Marcel's regression constant **tuned on training years** (comparing a tuned model to an untuned
   baseline is a strawman).
2. Every model in predict.py saw only ONE window while Marcel sees a career — a handicap I imposed,
   not a property of Statcast. Models re-run **with the same weighted history**.

### One-month horizon, 2026 holdout, 3,000-sample bootstraps
| forecaster | R2 | 95% | sort spread |
|---|---|---|---|
| this month's xwOBA | 0.015 | [-.016,+.044] | +.023 |
| **MARCEL, tuned** | **0.058** | [+.016,+.098] | +.043 |
| current window, 48 Statcast features | 0.057 | [+.013,+.097] | +.047 |
| weighted Statcast history, 19 feats | 0.062 | [+.017,+.105] | +.047 |
| everything (now + history + Marcel) | 0.060 | [+.016,+.103] | +.045 |

**Every head-to-head gap straddles zero.** 48-feature minus Marcel = **-0.002 [-0.039,+0.033],
P(model better) = 0.46**. Everything minus Marcel = +0.002, P = 0.55. **A coin flip.**

### Season level (Marcel's home ground), prior seasons only, n=245
| forecaster | R2 | 95% |
|---|---|---|
| MARCEL tuned | **0.164** | [+.011,+.290] |
| weighted past xwOBA, shrunk | 0.166 | [+.030,+.280] |
| MARCEL classic R=1200 | 0.075 | [-.123,+.235] |
| MARCEL no age bump | 0.102 | [-.070,+.244] |
| **Statcast history, 20 features (GBM)** | **-0.060** | [-.307,+.127] |

The 20-feature GBM is **worse than predicting league average for everyone** (gap -0.228, P=0.00).
267 training seasons, 20 correlated features -> overfit. A 3-parameter formula does not.
**A shrunk average of past xwOBA ties Marcel exactly** (0.166 vs 0.164, P=0.53).
**The value is in the shrinking, not the features.**
Marcel's age adjustment is real: removing it costs 0.062 (P=0.01). A 2004 heuristic with two
hard-coded constants survives four seasons of tracking data.

### WHERE Statcast does win: hitters without a track record
| prior history (quartile) | n | Marcel | model | gap | P(model better) |
|---|---|---|---|---|---|
| **least** | 272 | 0.007 | 0.056 | **+0.049** | **0.94** |
| second | 271 | 0.042 | 0.052 | +0.011 | 0.65 |
| third | 271 | 0.117 | 0.105 | -0.014 | 0.31 |
| most | 271 | 0.048 | 0.008 | -0.040 | 0.11 |
Monotone across four buckets, in the predicted direction. Measurement beats history exactly where
there is no history to average. This is the project's real niche.

### A PREDICTION OF MINE THAT FAILED
I predicted the largest Statcast edge among hitters whose measurements had just MOVED, since Marcel
cannot see a 3 mph bat-speed gain. Top decile of movers: gap **-0.001, P=0.50**. Exactly nothing.
The blind spot I was sure mattered does not, at one month of sample.

### A LEAK I CAUGHT IN MY OWN BENCHMARK
First pass scored season-level Marcel at R2=0.575 with tuning driving the regression constant down
to 200. Cause: `hist_sums(b, y, thru=99)` included the season being forecast. Signature to remember:
**a baseline suddenly performing implausibly well, plus tuning that says "barely regress", is
leakage until proven otherwise.** Fixed in marcel3.py (prior seasons only). The monthly arm was
always clean — its cutoff is the input month.

### What this licenses, precisely
NOT "Statcast is useless for forecasting" — 4 seasons is a short runway and the season-level failure
is a sample-size failure. NOT "the machine works". It licenses exactly: **at one month, with four
seasons of training data, the entire Statcast apparatus is worth about as much as a 2004 weighted
average — except for hitters without a track record, where it is worth considerably more.**

### Ceiling, reconciled (two inconsistent numbers had been reported)
var(baseline talent) .001190 / var(one month's drift) .000726 / var(noise at 87 PA) .002588.
- realistic ceiling (knows talent, cannot foresee drift) **R2 = 0.264**
- oracle ceiling (also foresees drift, unreachable) R2 = 0.425
Marcel and the models all sit at **21-23% of the realistic ceiling**; xwOBA alone at 6%.

---

## 2026-09-12 (later still) — Age vs history, and a correction to how the niche gets described

marcel4.py found the model beats Marcel in the bottom quartile of **prior playing time**. That is
not the same claim as "it works for young players" — a 33-year-old back from two lost seasons also
has thin history. Tested age directly (age_test.py). age vs prior PA correlate at **+0.549**.

### By age (2026 holdout, model = now + history + Marcel combined)
| age | n | Marcel | xwOBA alone | model | gap | 95% | P |
|---|---|---|---|---|---|---|---|
| **22-25** | 253 | 0.049 | 0.008 | 0.116 | **+0.065** | [+.003,+.125] | **0.98** |
| 26-28 | 327 | -0.024 | 0.002 | -0.043 | -0.020 | [-.074,+.035] | 0.23 |
| 29-31 | 268 | 0.102 | 0.030 | 0.089 | -0.014 | [-.070,+.041] | 0.32 |
| 32+ | 237 | 0.110 | 0.013 | 0.088 | -0.023 | [-.081,+.034] | 0.21 |
Ages 22-25 is the **only segment whose CI excludes zero** — sharper than the history split, whose
top bucket touched zero (-0.011).

### Crossed, to separate them
| cell | n | Marcel | model | gap |
|---|---|---|---|---|
| young (<=27), thin history | 353 | -0.004 | 0.018 | +0.022 |
| young (<=27), thick history | 131 | -0.011 | 0.026 | +0.037 |
| older (>27), thin history | 190 | 0.067 | 0.108 | +0.041 |
| **older (>27), thick history** | 411 | 0.112 | 0.065 | **-0.047** |
**The model loses in exactly one cell: established veterans.** It ties or beats everywhere else.
So it is neither purely age nor purely history — it is "does this hitter have a settled track
record".

### IMPORTANT CORRECTION to a natural summary
"Expected metrics beat track record for young players" is **not supported**. **xwOBA alone loses to
Marcel in every age bucket** (0.008 vs 0.049 at 22-25; 0.013 vs 0.110 at 32+). What beats Marcel is
the full 48-feature measurement model, not the expected statistic. Correct summary:
*a rich measurement model beats a track-record forecast wherever the track record is thin or the
player is still developing, and loses to it for established veterans.*

Caveat recorded: 4 age buckets x 4 history quartiles = 8 tests; one CI excluding zero at 5% is about
what chance produces. Treat as a hypothesis for 2027, not a finding.

### Steamer / ZiPS — attempted, blocked
FanGraphs hosts both but **CSV export is members-only**; steamerprojections.com returns HTTP 409.
Critical design point discovered while looking: FanGraphs shows *continuously updated* projections
(`type=steameru`), which already incorporate the season being forecast — using those would reproduce
C1 leakage exactly. **The benchmark requires PRE-season files** (`type=steamer`, published ~Feb).
Blocked pending a manual export; see RESEARCH_BACKLOG S27.
