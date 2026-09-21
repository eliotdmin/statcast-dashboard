#!/bin/bash
# Daily refresh, designed to survive launchd.
#
# WHY THIS IS MORE COMPLICATED THAN `python3 run_pipeline.py`:
# launchd does not run your shell profile. It starts jobs with a minimal PATH
# (/usr/bin:/bin:/usr/sbin:/sbin), so `python3` resolves to Apple's system
# Python -- which does not have pybaseball installed. A job that works perfectly
# when you run it by hand fails silently at 11am. So we resolve the interpreter
# explicitly and refuse to run if it cannot import pybaseball.
set -uo pipefail
cd "$(dirname "$0")" || exit 1
mkdir -p logs
LOG="logs/refresh.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# A machine-specific interpreter path does not belong in a committed plist, so
# it lives in .refreshrc, which is gitignored. Create it with:
#     echo "STATCAST_PYTHON=$(which python3)" > .refreshrc
# from the shell where the pipeline already works -- that captures whatever your
# conda environment actually resolves to, without anyone having to guess.
[ -f .refreshrc ] && . ./.refreshrc

find_python() {
    # An explicit override always wins.
    if [ -n "${STATCAST_PYTHON:-}" ] && "$STATCAST_PYTHON" -c 'import pybaseball' 2>/dev/null; then
        echo "$STATCAST_PYTHON"; return 0
    fi
    # conda's own answer, if conda is reachable at all.
    for cbin in "$HOME/anaconda3/bin/conda" "$HOME/opt/anaconda3/bin/conda" \
                "$HOME/miniconda3/bin/conda" "$HOME/opt/miniconda3/bin/conda" \
                /opt/anaconda3/bin/conda /opt/miniconda3/bin/conda /opt/homebrew/bin/conda
    do
        if [ -x "$cbin" ]; then
            base="$("$cbin" info --base 2>/dev/null)"
            if [ -n "$base" ] && [ -x "$base/bin/python3" ] \
               && "$base/bin/python3" -c 'import pybaseball' 2>/dev/null; then
                echo "$base/bin/python3"; return 0
            fi
        fi
    done
    for p in \
        "$HOME/anaconda3/bin/python3" \
        "$HOME/opt/anaconda3/bin/python3" \
        "$HOME/opt/miniconda3/bin/python3" \
        "$HOME/miniconda3/bin/python3" \
        "$HOME/miniforge3/bin/python3" \
        /opt/anaconda3/bin/python3 \
        /opt/miniconda3/bin/python3 \
        /opt/homebrew/bin/python3 \
        /usr/local/bin/python3 \
        /usr/bin/python3
    do
        [ -x "$p" ] && "$p" -c 'import pybaseball' 2>/dev/null && { echo "$p"; return 0; }
    done
    return 1
}

log "=== refresh starting ==="
PYTHON="$(find_python)" || {
    log "FATAL: no python on this machine can import pybaseball."
    log "       Set STATCAST_PYTHON in the launchd plist to the right interpreter."
    exit 1
}
log "interpreter: $PYTHON"

YEAR="${STATCAST_YEAR:-$(date +%Y)}"
"$PYTHON" run_pipeline.py --year "$YEAR" >> "$LOG" 2>&1
rc=$?
log "run_pipeline exit=$rc"

# A refresh that silently corrupts the database is worse than one that fails, so
# check integrity every time. This is what would have caught the damage early.
"$PYTHON" - <<'PY' >> "$LOG" 2>&1
import sqlite3
c = sqlite3.connect("data/statcast.db")
v = c.execute("PRAGMA quick_check(3)").fetchone()[0]
n = c.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
print(f"integrity: {v} | pitches: {n:,}")
if v != "ok":
    raise SystemExit("DATABASE CORRUPT -- stop and recover before the next run")
PY
irc=$?
log "integrity exit=$irc"

# Publish, so the live site always shows this morning's numbers. Only after a clean pipeline and a
# clean integrity check: a failed refresh leaves yesterday's deploy up rather than shipping a
# partial one. deploy.sh ships the committed code plus the fresh data (see its header).
if [ "$rc" = 0 ] && [ "$irc" = 0 ] && [ "${STATCAST_NO_DEPLOY:-0}" != 1 ]; then
    ./deploy.sh >> "$LOG" 2>&1
    log "deploy exit=$?"
else
    log "deploy skipped (pipeline=$rc integrity=$irc)"
fi
log "=== refresh done ==="
exit $rc
