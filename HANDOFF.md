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
