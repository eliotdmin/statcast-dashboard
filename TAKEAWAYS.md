# Takeaways, with provenance

One line per takeaway, then **how we got there** — because a result without its
derivation is just a number someone asserted, and three of the results below
replaced earlier versions of themselves.

Status: **[H]** holds · **[N]** tested, absent · **[R]** retracted · **[?]** real but
under-powered or post-hoc.

---

## 1. Method — the things that changed how we work

**[H] Grade every forecast against the noise ceiling, not against 1.0.**
At 87 PA a forecaster with perfect knowledge of stable talent scores R² = 0.264.
*How:* for two months of the same hitter, `E[(w₁−w₂)²] = σ²(1/pa₁+1/pa₂) + var(drift)`.
Regressing 16,228 squared differences on the sample-size term identifies both:
σ² = 0.2258, drift sd = .0381, talent sd = .0345. → D17

**[H] Shrink every displayed change by its metric's signal share.**
`var(observed) = var(true) + var(noise)`; noise is computable from sample size, so
true spread comes out by subtraction. Swing length 87% signal, bat speed 85%,
GB% 18%, sweet-spot% **0%**.
*How:* `calibrate.py` over 222 hitters with 250+ PA in both 2025 and 2026. → D16

**[H] Never compute a public metric from a raw column without an acceptance test.**
*How:* `woba_value` credits reached-on-error (.900), fielder's choice (.900) and
dropped third strikes (.700) as reaches. Real wOBA treats all three as outs.
Caught by reconciling against `expected_stats.woba` — Savant's own published
number — which showed +.009 before the fix and +.002 after. Four days of work
inherited the inflation. → D24

**[H] Measure across seasons only in units the rulebook fixes.**
*How:* `sz_top` went from a per-pitch operator estimate (353,643 distinct values
in 2025) to a per-batter formula (390 in 2026). A zone analysis measured in
`sz_top` units said the top of the zone expanded; in absolute feet it contracted
23.5 points. Same data, opposite conclusion. → D15

**[H] Never explain an outcome residual with another outcome rate.**
*How:* the first gap regression found ground-ball-single rate dominant at R²=.246.
A grounder that finds a hole *is* both variables. Its own split-half reliability
is .193 — luck explaining luck. → D18

**[H] Check a mechanism's magnitude before building on it.**
*How:* per-unit effect × spread of the driver × exposure, against the sd of the
thing explained. The ground-ball effect came to 7.3% of the gap's spread — real,
correctly identified, useless for forecasting. One line of arithmetic, run after
the model instead of before. → D23

**[H] A baseline that suddenly performs implausibly well is leakage.**
*How:* season-level Marcel scored R²=0.575 and the tuner chose "barely regress".
Both were symptoms of the history window including the season being forecast. → D21

---

## 2. Forecasting — the main line of work

**[H] Realised wOBA is worse than useless at one month.** Out-of-sample R² = −0.004:
worse than predicting league average for everyone. xwOBA gets +0.015.
*How:* 10,287 hitter-months, fit 2023–25, evaluated once on 2026, weighted by
target-window PA. `predict.py`.

**[H] Once you know xwOBA, wOBA is negative information.** Fitting
`next ~ b₁·wOBA + b₂·xwOBA` within input-sample buckets, b₁ is negative in every
bucket above 55 PA (−0.02, −0.10, −0.08, −0.04).

**[H] Playing time alone out-predicts xwOBA**, 0.032 to 0.015. Not a hitting
skill — the manager's private information on health and matchups. Always ablated. → D19

**[N] Nothing we built beats Marcel. Eight model families, all level or worse.**
48-feature GBM −0.002 [−0.039,+0.033] P=0.46; weighted-history +0.003 P=0.58;
grouped-CV ridge (α=5.6e4) −0.013; elastic net −0.011; PLS-3 −0.022; PCA-5 −0.037;
**Marcel + modelled residual −0.016**; Marcel + boosted residual −0.004; fitted
blend −0.003.
*How:* Marcel's regression constant tuned on training years (so the baseline gets
the same courtesy as the challenger), models re-run with the same career history
Marcel sees. `marcel2.py`, `marcel3.py`, `stability_and_models.py`. → D20

**[H] At season level a Statcast model is worse than nothing** (R² = −0.060 vs
Marcel's 0.164) while a shrunk average of past xwOBA ties Marcel exactly (0.166).
**The value is in the shrinking, not the features.**

**[H] The single biggest available improvement is regressing harder.**
Marcel's constant 1200 → tuned 3000 moved season R² from 0.0745 to 0.1640, P=0.97
— more than every Statcast feature combined. Past-to-future correlation of a
hitter's weighted record is only **0.40**. → D22

**[?] The one place measurement wins: no settled track record.** Ages 22–25,
+0.065 [+0.003,+0.125], P=0.98; monotone across four history quartiles. Crossing
age × history, the model loses in exactly one cell — older *and* thick history.
Caveat: 8 segments tested, one interval excluding zero is what chance produces.

**[R] Three of my own pre-registered predictions failed:** the xwOBA edge is
humped not declining; the weight on xwOBA rises rather than falls with sample;
and the advantage does *not* concentrate where measurements just moved
(−0.001, P=0.50).

---

## 3. Stability — added 2026-09-13, the slump question

**[H] Skills are stable. Results are not. The gap between them is enormous.**
Adjacent-window correlation, same hitter, same season:

| metric | 1 month | 2 months | 3 months |
|---|---|---|---|
| bat speed | .919 | .978 | .993 |
| whiff/swing | .711 | .922 | .971 |
| K% | .587 | .875 | .955 |
| exit velo | .598 | .883 | .960 |
| xwOBA | .321 | .447 | .516 |
| **wOBA** | **.135** | **.213** | **.240** |

**[H] And a "slump" does not carry forward at all.** Remove each hitter's own
mean — which is what isolates the slump from the hitter — and the carryover
collapses to nothing: wOBA −0.038 / −0.080 / −0.055, xwOBA +0.004 / −0.000 / +0.072.
*Caveat recorded:* demeaning a short panel induces a mechanical negative bias of
roughly −1/(T−1), so the small negatives are consistent with **zero** carryover
rather than genuine anti-persistence. The honest reading is ≈ 0.
*Operational consequence:* when a hitter is slumping, the slump itself predicts
nothing. Look at whether **whiff rate, bat speed or exit velocity** moved, because
those are the things that persist.
*How:* `stability_and_models.py`, 5,212 adjacent one-month pairs.

---

## 4. The wOBA − xwOBA gap

**[H] Not a within-season skill** (split-half ρ = .164) but **persists across
seasons for hitters** — corrected r = +0.267, +0.302, +0.238 over three
independent year-pairs.

**[H] And not at all for pitchers**: +0.104, −0.021, +0.161, split-half .213.
Whatever drives the hitter version is a batter attribute.

**[R] The mechanism we proposed is dead.** "xwOBA under-rates ground balls by 23
points, 52% of it reached-on-error" was the inflated numerator (§1, D24).
Corrected, the ground-ball gap is **+.0008**.

**[H] What survives:** xwOBA over-rates **popups** by 17.6 points per batted ball.
Small in aggregate (7% of batted balls).

**[?] So the persistence is real and currently unexplained.** Best open question
in the project.

---

## 5. Counts

**[H] The count matters roughly twice as much as the hitter.**
0–2 reached → .2074. 3–0 reached → .5580. Range .351 against .185 across 286
hitters with 1,000+ PA — **1.89×**, and 4× on standard deviations. An average
hitter at 3–0 out-produces the best hitter in baseball; at 0–2 he is worse than
the worst.
*How:* `counts.py`, every PA that passed through each count, 2023–26. Absolute
values are ~6–9 points high pending the D24 correction; the relative structure is
unaffected because the inflation is near-uniform across counts.

---

## 6. Pitching

**[N] Pitch-mix entropy does not predict results** — and re-run where it had the
best possible chance (third time through the order, where familiarity should
matter most), arsenal breadth still does nothing: −0.0027 ± 0.0040.

**[H] The times-through-order penalty is real within pitcher:** +24 points of wOBA
from the first pass to the third.

**[N] Tunnelling: nothing.** 340,000 swings, consecutive different pitch types
baselined on (previous type, this type, count). Excess whiff wanders between
−0.24 and +0.14 points with no ordering.
*Caveat:* release-point distance is a proxy; true trajectory separation at the
commit point was never computed.

**[N] Within-pitcher velocity decay does not predict late-game damage**
(+0.0031 ± 0.0024). The between-pitcher version said it did, monotonically across
five quintiles at r = +0.905 — entirely selection. Kept as the canonical example
that monotonicity across bins is not evidence.

**[H] xwOBA-against beats wOBA-against by 34% relative** at predicting next season
(0.170 vs 0.126) — a much bigger edge than the hitter version. And **K% + BB%
alone reach 0.156** using no batted-ball data at all: DIPS (1999), reproduced.

**[H] xERA adds nothing to analyse.** Savant's glossary: "a simple 1:1 translation
of xwOBA, converted to the ERA scale." Any xERA−ERA decomposition is the
xwOBA-against analysis plus sequencing and the scorer's earned/unearned call,
which is not in this data.

---

## 7. Hitting, zone, measurement

**[H] 89% of hitters slow their bat with two strikes**, by 1.37 mph. Those who
shorten most strike out less and produce more (r = −0.147 with 2K wOBA).
*Not causal* — the within-hitter test was never run.

**[H] Platoon split is a real trait at 72% signal**, but 28% of any published
leaderboard's spread is sampling noise.

**[H] The 2026 challenge zone is shorter, deeper, narrower and crisper.**
Top 3.4–3.6 ft: 41.1% → 17.6% called strikes. Bottom 1.4–1.6 ft: 42.0% → 52.5%.
The 20%–80% transition band narrowed 2.61 → 1.90 inches. Explains the
between-catcher framing spread collapsing from 15.5 runs to 10.6.

**[H] Bat speed is park-dependent**: home-minus-road sd 0.23 mph, correlated
+0.456 with the exit-velocity park effect — a shared installation effect, not
hitting.

**[R] Chase rate is coincident, not leading.** Originally scored confirmed because
chase changes were *detectable*, which is not what the hypothesis claimed. Within
hitter, 1,119 month-triples: Δchase → next month's ΔwOBA is +0.046 ± 0.036 (null),
while same-month is −0.370 ± 0.041.

**[H] Monthly wOBA changes mean-revert at −0.51.** Half of any month's movement is
mechanically given back. Any in-season alerting must account for it.
