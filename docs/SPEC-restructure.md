# Spec — restructure the dashboard around a player and a metric

**Status:** approved 2026-09-21, in progress. Written from user feedback. Resolved answers are
recorded in the table at the end; the published artifacts built from this source were deleted
the same day (Q9).

## The problem, in the user's words

> The dashboard is cluttered. There is a LOT going on… as is it scares the user off by being
> too dense.

Seven tabs, each a separate tool with its own controls, explainer and caveats. A reader has to
know which tool answers their question before they can ask it. The fix is to organise around
the two things a reader actually starts from — **a player**, or **a metric** — and let the
analyses become sections inside those.

---

## 1. Information architecture

### From seven tabs to three

| new tab | starts from | holds |
|---|---|---|
| **Player** | one player, one metric | everything about that player: his line, his rank, his changes, his streak, head to head |
| **Metric** | one metric | everything about that metric across the league: how reliable it is, how much data it needs, how well it predicts, who is moving on it |
| **Method** | — | the statistical addendum, rewritten (§4) |

**Q1.** The feedback says "three tabs" and names two. The third above is Method, which gives the
addendum a home in the navigation. The alternative is two tabs with the addendum as a link.

### Where every existing view goes

| existing tab | goes to | as |
|---|---|---|
| Player check | Player | the **header verdict** — the first thing shown for the selected player |
| Luck-adjusted rank | Player | **"How he ranks"** section |
| Real changes (his rows) | Player | **"What changed"** section |
| Real changes (league board) | Metric | **"Who moved"** section |
| Streak forecast (his row) | Player | **"Is he hot or cold"** section |
| Streak forecast (league board) | Metric | **"Who's hot or cold"** section |
| Head to head | Player | **"Compare to…"** section |
| Streak history | Metric | **"Do streaks last"** section |
| Sample-size planner | Metric | **"How much data is enough"** section |
| H2H scoring record | Metric | **"How well it predicts"** section |

Nothing is deleted. The league-wide boards are the one thing the feedback doesn't place; the
Metric tab is their natural home, since "who moved most on bat speed" is a question about a
metric. **Q2.**

### Deep links must not break

`/app/#p-card`, `#p-vs`, `#p-stretch`… are in the wild — shared links, the landing page, the
published artifacts. Map each old hash to its new tab and section, and scroll to it. A shared
link to `#p-vs` should open Player → Compare.

---

## 2. The Player tab

### Controls (one row, above everything)

`Player` · `Metric` · `Dates` · (Type and Season move here from the global bar)

The global bar exists because seven tabs each needed Type and Season. With the player chosen
first, Type follows from the player and Season is a property of the view. The strip goes.

### Sections, in order

1. **Header** — name, **current team, position**, season line (§2a), and Player check's one-line
   verdict: *"Hot, and it's mostly real"* / *"Hot, but mostly luck"*.
2. **How he ranks** — the shrunk percentile for the selected metric, large; all 16 behind
   "show every metric".
3. **What changed** — his real changes, the selected metric first.
4. **Is he hot or cold** — his streak status and expected persistence, **on wOBA**.
5. **Compare to…** — head to head with him fixed as Player A and a "compare to" picker for B,
   **on wOBA**.

**Sections 4 and 5 always show, whatever metric is selected.** They are about the player, not
the metric; they happen to be computed on wOBA. The metric selector drives sections 2 and 3
only. Each wOBA section says so in its heading — "Is he hot or cold? *(on wOBA)*" — so that
picking bat speed and seeing a wOBA streak is not a surprise. Hiding a section because the
selected metric doesn't support it happens on the **Metric tab only** (§5).

Each section: the answer, one line of interpretation, and a collapsed *"What this can't tell you"*.
Method prose stays in Method (D54).

### 2a. The surface-stats table (needs new data)

The feedback asks for "a full table of surface level stats, current team and positions."
**None of this is in the shards today.** They carry `pa, wn, xn, k, bb` and swing and batted-ball
counters, but no hits, extra-base hits, home runs or at-bats.

The database has everything needed:

| want | source column | how |
|---|---|---|
| H, 1B, 2B, 3B, HR, BB, IBB, HBP, SO, SF, SH, AB | `events` | count per block in the existing `blocks_all.py` pass |
| AVG, OBP, SLG, OPS, ISO | derived | from the counts above, for any window |
| G | `game_pk` | distinct games per block |
| current team | `home_team`, `away_team`, `inning_topbot` | the batting team in his most recent game |
| position | `fielder_2 … fielder_9` | the defensive slot he appears in most — see below |

**Recommendation: add these to the block aggregation**, not a separate file. Every window the
site already supports then gets a surface line for free.

**Cost.** A Mac job: `blocks_all.py` reads `~/snap.db`. About 13 new counters per block; the
2026 hitter shard is 583 KB at 24 fields, so expect roughly **+50%** on each shard. First paint
fetches one shard, so ~870 KB instead of ~583 KB. Acceptable; say so if not. **Q4.**

**Position has two options.**
- *Infer from the fielding slots* — the columns hold player ids, so a player's position is the
  slot he occupies most. Free, same pass. Weakness: a pure DH never fields, so he reads "DH",
  which is correct but by inference.
- *MLB StatsAPI `/people`* — authoritative, including primary position and age. Needs a fetch
  script like `fetch_history.py`, Mac only.

Recommend inference now, StatsAPI later. **Q5.**

**Q6.** The feedback's sentence *"If this needs to be downloaded scope it in and…"* is cut off.
Read here as "scope what a download would take" — the section above.

---

## 3. The Metric tab

### Controls

`Metric` · `Type` · `Season`

### Sections

1. **How reliable it is** — the reliability curve with its bootstrapped interval (D53), in plain
   words: *"Bat speed is 70% skill after 13 plate appearances. wOBA takes 525."*
2. **How much data is enough** — today's planner: detect a change of size X.
3. **Who moved** — the league board of real changes on this metric.
4. **Who's hot or cold** — *wOBA only today.*
5. **Do streaks last** — today's Streak history. *wOBA only.*
6. **How well it predicts** — the H2H scoring record and the naive-rule comparison (D58).
   *wOBA only.*
7. **League distribution** — *new, cheap*: a histogram of the metric this season, the selected
   player marked if one is chosen on the Player tab.

### Naming the planner

"Sample-size planner" should become something that states what it does. Candidates:

| name | for | against |
|---|---|---|
| **Power analysis** | the exact term for its detection mode | jargon to a non-stats reader; doesn't cover reliability mode |
| **Skillset reliability analysis** | covers reliability mode | long; "skillset" is doing little |
| **How much data is enough** | plain, says the question | not a noun |
| **Reliability & power** | covers both modes, honest | still two terms of art |

Recommend **"How much data is enough"** as the section title, with "reliability and power analysis"
in its first line for the reader who knows the term. **Q7.**

---

## 4. The Method tab (the addendum, rewritten)

The feedback: much higher level, readable by a non-baseball audience; headlines that are
one-sentence theses; drop "What was wrong once"; move analysis-specific caveats to their
analyses.

### Headlines become the takeaway

| now | proposed |
|---|---|
| A property of the column, not of the player's number. | **"% real" says how much of a stat is skill across all players — not how accurate one player's number is.** |
| The number that does the shrinking has its own error bar. | **We know almost exactly how trustworthy swing speed is; we know how trustworthy batting results are only roughly.** |
| "Is it noise?" and "is it big?" are different questions. | **A change can be real and still too small to matter, so every change is judged on both.** |
| 1.0 is not the benchmark; 0.264 is. | **Next month's results are mostly luck, so even a perfect forecaster would be wrong most of the time.** |
| An ordering, because a projection is not supportable. | **Predicting a player's exact numbers barely beats guessing, so we only predict which of two players does better.** |
| 2026 is no longer a clean test year. | **We have looked at 2026 too often to treat it as a fair test, so its results are shown but not trusted.** |
| What was wrong once, and is fixed now. | *removed* |

### Written for someone who doesn't follow baseball

- Define wOBA once, in a sentence: *a single number for how much a hitter contributes per plate
  appearance, weighting a home run more than a single.*
- No σ², Φ, Spearman–Brown or Brier in the running text. Formulas go in a collapsed "the maths"
  block per section, and the full treatment already exists in `report.html`.
- Each section: the thesis headline, two or three plain sentences, one example with a real
  player, then the collapsed maths.

### Analysis-specific caveats move out

This partly reverses D54, which moved method **out** of the tabs into the addendum. The two fit
together if the line is drawn by length:
- **A caveat that changes how you read one answer** goes in that section, collapsed — e.g. "over
  two weeks this has no demonstrable skill" belongs under Compare, not in Method.
- **Method that explains how an analysis works** stays in Method, **bucketed by analysis** with
  an anchor each, so a section can link to "how this is worked out".

The corrections section goes. Its content isn't lost: DECISIONS.md and FINDINGS.md hold the
full record, and `report.html` covers it for a technical reader.

---

## 5. What the metric selector can and can't do today

The biggest scoping question. The Player and Metric tabs both let you pick a metric, but four
analyses exist **for wOBA only**:

| analysis | metrics |
|---|---|
| how he ranks / how reliable it is / how much data is enough | all 16 |
| what changed / who moved | **9 inputs** (swing and approach) — **not** wOBA, xwOBA, launch angle, barrel%, sweet-spot%, ground-ball%, attack direction |
| is he hot or cold / who's hot or cold | wOBA |
| compare to (head to head) | wOBA |
| do streaks last | wOBA |
| how well it predicts | wOBA |

**On the Player tab these always show** (§2) — the metric selector does not gate them.

*Correction, found while building:* the change log tracks nine **input** metrics, deliberately —
its purpose is to separate a real change in how a player swings from a move in his noisy
results — so wOBA is never one of them. wOBA and the change analyses therefore never overlap. On
the Player tab "What changed" shows **all** of his changes with the selected metric first; on the
Metric tab "Who moved" is gated to the input metrics, exactly as the wOBA sections are gated to
wOBA.

**On the Metric tab, show the wOBA-only sections only when the selected metric has them, with
one line saying so** ("Streak and matchup analysis use wOBA, the all-in-one results measure").
Do **not** extend them to every metric:

- For the swing metrics it isn't worth it. Bat speed is 97% skill at a half-season, so "which of
  two hitters has the higher bat speed next month" is near-certain and uninteresting. Head to
  head is informative precisely *because* outcomes are noisy.
- For the outcome metrics it's a real modelling job. Each needs its own per-PA variance, drift
  and prior-season levels, and `history.json` holds only wOBA and xwOBA.

The cheap, worthwhile extension is **xwOBA, K%, BB%** — outcome-like, noisy, and in the case of
xwOBA already in `history.json`. Phase 4. **Q3.**

---

## 6. Landing page

| element | now | proposed |
|---|---|---|
| headline | Tell a real change from a lucky streak. | **Really understand MLB player performance.** |
| subtitle | *(long lede)* | **Decompose a player's statistics into sustainable changes, hot streaks, and luck.** |
| button | Open the dashboard → | **Enter →** |
| "check one player" search | present | **removed** |
| section heading | Each one answers a single question. | **Each tool probes deeper into an MLB player's output.** |

Tool questions, with one change — **"player X"** reads as a template placeholder on a page where
no player is selected, so **"a player"**:

| now | proposed |
|---|---|
| Where did he really rank over these dates? | How did a player's output compare with his peers', and is it real? |
| Did he actually change something? | How did a player's underlying skills change, and are the changes real or fluky? |
| How much of a hot streak should I keep? | Is a player on a hot or cold streak — and how much of it is signal, not noise? |
| How long until a number means anything? | How long until past performance predicts future performance? |
| Which of these two is better from here? | Head-to-head matchups between two players. |

**On the two open copy lines.** "Really understand MLB player performance" is warm but "really"
hedges; alternatives: *"See what's real in MLB player performance"* — keeps the site's name
in the headline — or *"MLB player performance, separated from luck."* The subtitle is strong as
written; the only suggestion is "sustainable changes" → "lasting changes", which reads more
plainly. **Q8.**

**Consequence.** Under the new structure these five are *sections*, not tabs, so each card's
button should deep-link into Player or Metric at that section. And the search being removed was
the only way into Player check from the landing page — "Enter →" now does that job.

---

## 7. Other consequences

- **The published artifacts.** `mkdash.py` and `mkmock.py` build from the same `body.html`, so a
  restructure changes both published artifacts too. Rebuild them to match, or freeze them at the
  current version. **Q9.**
- **The summary component** has one builder per view (seven). It becomes one per section, mounted
  where the reader is. The evidence-packet design (D-series) is unchanged.
- **Decisions this supersedes:** D47's per-tab question line (becomes per-section), D48's global
  bar (goes), D57's tab names (become section names), and part of D54 (§4). Each gets a D-entry
  saying so when it's built.

---

## 8. Phasing

| phase | what | data work | risk |
|---|---|---|---|
| **1** | landing copy; remove the search; rename the planner; Method headlines as theses; drop corrections | none | low — copy |
| **2** | Player / Metric / Method; move every section in; "compare to" on Player; league boards to Metric; old-hash redirects | none — existing data | medium — every view moves |
| **3** | surface stats, team, position | `blocks_all.py` on the Mac; shards ~+50% | medium — pipeline |
| **4** | extend streak and matchup analyses to xwOBA, K%, BB% | per-metric variance and drift | high — modelling, and S33 applies |

Phase 1 can ship on its own and relieves the density complaint on the pages people see first.
Phase 2 is the real restructure and should land in one piece — half-migrated, the site would have
both navigations at once.

---

## Open questions

| | question | proposed default |
|---|---|---|
| **Q1** | Two tabs or three? | Three: Player · Metric · Method |
| **Q2** | Where do the league-wide boards go? | Metric tab |
| **Q3** | Metric selector on a wOBA-only analysis: hide, or extend? | Hide with a note; extend only xwOBA / K% / BB%, in phase 4 |
| **Q4** | Is ~+50% on shard size acceptable? | Yes |
| **Q5** | Position by inference or StatsAPI? | Inference now |
| **Q6** | The cut-off sentence about downloads | Read as "scope it" — §2a |
| **Q7** | Planner's new name | "How much data is enough" |
| **Q8** | Headline and subtitle | As given, or one of the alternatives in §6 |
| **Q9** | Rebuild the published artifacts or freeze them? | Rebuild |

### Resolved 2026-09-21

| | answer |
|---|---|
| Q1 | Three tabs — Player · Metric · Method (left to Claude) |
| Q2 | League-wide boards go in Metric |
| Q6 | Read correctly: scope what a download takes |
| Q9 | Delete. Stretch Finder and Stretch Finder Deployed were deleted; `mkdash.py`, `mkmock.py` and `site/profiles.json` removed; the panel CSS `mksite.py` read out of `mkmock.py` moved into `mksite.py` itself, output byte-identical |
| — | Clarified: on the Player tab the wOBA-only sections always show for the selected player; metric-gating applies to the Metric tab only |
| Q3–Q5, Q7, Q8 | Proposed defaults stand unless revisited |
