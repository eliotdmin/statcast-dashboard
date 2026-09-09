#!/bin/bash
# Daily refresh. Edit PYTHON below if you use a conda env.
cd "$(dirname "$0")" || exit 1
PYTHON="${STATCAST_PYTHON:-python3}"
YEAR="${STATCAST_YEAR:-$(date +%Y)}"
echo "=== refresh $(date) ==="
"$PYTHON" run_pipeline.py --year "$YEAR" >> logs/refresh.log 2>&1
echo "exit=$? $(date)" >> logs/refresh.log
