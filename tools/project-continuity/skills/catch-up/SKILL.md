---
name: catch-up
description: Report where a project stands at the start of a session - state, recent decisions, the last session log, uncommitted work and unpushed commits. Use when opening a project after time away, when switching between Claude Code and Cowork, or when the user says catch me up, where were we, what is the state of this project, or what was I doing.
argument-hint: "[optional: a topic to focus on]"
allowed-tools: Bash(git *), Bash(ls *), Bash(cat *), Bash(head *), Bash(tail *), Read, Glob, Grep
---

Establish where this project stands before doing anything else. Report; do not
start work, and do not offer to fix what you find unless asked.

## Gather

Run these against the repo root. Skip silently what does not exist.

1. `git status --short --branch` and `git log --oneline @{u}..HEAD 2>/dev/null | wc -l`
   for unpushed commits. `git log --oneline -8` for recent history.
2. Read, if present: `CLAUDE.md`, `HANDOFF.md`, `README.md`. These carry **state**.
3. Read the tail of `DECISIONS.md` (last 3 entries) and `FINDINGS.md`. These carry
   **reasoning** - why things are the way they are and what was rejected.
4. Read the most recent file in `docs/log/`. This carries **narrative** - what was
   tried, including dead ends.
5. Read today's and yesterday's `.claude/breadcrumbs/*.tsv` if present. These are
   raw facts recorded automatically after each turn; use them to see what happened
   in a session that was never written up.
6. Note any gap: if the newest `docs/log/` entry is older than the newest commit,
   work has happened that was never written down. Say so.

If the user gave an argument, also grep `DECISIONS.md`, `FINDINGS.md` and
`docs/log/` for it and report what was already tried.

## Report

Under 250 words unless asked for more. In this order:

- **Where it stands** - one paragraph. Branch, unpushed count, working tree clean
  or not, what the last session was doing.
- **Live threads** - what the handoff or log names as next, as a short list.
- **Recent decisions** - only ones that constrain what happens next, with their D
  numbers.
- **Unwritten work**, if the gap in step 6 exists - name the commits that have no
  log entry and say that `/log-session` would close it.

Never invent a next step that no file names. If the project's own records do not
say what comes next, say that plainly - that absence is itself the finding.
