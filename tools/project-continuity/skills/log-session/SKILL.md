---
name: log-session
description: Write this session into the project's permanent record - append a dated entry to docs/log/, add any new entries to DECISIONS.md, and refresh HANDOFF.md. Use at the end of a working session, before switching machines or surfaces, or when the user says log this session, write up what we did, update the decisions, or close out.
argument-hint: "[optional: a headline for the entry]"
allowed-tools: Bash(git *), Bash(date *), Bash(ls *), Bash(cat *), Read, Write, Edit, Glob, Grep
---

Turn this session into something a future session - or a different surface - can
use. Three files, in this order. Write from evidence, never from memory alone.

## 1. Gather evidence first

- `.claude/breadcrumbs/$(date +%F).tsv` - the deterministic trail: commits made,
  files touched, working-tree stats, recorded automatically after each turn. Read
  it before writing anything. It is the record of what happened; your recollection
  is the record of what you meant.
- `git log --oneline` since the first commit in the trail, and `git status --short`.
- The existing `docs/log/` entries - match their voice and structure exactly rather
  than imposing a new format.

## 2. Append to `docs/log/YYYY-MM-DD.md`

Create it if absent; append if the day already has one. Cover:

- **What got built** - files and what they do, one line each.
- **What was found** - results, with numbers. Link to `FINDINGS.md` rather than
  duplicating it.
- **Dead ends and wrong turns** - the section that earns the file. Record what was
  tried and rejected *and why*, including things that merely did not work. The
  expensive mistake is redoing work you already rejected and no longer remember
  rejecting.
- **Left undone** - anything abandoned mid-flight.

Write it to be grepped, not read whole. Say so in the file if it is new.

## 3. Append to `DECISIONS.md`

Only for choices that constrain future work. Follow the existing entry format
exactly - typically the decision, *what it was chosen over*, and *what would make
it wrong*. Number continuing from the last entry. Supersede rather than delete.

A preference is not a decision. If nothing this session constrains the future,
add nothing and say so.

## 4. Refresh `HANDOFF.md` or `CLAUDE.md`

Update only what is now false: current branch state, next steps, anything the
session invalidated. Do not append a changelog - this file is state, and state is
overwritten, not accumulated.

## 5. Report

Name each file touched and, in one line each, what was added. Then state the
unpushed commit count and stop. Do not push; the user pushes.
