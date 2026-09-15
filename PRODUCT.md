# Ten ways to productize this

The asset here is not the data. Statcast is free and everyone has it. The asset is the
**calibration layer**: a measured, validated table of how much of each metric is real at
each sample size, plus the discipline to apply it. Every idea below is a way of selling
*that*, and the ones that fail are the ones that quietly revert to selling the data.

Ordered roughly by (differentiation x feasibility).

---

## 1. The Prediction Ledger — score yourself in public

Every profile the app generates writes an immutable, timestamped forecast: player, metric,
shrunk projection, sample size, date. Thirty days later a cron job scores it. The site has
a permanent, un-editable accuracy page.

**Why it's the strongest idea here.** No baseball content property does this. Every take
on the internet is unfalsifiable by construction — the podcast that called a hot streak
real in June is not searchable in September. Philip Tetlock's *Expert Political Judgment*
(2005) ran exactly this experiment on 284 professional pundits over twenty years and found
their accuracy indistinguishable from chance, largely because nobody was keeping score.
Metaculus and the Good Judgment Project turned that finding into a product. The move here
is to be the first baseball site whose calibration is a feature rather than a claim.

**Why it's feasible for you specifically.** You already have the shrunk projections and the
holdout machinery. The scorer is ~80 lines. And your project has the rarest possible
credential for it: a `DECISIONS.md` that documents four of your own retractions.

**Risk.** You will be publicly wrong, often. That is the product.

---

## 2. Reliability-as-a-service — sell the layer, not the dashboard

A tiny API: `POST {metric, n}` → `{reliability, shrink_factor, n_for_0.7}`. Plus a
`/shrink` endpoint that takes a raw leaderboard and returns the honest one.

**The analogy.** Plaid's value was never the bank data — it was the boring normalization
layer everyone else didn't want to build. The same applies here: half the baseball apps on
the internet display raw 40-PA percentiles because computing the shrinkage correctly takes
a week of work nobody budgets. Sell the week.

**Effort.** A weekend. The table already exists in `output/calibration.json` and
`blocks_all.json`'s `rel` block.

**Risk.** Tiny market, and the obvious buyer (a fantasy site) would rather copy the table
than pay for it. Treat as a credibility artifact and a lead-generator, not a revenue line.

---

## 3. "Don't Chase" — the inverse alert product

A daily wire of the hottest and coldest stretches in baseball, sorted by **how little of
each is real**. "Nine players are in the top 10 of wOBA over the last two weeks. Here is
what each of their bat-tracking numbers says, and here is the one whose inputs actually
moved."

**Why it sells.** Fantasy and DFS are a market of people making sample-size errors with
money, and every existing product amplifies the error — waiver-wire columns are a machine
for chasing 40-PA hot streaks. This is the only product in the category that profits by
telling users to do nothing. Compare Vanguard's entire business model against active
management: the pitch is *the cost of your instinct*.

**Effort.** Low — it is a daily run of `blocks_all.py` plus a ranking. It is the most
natural first paid product.

---

## 4. Automated pre-game one-pagers for beat writers and broadcasts

One page per starting pitcher per game: what his delivery has actually done in the last
three starts, which of it clears the noise bar, and one honest sentence about the results.
Generated the night before, emailed at 8am.

**The precedent.** The Associated Press automated its quarterly earnings stories with
Automated Insights in 2014 and went from ~300 companies covered per quarter to ~4,400.
That worked because earnings reports are structured, repetitive, and nobody enjoys writing
them. Pre-game notes are identical: a beat writer produces them under deadline, from the
same Savant page, every day, 162 times.

**Risk.** Sales cycle into newsrooms is brutal and budgets are gone. A cheaper version is
to give it away to five beat writers and let attribution be the marketing.

---

## 5. The arbitration and agency brief

Sell to agencies, not fans. A player's arbitration case, or his free-agent pitch, lives or
dies on whether you can argue the surface stats understate him. Your tooling produces
exactly that argument in a defensible form: *here is what he controls, here is the
reliability of each number, here is the part of last year's results that was noise.*

**The outside example.** This is the *Moneyball* trade in reverse — the original edge was
teams buying undervalued skills; the durable business turned out to be on the agent side,
where Scott Boras Corporation has run an in-house analytics group producing exactly these
binders for two decades. Those binders are hand-made. Yours would not be.

**Risk.** Relationship business, near-zero inbound, and you'd be competing with teams'
internal groups. But it is the only idea on this list with five-figure-per-client pricing.

---

## 6. Open the benchmark: a public Marcel leaderboard

Publish the temporal-holdout harness — fit on 2023-2025, score once on 2026 — and let
anyone submit a projection system. Score everything against Marcel. Keep the test set
sealed.

**The precedent.** The Netflix Prize (2006-09) and, more to the point, MLPerf and Kaggle:
the entity that owns the *evaluation* ends up more central than any entity that owns a
model. You already have the hardest part — a leak-free harness and the scar tissue from
D21, where your own first benchmark leaked and reported R² = 0.575 instead of 0.164.

**Effort.** Moderate. The harness exists; the submission plumbing does not.

**Risk.** Needs a community to be interesting. Seed it by submitting three of your own.

---

## 7. Port the machinery to a sport where nobody has done it

The calibration pipeline is sport-agnostic: it needs repeated measurements of the same
performer and a natural split. College baseball (Trackman is everywhere now), KBO/NPB,
minor-league Statcast, cricket ball-tracking, tennis serve data.

**Why it's a real moat.** In MLB you are competing with FanGraphs, Savant, THE BAT, and
forty smart people on Twitter. In NPB or in D1 college, the reliability table simply does
not exist publicly, and the first correct one becomes the reference. This is how
Football Outsiders started — DVOA was not a better idea than what baseball had, it was the
same idea applied where nobody had applied it yet.

**Risk.** Data acquisition is the whole job, and it is unglamorous.

---

## 8. The sample-size planner for hitting labs

`How many swings do I need before I can tell whether this change worked?` Input: the metric
and the effect size you care about. Output: the number of tracked swings, with the power
curve.

**Why it matters.** Every driveline-style facility and every college program now runs
bat-tracking, makes a mechanical change, and evaluates it on 40 swings. This is the same
arithmetic as a clinical-trial power calculation, and clinical research solved the cultural
problem by making the calculation *mandatory before you start*. Being the tool that a coach
runs before the intervention rather than after is a genuinely different position in the
market.

**Effort.** Very low — it is the Spearman-Brown projection run backwards. Probably the best
effort-to-usefulness ratio on this list.

---

## 9. Natural-language search over the block store

"Show me hitters who added two degrees of attack angle mid-season and kept it." The prefix-
sum block store already answers arbitrary date ranges in O(1); an LLM translating English
into a range query over it is a thin, reliable layer — the model emits a query, not a fact,
so it cannot hallucinate a number.

**The design principle worth stealing.** Let the model choose *what to look up*, never
*what is true*. That is why text-to-SQL products work and "ask the AI about the data"
products don't.

**Risk.** Demo-friendly, retention-hostile. Build it last.

---

## 10. The embeddable widget

A single `<script>` tag that renders the shrunk percentile card for any player-stretch,
free, with a footer link. Datawrapper grew almost entirely this way: newsroom charts carry
the byline into every article that uses them.

**Why it's on the list despite being the least interesting.** It is the only idea here that
distributes itself. Everything above requires you to go find users.

---

## What I'd actually do

**#1 and #3 together.** The Don't-Chase wire gives you a daily reason to exist and a
plausible $5/month audience; the Prediction Ledger makes it the only such product that can
prove it works. They share all their infrastructure. #8 is a one-afternoon side quest with
an outsized chance of getting linked by a coach with an audience.

The trap is #9 and #10 — both are fun to build, and neither makes anyone trust you.

---
---

# Deep dive: #4, automated pre-game one-pagers

## What the product actually is

One page, per starting pitcher, per game, generated the night before and delivered at
7am local. Four blocks:

1. **What his delivery has done in the last three starts**, against his own season
   baseline, with `verdict` and `size` from `profile.py`. Velocity, extension, arm angle,
   spin, release point.
2. **The two or three things that actually moved**, in plain sentences, with the ones
   that did not move explicitly listed as "unchanged" -- because the negative is what a
   broadcaster needs to avoid saying something false.
3. **The matchup slice**: how this lineup has done against this pitch mix, shrunk.
4. **One "do not say this" box**: the numbers that look like a story and are not. If his
   BABIP is .180 over four starts, the box says so and says what the honest version is.

Block 4 is the differentiator and the reason a beat writer would keep opening it.

## Who buys, realistically

Three tiers, and only one of them is a business:

- **MLB club communications / broadcast partners.** Every RSN produces a version of this
  by hand. A graphics producer spends 3-5 hours per game building notes off Savant. 30
  clubs x 162 games. This tier has budget and a procurement process measured in quarters.
- **National outlets** (The Athletic, ESPN, MLB.com). They have in-house data teams and
  will build it rather than buy it. Skip.
- **Beat writers and local radio** individually. No budget, enormous need. This is the
  distribution tier, not the revenue tier.

**The realistic path is to give it away to the third tier to get to the first.** Five
beat writers using it and crediting it is the only credential that gets a club call
returned.

## The precedent, in detail

The Associated Press automated earnings stories with Automated Insights' Wordsmith in
mid-2014. Before: roughly 300 companies covered per quarter, written by staff. After:
about 3,700 -- a 12x expansion of coverage with no additional writers, and the AP
publicly said the freed-up time went to actual reporting rather than layoffs. Two details
matter for you:

1. **It worked because the input was structured and the output was formulaic.** Earnings
   releases arrive as tables. Pre-game notes are the same shape. The moment the task
   requires judgment about *why*, automation quality falls off a cliff -- which is exactly
   why block 4 above is constrained to "here is what you cannot conclude" rather than
   "here is what happened to him."
2. **It did not sell as AI.** It sold as coverage expansion. Nobody bought a language
   model; they bought 3,400 more stories. Your pitch is not "LLM scouting reports," it is
   "your graphics producer gets four hours back and stops putting a .180 BABIP on air as
   if it meant something."

The counter-precedent is worth knowing too: the *LA Times* Quakebot (2014) generated
earthquake stories automatically and in 2025 published a false 6.3-magnitude alert because
USGS re-published a 1925 quake record with a current timestamp. Automated pipelines fail
by trusting their input. Your equivalent failure mode is D24 -- a provider column that
silently means something other than its name -- and your defense is the acceptance test.

## Unit economics

Per page: roughly 3k input tokens (mostly a cached system prompt, billing at 0.1x) and
400 output. On Sonnet at $3/$15 per MTok that is well under a cent. 30 games x 2 starters
= 60 pages/day x 180 days = 10,800 pages, call it **$100-150 per season in inference**.
The cost is entirely the data pipeline and the sales motion, which is the usual shape:
the model is free, the distribution is not.

## What would kill it

- **Latency of trust.** One wrong sentence on air and you are out. This argues for
  shipping block 4 (the negative constraints) *first*, alone, as a "do not say this"
  sheet, and adding generation only after the constraint layer has been right for a
  season.
- **Clubs' internal groups.** Every team already has an analyst who could build this. The
  wedge is that they build for the front office, not for comms, and comms cannot get
  their time.

---

# Deep dive: #8, the sample-size planner

Built. `planner.py`. This is the one on the list that was an afternoon, and it may be the
most useful thing in the repo.

## The table that is the product

Plate appearances needed for a between-player ranking to reach a given reliability
(2023-2026, half-season split-half, Spearman-Brown projection):

| metric | rho at 207 PA | rho=0.5 | rho=0.7 | rho=0.8 | rho=0.9 |
|---|---|---|---|---|---|
| swing length | .982 | 4 | 9 | 15 | 34 |
| bat speed | .974 | 6 | 13 | 22 | 50 |
| attack angle | .961 | 8 | 20 | 34 | 76 |
| whiff% | .917 | 19 | 43 | 75 | 168 |
| chase% | .909 | 21 | 48 | 83 | 186 |
| K% | .861 | 33 | 78 | 133 | 300 |
| exit velo | .865 | 32 | 75 | 129 | 290 |
| hard-hit% | .822 | 45 | 105 | 180 | 404 |
| xwOBA | .691 | 93 | 216 | 371 | 834 |
| BB% | .728 | 77 | 181 | 310 | 697 |
| wOBA | .479 | 225 | 524 | 899 | **2,023** |
| sweet-spot% | .370 | 353 | 823 | 1,411 | **3,176** |

Read the last column. **wOBA needs three and a half seasons to become a 90%-real
ranking.** Sweet-spot% needs five and a half. Bat speed needs fifty plate appearances.
That is the entire thesis of this project in one table, and it is the kind of artifact
that gets screenshotted.

## The second mode: detectable difference

`--detect` answers the question a hitting coach actually has. Same decomposition,
rearranged into a power calculation:

```
n = n0 * (1 - rho) * var_league(n0) * ( (z_{alpha/2} + z_beta) / delta )^2
```

Worked examples from the tool:

- **A pitcher who has lost 1.0 mph**: detectable at 80% power in **26 batters faced** --
  one start. Velocity is measured with reliability .997 and a league sd of 2.4 mph.
- **A hitter who has gained 1.0 mph of bat speed**: **369 PA** against a baseline treated
  as known, and *impossible* against a 300-PA baseline -- the tool says so explicitly,
  because when the required `n` exceeds the baseline's own size there is no follow-up
  window that resolves the difference. The answer is "lengthen the baseline first," which
  is a real and non-obvious piece of experimental design.
- **A 2-degree attack-angle change**: **215 PA**.
- **A 30-point wOBA change**: **1,962 PA**. Nobody is ever measuring this within a season.

## Why this is the right place in the market

The analogy is exact, not loose. A clinical trial computes its sample size *before*
enrollment; ICH E9 and every journal's CONSORT checklist require the calculation in the
protocol, and post-hoc power analysis is considered a statistical error. Sports science
has no equivalent norm. Every Driveline-style facility, every college program with a
Trackman unit, runs the same loop: make a mechanical change, take 40 swings, look at the
number, decide. Forty swings resolves bat speed fine (rho = .9 at 50 PA) and resolves
essentially nothing about exit velocity, hard-hit rate or outcomes.

**The product is not a calculator. It is a norm.** Being the tool a coach runs before the
intervention is a different and much stickier position than being the tool that evaluates
it afterward -- and the first mode above gives you the shareable artifact that gets you in
the door.

## What to build next on it

1. A web version with two inputs and one number. Ten minutes of work on top of what exists.
2. **A design mode**: "I can get 200 swings. What is the smallest change I could detect?"
   That is the same formula solved for `delta` instead of `n`, and it is the question
   coaches actually ask.
3. Port the table to whatever tracked metrics a facility has that MLB does not -- force
   plate, motion capture. The reliability table for those does not exist anywhere public.
