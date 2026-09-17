# project-continuity

Carries a project across sessions, and across Claude Code and Cowork.

There is no first-party sync between the two surfaces — no shared transcripts,
no shared memory, no shared task list, and Cowork does not read `CLAUDE.md` from
a connected folder on its own. **The git repo is the only shared substrate, and
plugins are the only shared behaviour.** This plugin is the bridge: install it in
both and they speak the same language about the same files.

## What it does

A project records three different things, and only two of them survive on their own:

| | lives in | survives a gap? |
|---|---|---|
| **State** — what exists, what is next | `CLAUDE.md`, `HANDOFF.md` | yes |
| **Reasoning** — why, and what was rejected | `DECISIONS.md` | yes, if written when decided |
| **Narrative** — what was tried, in order | `docs/log/YYYY-MM-DD.md` | only if deliberately logged |

The third is the one that lapses. This plugin makes recording it cheap.

### `/catch-up`
Reads the repo's own records — git state, `HANDOFF.md`, the tail of `DECISIONS.md`,
the latest `docs/log/` entry, today's breadcrumbs — and reports where things stand
in under 250 words. Run it when opening a project after time away or when moving
between surfaces. It also flags the gap that matters: commits newer than the
newest log entry, i.e. work nobody wrote down.

### `/log-session`
Writes the session into the permanent record: appends to `docs/log/`, adds any new
`DECISIONS.md` entries, refreshes `HANDOFF.md`. It reads the breadcrumb trail first,
so it writes from evidence rather than recollection. It never pushes.

### The breadcrumb hook
After every turn, a `Stop` hook appends deterministic facts to
`.claude/breadcrumbs/YYYY-MM-DD.tsv` — commits made, files touched, diff stats,
branch. It is deliberately stupid: it records what a machine can know for certain
and never says why.

That split is the design. Journal and ledger: the journal is chronological, dumb
and complete; the ledger is organised and interpreted. You can always rebuild the
ledger from the journal, never the reverse. The hook keeps the journal so that
`/log-session` has something true to work from hours later.

```
17:05  data-integrity  commit   d144f24 Say in HANDOFF.md what the repo carries
17:31  data-integrity  working  3 files changed, 214 insertions(+), 61 deletions(-)
17:31  data-integrity  touched  site/summary.js web/app.js web/serve.py
```

The trail is local scratch, gitignored inside its own directory, and never
committed. The hook is silent, exits zero even on failure, and does nothing at all
when a turn changed nothing.

## Install

**Claude Code** — `/plugin install` from your marketplace, or point it at this
directory. The hook activates for any git repo you work in.

**Cowork** — Customize → Plugins → install the `.plugin` file. Skills work the
same; hooks run only for plugin-installed hooks, which is what this is.

## Conventions it assumes

- `docs/log/YYYY-MM-DD.md` for session narrative; existing entries set the voice.
- `DECISIONS.md` entries record the decision, what it was chosen over, and what
  would make it wrong.
- Claude drafts commits; the user reviews and pushes. Neither skill pushes.

None are required — both skills skip gracefully what does not exist.
