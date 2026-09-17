#!/usr/bin/env bash
# Append deterministic facts about what changed during this turn.
#
# This script is deliberately stupid. It records what a machine can know for
# certain -- commits, file stats, branch -- and never tries to say why anything
# happened. The narrative is written later, by the model, from this trail.
# Journal and ledger: you can always rebuild the ledger from the journal, and
# never the other way round.
#
# Contract: silent on stdout (a Stop hook's output can land in context), never
# non-zero (a failing hook should never cost someone their turn), and no work at
# all when nothing changed.

set -u
exec 3>&1 1>/dev/null 2>&1          # everything below is silent by construction
cat >/dev/null                      # drain the hook's JSON payload; we do not need it

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 0

DIR="$ROOT/.claude/breadcrumbs"
STATE="$DIR/.state"
LOG="$DIR/$(date +%F).tsv"
mkdir -p "$DIR" || exit 0
# The trail is local scratch, not project history. Ignoring it inside its own
# directory keeps it out of git without touching the project's .gitignore --
# and closes the self-reference bug where the hook records its own writes.
[ -f "$DIR/.gitignore" ] || printf '*\n' >"$DIR/.gitignore"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-')"
HEAD_NOW="$(git rev-parse --short HEAD 2>/dev/null || echo '-')"

# A fingerprint of the working tree: same fingerprint means this turn changed
# nothing on disk, so there is nothing worth recording.
DIRTY="$(git status --porcelain=v1 2>/dev/null | sort | cksum | cut -d' ' -f1)"
FP="$HEAD_NOW:$DIRTY"

HEAD_WAS="-"; FP_WAS=""
if [ -f "$STATE" ]; then
  HEAD_WAS="$(sed -n 1p "$STATE")"
  FP_WAS="$(sed -n 2p "$STATE")"
fi
[ "$FP" = "$FP_WAS" ] && exit 0

TS="$(date +%H:%M)"
say() { printf '%s\t%s\t%s\t%s\n' "$TS" "$BRANCH" "$1" "$2" >>"$LOG"; }

# New commits since the last breadcrumb, oldest first.
if [ "$HEAD_WAS" != "-" ] && [ "$HEAD_WAS" != "$HEAD_NOW" ] \
   && git cat-file -e "$HEAD_WAS^{commit}" 2>/dev/null; then
  git log --reverse --format='%h %s' "$HEAD_WAS..$HEAD_NOW" 2>/dev/null \
    | while IFS= read -r line; do say "commit" "$line"; done
elif [ "$HEAD_WAS" = "-" ]; then
  say "session" "starting at $HEAD_NOW on $BRANCH"
fi

# Uncommitted work, as one line of stats rather than a diff.
STAT="$(git diff --shortstat 2>/dev/null | sed 's/^ *//')"
[ -n "$STAT" ] && say "working" "$STAT"

STAGED="$(git diff --cached --shortstat 2>/dev/null | sed 's/^ *//')"
[ -n "$STAGED" ] && say "staged" "$STAGED"

# Which files, capped so a big refactor does not write a hundred lines.
FILES="$(git status --porcelain=v1 2>/dev/null | awk '{print $NF}' | head -12 | tr '\n' ' ')"
[ -n "$FILES" ] && say "touched" "${FILES% }"

printf '%s\n%s\n' "$HEAD_NOW" "$FP" >"$STATE"
exit 0
