# The statistics in this project, derived

Every formula this repo relies on, with (a) the plain-language version, (b) the
derivation, and (c) why the quantity means what we claim it means. Read top to bottom
once; after that it is a reference.

Notation: `X` is what we observe, `T` is the truth we want, `E` is an expectation,
`var` a variance, `cov` a covariance, `n` a sample size (plate appearances, batters
faced, tracked swings).

---

## 0. The one idea everything else is built on

**Plain version.** A player's stat line is his ability plus what happened to him. You
want the first part. You can only see the sum.

**Formal version.** Every measurement decomposes as

```
X = T + e ,      E[e] = 0 ,      cov(T, e) = 0
```

`T` is *true talent over this window* -- what he would average if you could replay the
same window infinitely many times. `e` is everything else: which pitchers he happened to
face, whether a line drive found a glove, which 40 of his 600 possible pitches actually
arrived. The assumption `cov(T, e) = 0` is what makes the rest work, and it is an
assumption: it says a good hitter is not systematically luckier. For batted-ball outcomes
that is close to true. For something like *wins* it is badly false.

Because the two parts are uncorrelated, variances add:

```
var(X) = var(T) + var(e)
```

This is the entire foundation. Everything below is a way of estimating one of those
three terms from data.

---

## 1. Reliability, and what "% real" actually means

**Plain version.** Line up 300 hitters by their bat speed over two weeks. Line them up
again by their wOBA over the same two weeks. Both lists look equally like rankings. One
of them would come back almost identically if you re-ran the two weeks; the other would
reshuffle almost completely. Reliability is the number that tells you which is which.

**ELI5 version.** You and 300 friends each flip a coin 10 times and line up by how many
heads you got. That ranking is *entirely* fake -- everybody's coin is the same. Now you
all take a math test and line up by score. That ranking is almost *entirely* real.
Reliability is "what fraction of the lineup is the math test and not the coin flips."
Two weeks of wOBA is mostly coin. Two weeks of bat speed is mostly math test.

**Formal version.** Reliability is defined as

```
rho = var(T) / var(X)  =  var(T) / (var(T) + var(e))
```

a number between 0 and 1. Substituting the decomposition from Section 0, it is the share
of the observed spread *between players* that comes from players actually differing.

Three things follow immediately, and all three are constantly misread:

1. **It is a property of the column, not the cell.** `rho = 0.45` does not mean any one
   player's wOBA is 45% accurate. It means that across the population you measured, 45%
   of the variance in the ranking is real. Ask it about a single player and it has no
   answer.
2. **It depends on the population.** The same metric measured on 300 major leaguers and
   on 300 randomly chosen adults has wildly different reliability, because `var(T)` is
   different, even though `var(e)` is identical. Restrict to a narrow group and
   reliability falls. This is why "reliability" figures quoted from one study do not
   transfer to another sample.
3. **It depends on `n`.** `var(e)` shrinks roughly as `1/n`, `var(T)` does not, so
   reliability rises with sample size. Quoting a reliability without the sample size it
   was measured at is meaningless -- which is exactly why this repo stores `n0` next to
   every `sb` in `blocks_all.json`.

---

## 2. How we estimate rho without ever seeing T

**Plain version.** Split the season in half. If the two halves agree, the thing is real;
if they disagree, it was noise. Then correct for the fact that each half is only half a
season.

**Formal version.** Take two independent measurements of the same player in the same
season: odd-numbered half-month blocks (`X1`) and even-numbered ones (`X2`). Both measure
the same `T` with independent errors:

```
X1 = T + e1 ,   X2 = T + e2 ,   cov(e1, e2) = 0
```

Now compute the correlation between them:

```
              cov(X1, X2)            cov(T + e1, T + e2)
r  =  --------------------------  =  -------------------------
       sqrt(var(X1) var(X2))              var(X1)                (halves are equal size)

      var(T) + cov(T,e2) + cov(e1,T) + cov(e1,e2)        var(T)
   =  -------------------------------------------   =   ---------
                      var(X1)                            var(X1)
```

**Every cross term dies**, because the errors are independent of each other and of the
truth. So the split-half correlation *is* the reliability -- but of a half-season, not a
full one. That is the whole trick: a correlation you can compute equals a variance ratio
you cannot.

**In this repo:** `blocks_all.py` computes exactly this, on 1,572 hitter-seasons with a
mean of 207 PA per half.

---

## 3. Spearman-Brown: correcting for the split, and projecting to any n

**Plain version.** A test with twice as many questions is more reliable, in a way you can
write down exactly. Spearman-Brown is that formula. It converts "reliability at 207 PA"
into "reliability at any number of PA."

**Formal version.** Average `k` independent replications of a measurement. The truth does
not change; the noise averages down:

```
var(T)  ->  var(T)                 (unchanged)
var(e)  ->  var(e) / k             (independent errors average out as 1/k)
```

So the reliability of the `k`-fold measurement is

```
                var(T)                          divide top and bottom by var(T):
rho_k  =  -----------------------
           var(T) + var(e)/k

           1                        1                       k * rho_1
       = -------------------  =  ----------------------  = -------------------
          1 + (var(e)/var(T))/k    1 + (1-rho_1)/(k rho_1)   1 + (k-1) rho_1
```

using `var(e)/var(T) = (1 - rho_1)/rho_1`. That last form is the **Spearman-Brown
prophecy formula**:

```
rho(k) = k * rho_0 / (1 + (k - 1) * rho_0)
```

Two uses, and this repo needs both:

- **k = 2**, to go from a half-season split to a full season:
  `rho_full = 2r / (1 + r)`.
- **k = n / n0**, to go from the measured sample size `n0` to whatever sample size the
  user just selected in the Stretch Finder. This is the `relAt()` function in the
  artifact and `rel_at()` in `profile.py`.

**Sanity check, and why we trust it.** The projection predicts a month-to-month wOBA
reliability of .15; independently measured, it is .135. It predicts bat speed at .94;
measured, .919. Both a little optimistic, in the same direction, by a similar margin --
which is what you expect, because Spearman-Brown assumes the truth held still over the
window and real talent drifts. Use it for the shape, not the third decimal.

**Where it breaks.** It assumes the `k` replications are exchangeable. Pitchers faced in
April are not exchangeable with pitchers faced in September; a hitter who changes his
swing in June violates the constant-`T` assumption outright. Both push true reliability
*below* what the formula reports.

---

## 4. Shrinkage: why the same rho tells you what to believe

**Plain version.** If only 45% of the spread is real, then only about 45% of a player's
distance from average is real. Keep 45% of it and throw the rest away.

**Formal version.** We want `E[T | X]`, the best guess at the truth given the observation.
Under joint normality (and as the best *linear* estimator regardless),

```
E[T | X]  =  mu + b (X - mu)  ,        b = cov(T, X) / var(X)
```

and since `cov(T, X) = cov(T, T + e) = var(T)`,

```
b = var(T) / var(X) = rho
```

**The regression coefficient is the reliability.** That is not a coincidence or an
analogy -- it is the same ratio. So the honest estimate of a player's true rate is

```
T_hat = league_mean + rho * (observed - league_mean)
```

and in percentile space, where the league mean is the 50th percentile:

```
pct_shrunk = 50 + rho * (pct_raw - 50)
```

That is the solid bar in the Stretch Finder. The dashed outline is `pct_raw`, which is
what an uncorrected Savant-style page shows. The gap between them is the part of the
ranking that is coin flips.

**The outside example worth knowing.** Efron and Morris (1977, *Scientific American*,
"Stein's Paradox in Statistics") used 18 hitters' first-45-at-bat batting averages to
predict their rest-of-season averages. Shrinking every player toward the group mean beat
using each player's own average by a factor of about 3.5 in total squared error --
*including for the player who ended up best*. The result is counterintuitive enough that
it is called a paradox: you improve your estimate of Player A by using data from Players
B through R, who have nothing to do with him. What is actually happening is Section 0.
Each observed average is truth plus noise; the noise is what makes the spread of observed
averages wider than the spread of true averages; shrinking corrects the width.

---

## 5. The two questions you must ask about any change

**Plain version.** "Could this be noise?" and "is it big?" are different questions, and a
metric can pass one and fail the other in both directions.

**Formal version, question 1 (`delta_z`).** For a player measured over `n1` now and `n2`
before, the noise-only standard error of the difference is

```
var_noise(n) = var_league_observed(n) * (1 - rho(n))          [from Section 1]
var_noise(n2) = var_noise(n1) * (n1 / n2)                     [noise scales as 1/n]

se = sqrt( var_noise(n1) + var_noise(n2) )
z  = (rate_now - rate_before) / se
```

`|z| >= 2.5` is the "real" verdict in `profile.py`; 1.5-2.5 is "weak".

**Formal version, question 2 (`delta_sd`).** The same difference expressed in units of
how much players differ from each other:

```
delta_sd = (rate_now - rate_before) / sd_league_observed
```

**Why you need both.** Arm angle has reliability ~0.999, so `var_noise` is nearly zero
and almost any drift clears `z = 2.5` -- a 0.9-degree change is statistically
unambiguous and 0.07 league standard deviations, i.e. nothing. Conversely, Dylan Cease's
2026 strikeout rate fell 4.2 points over 242 batters faced: `z = -1.06` (cannot be
distinguished from noise) and 0.6 sd (a change anyone would notice). The honest sentence
is "he may well have changed this much and this sample cannot tell you," which is more
useful than either verdict alone. This is D26.

This is the same distinction as statistical significance versus effect size in any other
field, and it bites harder here because Statcast measures some things with instruments
and other things by waiting for outcomes.

---

## 6. wOBA: what it is and why the weights are what they are

**Plain version.** Batting average treats a single and a home run the same. OBP treats a
walk and a home run the same. wOBA weights each outcome by how many runs it is actually
worth, then rescales the whole thing so it reads like an OBP.

**Formal version.** For each event type, compute the **linear weight**: the average change
in run expectancy caused by that event, measured across all 24 base-out states.

```
w_event  =  E[runs from this half-inning | after the event]
          - E[runs from this half-inning | before the event]
          + runs that scored on the play
```

Those raw weights run about: walk +0.31 runs, single +0.44, double +0.75, triple +1.02,
home run +1.38, out -0.26. Then wOBA sets the out at zero and multiplies everything by a
scale factor chosen so that league wOBA equals league OBP -- roughly 1.15 in the modern
game, though FanGraphs recomputes it annually. That gives the familiar coefficients:

```
          0.690*uBB + 0.722*HBP + 0.888*1B + 1.271*2B + 1.616*3B + 2.101*HR
wOBA  =  ------------------------------------------------------------------
                          AB + BB - IBB + SF + HBP
```

The scaling is cosmetic -- it exists so .320 means "average" to anyone who knows OBP --
but it means wOBA coefficients are *not* runs, and you must divide by the scale (~1.15)
before converting a wOBA difference into runs.

**The trap this project fell into (D24).** Statcast's pitch-level `woba_value` column is
not wOBA. It credits reached-on-error at 0.900, fielder's choice at 0.900, and a dropped
third strike at 0.700 -- events that do not raise your OBP and are not in wOBA's
numerator. Four days of analysis inherited a 9-point inflation and one published finding
was entirely an artifact of it. The fix is a HIT-restricted numerator and an acceptance
test against the published `expected_stats.woba`. **Never compute a public metric from a
raw column without reconciling it against the published version.**

---

## 7. xwOBA: the same weights, applied to what *should* have happened

**Plain version.** Take every batted ball. Look up how often balls hit at that exit
velocity and launch angle became singles, doubles, triples and homers, league-wide. Use
those probabilities instead of what actually happened. Strikeouts and walks stay real,
because nothing is in doubt about them.

**Formal version.** For each batted ball `i` with exit velocity `v` and launch angle `a`
(plus sprint speed on weakly-hit balls, where legs matter):

```
xwOBA_contribution_i  =  sum over outcomes o of  P(o | v, a) * w_o
```

where `P(o | v, a)` is estimated from every comparable batted ball in the league and `w_o`
is the same linear weight as in wOBA. Walks, hit-by-pitches and strikeouts contribute
their actual weights. Divide by plate appearances.

**Why it is more predictive than wOBA.** It replaces the noisiest step in the chain --
what a fielder did with the ball -- with a league average, and leaves the parts the hitter
controls intact. In the language of Section 0, it removes a large chunk of `var(e)` while
leaving `var(T)` alone, which raises `rho`. Measured here: half-season reliability .691
for xwOBA against .479 for wOBA.

**What it deliberately ignores, and why that matters.** `P(o | v, a)` is a league average,
so xwOBA cannot see spray angle, park, the shift, or the fact that a specific hitter beats
out more grounders than the league. Those are real, persistent hitter traits, and their
absence is one candidate explanation for the wOBA-xwOBA gap this project measures at
+0.27 standard deviations, replicated across three year-pairs and currently **unexplained**
(the ground-ball mechanism was retracted at D23/D24). A gap is a fact about two numbers.
It is not a forecast, and "due for regression" is not a permitted inference from it.

---

## 8. Marcel: the benchmark everything must beat

**Plain version.** The dumbest projection that is not stupid. Weighted average of the last
three seasons, dragged hard toward league average, nudged for age. Tom Tango named it
after Marcel the monkey from *Friends*, on the argument that if your system cannot beat a
monkey it does not exist.

**Formal version.**

```
1. Weight the last three seasons 5 / 4 / 3 (most recent heaviest).
2. Add R plate appearances of league-average performance:

            5*S1 + 4*S2 + 3*S3 + R * league_rate
   proj  =  -------------------------------------
            5*P1 + 4*P2 + 3*P3 + R

3. Age adjustment, applied multiplicatively:
       under 29:  * (1 + (29 - age) * 0.006)
       over  29:  * (1 + (29 - age) * 0.003)
```

Step 2 is Section 4 in disguise. Adding `R` PA of league average *is* shrinkage: the
fraction of the player's own record that survives is `P/(P+R)`, which is exactly the
reliability of a sample of size `P` when `R = var(e)/var(T)` in PA units.

**What this project found (D21, D22).**
- My first Marcel implementation leaked -- the history window included the season being
  forecast -- and reported R2 = 0.575 with the tuner choosing `R = 200`. The diagnostic
  worth memorizing: *a baseline performing implausibly well, combined with the tuner
  saying "barely regress," is leakage.* The true figure is 0.164.
- Changing `R` from the classic 1200 to a tuned 3000 moved season-level R2 from 0.0745 to
  0.1640 -- a larger gain than every Statcast feature in this repo combined. Regressing
  harder is the only free lunch found so far.

---

## 9. The ceiling: why R2 = 0.034 can be most of what exists

**Plain version.** You are trying to predict a number that is itself mostly noise. Even a
perfect forecast of true talent would score badly against it. So you have to know what
perfect would have scored.

**Formal version.** The target -- next window's wOBA over `n` PA -- is itself `T + e`.
The best possible prediction is `T`. Its R2 against the observed target is

```
              var(T)                             sigma^2
R2_max  =  -------------  ,    var(e) = E[ ------------- ]
            var(T+e)                          n_target
```

where `sigma^2` is the per-PA variance of wOBA outcomes, measured in `calibrate.py` at
**0.2258**. For the 2026 holdout in `streaks.py` (mean 96 PA per target window):

```
var(observed next wOBA) = 0.00341
var(noise)              = 0.00243
var(true talent)        = 0.00097
R2_max                  = 0.2854
```

Against that ceiling, the expected-stats model's out-of-sample R2 of 0.0335 is **12% of
everything available**, not 3% of a perfect score. Recent wOBA alone gets 0.004 -- and at
60-day windows the coefficient turns *negative*, which is the cleanest statement of why
this project exists.

---

## 10. The machinery that keeps us honest

**Temporal holdout.** Fit on 2023-2025, look at 2026 exactly once. Not a random split:
a random split lets the model see the future, and in a domain where league-wide conditions
change annually (see D15, the 2026 `sz_top` redefinition) that is fatal.

**GroupKFold by player.** When cross-validating within the training years, all of a
hitter's windows go in the same fold. Otherwise the model learns "this is Aaron Judge"
from one fold and is tested on Aaron Judge in another -- an identity lookup that looks
like skill.

**Paired percentile bootstrap.** To ask whether model B beats model A, resample the *same*
rows for both, 3,000-4,000 times, and read the percentiles of `R2(B) - R2(A)`. Pairing
matters: the models' errors are highly correlated, so an unpaired comparison has far wider
intervals and will tell you nothing is significant.

**Characterization tests.** `tests/test_facts.py` asserts the findings, not the code.
Each test names the decision it guards, and the wOBA test asserts *both* directions -- the
corrected numerator matches the published value, and the raw column still over-credits. If
the provider ever fixes `woba_value`, the test fails and D24 gets retired deliberately
instead of silently.

**Pre-registration.** Write the prediction down before running it. Three of the five in
this project failed (P1, P2, P5), which is the point: without writing them down first,
three failures would have quietly become "we explored and found nothing interesting."

---

## Appendix: the numbers this project measured

Half-season split-half reliabilities, corrected by Spearman-Brown, at the stated mean
sample size. From `blocks_all.py`, 2023-2026.

| hitters (n0 = 207 PA) | rho | pitchers (n0 = 176 BF) | rho |
|---|---|---|---|
| swing length | .982 | arm angle | .999 |
| bat speed | .974 | extension | .997 |
| attack angle | .961 | fastball velo | .997 |
| whiff% | .917 | spin rate | .994 |
| chase% | .909 | whiff% | .812 |
| K% | .861 | zone% | .801 |
| exit velo | .865 | K% | .742 |
| xwOBA | .691 | xwOBA against | .534 |
| wOBA | .479 | wOBA against | .389 |
| sweet-spot% | .370 | edge% | .228 |

The ordering is the finding. Everything measured with an instrument sits at the top.
Everything measured by waiting for outcomes sits at the bottom. wOBA -- the statistic the
entire discourse runs on -- is below half.
