# Handoff — current state and next steps

Written 2026-09-17, at the end of a Cowork session, for picking the work back up
in Claude Code. Branch: `data-integrity`, **7 commits ahead of origin and
unpushed**. Review the diff and push when you are happy with it.

---

## The one thing that was broken and is now fixed

Until this commit, **the source that generates the website lived only inside an
ephemeral cloud container.** `web/` was committed, but `web/index.html`,
`web/app.js` and `web/styles.css` are *build artifacts* — the files that produce
them were not in the repo at all. If that container had been reclaimed, the only
way to change the site would have been hand-editing generated output.

Those sources are now in `site/`. Treat `site/` as the truth and `web/` as
output. Do not hand-edit anything in `web/` except `serve.py`, `stored_summaries.json`
and `data/` — everything else there is overwritten on the next build.

---

## Layout

```
site/                  SOURCE for the website  <- edit here
  head.html            <title>, font links, the whole stylesheet (tokens first)
  body.html            markup + client JS for all four tabs, shared by all builds
  summary.js           the LLM summary component, shared by the site and the mockup
  mkdash.py            -> stretch_finder.html   (artifact: all 4 seasons, no LLM)
  mkmock.py            -> mockup.html           (artifact: 2026 only, stored LLM)
  mksite.py            -> web/                  (the deployable site, live LLM)
  stored_summaries.json  one canned response per view, used when no API key is set
  profiles.json        four stored player profiles (legacy, still read by mkmock)

web/                   BUILD OUTPUT + the server-side pieces
  index.html           landing page          (generated)
  app/index.html       the tool              (generated)
  styles.css  app.js   (generated)
  lib/packet.js        (generated) evidence-packet builder, shared browser+server
  api/summary.js       (generated) Vercel function; holds ANTHROPIC_API_KEY
  prompts/*.md         (generated) base.md + one per view
  serve.py             hand-maintained zero-dependency local server
  stored_summaries.json  copy of site/stored_summaries.json, read by serve.py
  data/*.json          the shards — gitignored, produced by blocks_all.py
  vercel.json          (generated)
```

### Build and run

```bash
python3 site/mksite.py          # writes web/  (reads site/head.html, body.html, summary.js)
cd web && python3 serve.py      # http://localhost:8787   (no npm, no account)
```

`mkdash.py` and `mkmock.py` read the pipeline's JSON from `output/` by default;
override with `STATCAST_OUT=/some/path`. `mksite.py` does **not** copy the data
shards — `web/data/` is populated by `blocks_all.py` and is gitignored, so after
a fresh clone run the pipeline before expecting the site to show anything.

---

## What changed this session

**1. The masthead nav was dead.** Its links were fragment hrefs pointing at tab
panels, and a panel that is not open carries `[hidden]`, which is not a scroll
target — so all three did nothing. They now drive the tab they name, the tab
strip writes the matching hash, and both controls repaint from one
`window.onTabShow` callback. `/app/#p-carry` deep-links.

**2. Every dynamically filled `<select>` now ships a default option** in the
static markup. `#c-metric` was the visible case: the change log renders lazily,
so its Metric box sat empty until the tab was first opened.

**3. A CSS leak.** `head.html` styled the article column with bare `header{}` and
`footer{}` element selectors, which also matched the deployed site's
`<header class="mast">` and `<footer class="site-foot">`. The footer inherited
`max-width:86ch` and collapsed into a 629px column pinned to the left edge of a
full-bleed card. Both rules are now scoped to `.wrap > `.

**4. A landing page,** and the tool moved to `/app/`. The landing page's worked
example is real output — Bregman, Jul 16 – Sep 15 2026, rendered with the tool's
own `.row` component so the demo cannot drift from what it demonstrates.

**5. An editorial type pass.** Everything had been 13–13.5px at an 82ch measure.
There is now a type scale in tokens, prose at 14.5/1.65 capped at 68ch, and IBM
Plex Serif for display only. The "what this view is for" blocks became
`<details>` — on the Percentiles tab the bars moved from y=863 to y=578.

**6. The summary component was generalized** from one player-profile panel to one
component that reads whichever view is open. See below.

**7. A statistical bug.** With `confirmed only` checked, the change-log board note
reported the hold rate of rows the filter had *selected* on `held >= 0.5` — so it
could only ever say 100%. It now says so and reports the unfiltered rate instead.

---

## The summary component

`site/summary.js`. One node that moves into whichever panel is open, so there is
one state machine and one set of ids rather than four of each.

- `BUILD["p-stretch" | "p-changes" | "p-carry" | "p-planner"]` each read
  `VIEWSTATE`, which the four renderers in `body.html` populate, and return
  `{view, title, sub, note, cols, rows, context}`.
- `cols`/`rows` are **the same array** that renders the audit table and that gets
  posted. That identity is the whole design: if the prose says something the
  table does not support, it is one click to see.
- Transport is per build. `mksite.py` posts to `/api/summary`; `mkmock.py`
  resolves from an inlined object after a 900ms delay so the loading states are
  exercised. Everything above the transport is shared.
- No key set → `serve.py` returns the stored response for that view and the meter
  labels it in orange. Key set → the same component goes live with no code change.
- Prompts are two blocks: `web/prompts/base.md` is byte-identical on every call so
  it caches at 0.1×, and a small per-view block sits after the breakpoint.

### Gotchas that cost time, so you do not repeat them

- `show()` must dispatch `tabshow` **after** the renderer runs, not before —
  listeners read `VIEWSTATE` and the renderer is what writes it.
- In a change-log row, `o.f` **is** the metric object (`o.f.f` is its formatter),
  and the window is `sh(BL[o.a])`, not `lbl(o.a)`.
- `packet.span.from` is a block *value*, not an index — do not put it through `BL[]`.
- The boot mount uses `TABS[active][1]`, not a hard-coded panel, or a deep link
  leaves the component inside a hidden panel.
- `repeat(auto-fit, minmax(400px, 1fr))` honours the min track even when it
  exceeds the container. Use `minmax(min(400px,100%),1fr)`.

---

## Next steps, roughly in order

1. **Push the branch.** Seven commits are sitting unpushed.
2. **Set `ANTHROPIC_API_KEY` and exercise the live path.** Every summary so far
   has come from the stored fallback. The four stored responses in
   `site/stored_summaries.json` were written by hand against real output; compare
   live generations against them and tighten `web/prompts/*.md` where the model
   drifts. Watch specifically for the failure the guardrails exist to prevent:
   narrating the largest number instead of the most defensible one.
3. **Deploy.** Vercel Hobby is free and sufficient (100 GB transfer, 1M edge
   requests, 1M invocations) but is non-commercial-only; Pro is $20/dev/month.
   `vercel env add ANTHROPIC_API_KEY` for Production and Preview.
4. **`site/` and `web/` duplicate `stored_summaries.json`.** Make `mksite.py` copy
   it rather than keeping two.
5. **The carry board's window is "last two blocks",** so it ranges 16–30 days
   rather than a rolling 30. Worth making honest.

### Longer-standing debts, unchanged this session

- The Steamer/ZiPS benchmark is blocked on a manual FanGraphs pre-season CSV
  export (`type=steamer`, **not** `steameru`).
- The `woba_value` correction was never propagated to the Marcel conclusions (T13).
- Survivorship bias (T3) has never been quantified.
- The wOBA−xwOBA gap is replicated and still unexplained after its proposed
  mechanism was retracted. `PREREGISTRATION.md` seals P6–P10 for 2027, including
  P8 — that M2's R² will come in *below* its 2026 figure of 0.0335.

---

## Conventions

- Claude drafts commits on a branch; **you** review the diff and push. Never
  commit to `main`.
- Project knowledge belongs in repo files — `CLAUDE.md`, `DECISIONS.md`,
  `FINDINGS.md` — not in chat transcripts. `DECISIONS.md` is at D1–D28.
- Negative results get recorded, not buried. D27 (input corroboration adds
  nothing at 15/30/45-day resolution) and D28 (2026 is no longer a clean holdout)
  are both load-bearing.

---

## Circling back to Cowork

The repo carries **state** and **reasoning** perfectly well; it does not carry
**narrative** unless someone writes it down on purpose. Three different things,
and only the first two survive on their own:

| | where it lives | survives a surface switch? |
|---|---|---|
| State — what exists, what is next | `CLAUDE.md`, this file | yes, automatically |
| Reasoning — why, and what was rejected | `DECISIONS.md` (D1–D29) | yes, if written when decided |
| Narrative — what was tried, in order | `docs/log/YYYY-MM-DD.md` | **only if deliberately logged** |

`docs/log/2026-09-10.md` sets the convention and states its own purpose well:
*"grep it when you wonder whether something was already tried. Dead ends are
recorded on purpose."* It is also the only entry, and a week of work has landed
since. That gap, not the choice of surface, is what actually loses information.

Cowork picks all of this up automatically — the device bridge reads the repo and
the standing instruction points at it — so the Claude Code → Cowork direction
costs nothing. The direction that loses things is any work, on either surface,
that never got written down.

### Published artifacts

These live in the artifact gallery, **not** in the repo, and are the one thing a
markdown file cannot reconstruct. Republish by passing the URL, or a new artifact
is created instead of updating these:

| Artifact | URL | Built by |
|---|---|---|
| Stretch Finder (all 4 seasons, no LLM) | `https://claude.ai/artifact/XCNUG7vYNNjXTcFHFGiFJj` | `site/mkdash.py` |
| Stretch Finder Deployed (2026, stored LLM) | `https://claude.ai/artifact/BboGZRVZgsys4CNVUwtjyN` | `site/mkmock.py` |
| Signal, Noise and the Luck Gap | `https://claude.ai/artifact/FVTe6toG51kSLM6Bgs5Etb` | `STATISTICAL_PROGRAM.md` |

### Keeping the log fed

Make it a trigger rather than a resolution. At the end of a working session, in
either surface:

> Append today's session to `docs/log/<today>.md` following the convention in
> `docs/log/2026-09-10.md` — what got built, what was found, and especially the
> dead ends. Then add any new entries to `DECISIONS.md`.

The `project-log` skill does this and is available on both surfaces. In Claude
Code it can also be a slash command in `.claude/commands/`, which is the version
most likely to actually get run.

Claude Code keeps its own full transcripts as JSONL under `~/.claude/projects/`,
and `claude --resume` reopens one with context intact — so raw history is not
lost there, it is just greppable rather than browsable. The session log is what
turns it into something a person, or a future session, will actually read.

**2026-09-20: the product was renamed from "Stretch Finder" to "True Talent" (D43).** The two
artifact rows above keep their original titles, because that is what those artifacts are called.
The repo directory and the Vercel project are still `statcast-dashboard` by design.

---

## 2026-09-20 (later): `site/` rebuilt from `web/`

The drift described above had recurred, in the opposite direction and larger. `site/` is now the
truth again and `python3 site/mksite.py` reproduces the deployed tree byte-for-byte. Full
reasoning in **D45**; the operating rule and the verification command are now in `CLAUDE.md`.

What changed in the repo: `site/body.html`, `site/head.html`, `site/summary.js`, `site/mkmock.py`
and `site/mksite.py` were reconstructed from `web/`. No file in `web/` changed except
`addendum.html`, which is now generated from the shared chrome instead of existing only as
hand-made output (it gains one HTML comment, three blank lines and `aria-current` on its own nav
link; rendered text is identical).

Three latent bugs fixed on the way: `mksite.py` resolved its inputs against the caller's cwd, so
the documented build command could not run; the build overwrote the real `web/og.png` with a 1×1
placeholder; and the sixteen `str.replace` anchors that assemble `app.js` had no assertion behind
them, so a stale one would have dropped a feature silently.

**Next, and the reason the back-port was done first:** a head-to-head view — *which of these two
players will be better over the next N weeks* — reported as a calibrated probability rather than
a projected line, with the uncertainty split into talent / drift / sampling. Plus the pairwise
"how many PA until you could tell them apart" answer from the planner's own machinery, and a
calibration curve built by backtesting the estimator over 2023–2025.

### 2026-09-20 (later still): clarity and rigour pass

Five changes, in the order they were asked for — D47, D48, D49 carry the reasoning.

1. **A plain question under the title on every tab**, reusing the landing page's own wording.
2. **Head to head now defines its claim** ("finishes the next month with the higher wOBA of the
   two"), labels every number, and glosses Brier once.
3. **The global Type/Season control is a status strip**, not a fourth identical card — and it now
   actually disables itself on Breakouts, which had been claiming in a footnote that it didn't
   apply while staying fully live.
4. **Head to head shows how each estimate was reached**: this season vs usual level, with the
   weight each supplied drawn as a bar. Plus a landing-page card for the tab, which it had been
   missing, and an inline flag when a player's prior history is thin.
5. **A fixed three-slot explainer on all seven tabs** — what this answers / how to read it / what
   it can't tell you. Existing prose was re-bucketed; the limits sections are mostly new.

Verified: the build is idempotent, all three pages parse with zero unclosed tags, `app.js`,
`evidence.js` and `api/summary.js` all parse, and both artifact builds produce seven tabs.
**Still not seen in a browser** — the Chrome extension would not connect in either session, so
every check here is structural. A visual pass is the first thing to do next.

Known gaps: `stored_summaries.json` still has no `vs` entry (nor `card`/`breakouts`), so the
no-API-key path shows a clear error on those three tabs. Marcel is still not among the forecasters
`matchup.py` scores.

### 2026-09-20 (browser pass): nine fixes that only a real render could find

Everything to this point had been verified structurally — the build was idempotent, the HTML
parsed with no unclosed tags, the JS parsed, and the maths was replicated in Python. All of that
was true, and the tab was still visibly broken in ways none of it could see.

1. **`history.json` race.** The LOADER repainted only the Player check tab by index when prior
   seasons landed, so Head to head — which cannot produce an estimate at all without them —
   rendered first and stayed stuck on "no prior-season baseline". It now repaints whichever tab
   is open. *The user spotted this one on the first screenshot.*
2. **The warning didn't distinguish "still loading" from "this player has no history"**, sending
   a reader after missing data that was merely in flight.
3. **The warn bar was never cleared on the success path**, so a resolved warning sat above a
   perfectly good answer.
4. **`.warnbar:empty` still painted** its background and left border — a coloured stripe under
   the headline whenever a warning was cleared.
5. **The calibration table had been silently deleted.** An earlier edit replaced a span of
   `renderVsCal` that happened to contain the whole table-building block. The note below it still
   rendered, so every structural check passed and the tab simply had no table.
6. **`&sub1;` is not an HTML entity** — the drift formula printed `2σ&sub1;²t` on screen.
7. **The highlighted calibration row** drew its accent on every `td`, striping the table.
8. **The "386 qualified hitters" note** stayed visible on Breakouts, where Type and Season don't
   apply.
9. **`serve.py` let the browser cache `app.js`.** Three separate times a rebuilt file looked like
   a change that hadn't worked. It now sends `no-store` for everything except `/data/`.

Number 5 is the one worth remembering: **a parse check cannot tell you that a feature is missing,
only that what remains is well-formed.** The others were cosmetic or a race; that one would have
shipped a headline feature with its evidence table quietly absent.

Confirmed working in Chrome afterwards: all seven tabs and their questions; the global bar
disabling itself on Breakouts and re-enabling on exit; the as-of selector driving the estimate;
the outcome reveal firing on an elapsed window (Bregman 61% over Crow-Armstrong on 30 May,
scored wrong — Crow-Armstrong hit .513 to .303); the calibration table following the horizon
(15/30/60/90 days, different n and Brier each); the self-check warning appearing at the 15-day
horizon and nowhere else; and pitchers switching correctly to "lower wOBA allowed" and
"batters faced".

**Not verified: responsive layout.** The extension's viewport stays 1280px wide whatever the
window is resized to, so phone width is still unchecked. `.pests` uses the
`minmax(min(300px,100%),1fr)` guard from the gotchas list, but `.pest-row`'s five-column grid
(`5.6em 3.4em 1fr 64px 2.6em`) is the thing most likely to be cramped and nobody has looked at it.

## 2026-09-21: restructure into Player / Metric / Method (D58–D61)

- Seven tabs became two, plus a Method page (D60, spec in `docs/SPEC-restructure.md`). The Player
  tab holds, in order: Season line, The verdict, How he ranks, What changed, and Compare to…. The
  Metric tab holds: planner, Who moved, hot/cold, carry, breakouts, and head-to-head scoring.
  wOBA-only sections always show on the Player tab. On the Metric tab they fold away when another
  metric is picked.
- Surface stats, team and position are new shard fields (D61). `blocks_all.py` now runs on the Mac
  and publishes to `web/data/`. It had failed on every scheduled run until now (FINDINGS 2026-09-21).
- The head-to-head is now scored against naive slice baselines (D58).
- `mkdash.py`, `mkmock.py` and `profiles.json` are deleted (D59).
- **Unchecked:** phone width for the Season line (it scrolls inside `.tw`), the pitcher-only
  columns, and the first scheduled refresh with the fixed `blocks_all.py`. Check that tomorrow's
  `logs/refresh.log` SUMMARY no longer says `FAILED: blocks`.
- Phase 4 of the spec (extending streaks and head-to-head beyond wOBA) has not started.
- Nothing is committed.

### 2026-09-21 (later): analyses, not metrics (D62)

Both tabs now pick one analysis at a time from a pill row, with no global Metric picker. The second
tab is called **League**. The hash names the open analysis. I checked in Chrome: every analysis
on both tabs renders without errors, deep links work on a fresh load and on a hash change
(`#p-break`, `#p-carry`, `#p-card?k=pit&id=…`), the hot/cold click opens the player, the planner
and Who moved pickers work, and a type switch keeps the chosen analysis. Still unchecked: phone
width for the pill row, which wraps.

### 2026-09-21 (walk-through): Season line across seasons, eight UI fixes (D63)

New file `lines.py`, run by `blocks_all.py`, writes `web/data/lines-{bat,pit}.json`. All eight
fixes were checked in Chrome at 1280px. Phone width is still unchecked, because the browser window
does not resize from this environment. At phone width the Season line table (up to 16 columns)
scrolls sideways inside its `.tw` box, which is the thing most worth looking at.

### 2026-09-21 (latest): D68
- New script `fetch_careers.py`; it needs network and is in the pipeline.
- `serve.py` pricing changed. Restart the dev server for it to take effect.
- The carry board's wide table scrolls sideways inside its box when "what happened" is shown.
- Open: rebuild `history.json` from 2015 (`fetch_history.py`, which writes the DB, so do it on the
  Mac) to test whether Marcel's tie with the estimator comes from its longer history.

### 2026-09-23: presentable-project pass (D77, D78)

- `analysis/` holds 39 one-off studies; the root now has 23 scripts, all of which run daily or are
  imported by something that does.
- `tests/test_build.py` + `.github/workflows/tests.yml`: the build checks run in CI on every push.
  `tests/test_facts.py` still needs the local database and is not in CI.
- League tab opens on Hot & cold, which now has an AI summary (`hotcold` view).
- Phone width checked at 390px: nothing overflows; wide tables have scroll shadows.
- README rewritten with screenshots in `docs/img/`.
- **Unpushed at the end of the session**, so the CI badge has never rendered and the workflow has
  never run. Push to see it go green.
