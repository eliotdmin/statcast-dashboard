#!/bin/bash
# Publish the site to production: the COMMITTED web/ plus the CURRENT web/data/.
#
#     ./deploy.sh             # deploy
#     ./deploy.sh --dry-run   # build the snapshot and list it, deploy nothing
#
# Why a snapshot rather than `cd web && npx vercel deploy --prod`: the daily refresh runs this
# unattended, and web/ on disk can hold half-finished work at 11:00. Deploying from `git archive
# HEAD` means production only ever gets code that was committed, while web/data/ -- gitignored,
# rebuilt by the pipeline every morning -- is copied in fresh, so the numbers are always current.
# The Vercel link (web/.vercel/project.json) is gitignored too, so it is copied across; the login
# comes from the Vercel CLI's own saved credentials.
set -euo pipefail
cd "$(dirname "$0")"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1

[ -f web/data/blocks_index.json ] || { echo "deploy: web/data looks empty; run the pipeline first"; exit 1; }
[ -f web/.vercel/project.json ] || { echo "deploy: web/ is not linked to Vercel (web/.vercel/project.json)"; exit 1; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/statcast-deploy.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
git archive HEAD web | tar -x -C "$TMP"
rsync -a --delete web/data/ "$TMP/web/data/"
mkdir -p "$TMP/web/.vercel" && cp web/.vercel/project.json "$TMP/web/.vercel/"

echo "deploy: snapshot of $(git rev-parse --short HEAD) + web/data ($(du -sh "$TMP/web/data" | cut -f1)), $(find "$TMP/web" -type f | wc -l | tr -d ' ') files"
if [ "$DRY" = 1 ]; then
    (cd "$TMP/web" && find . -maxdepth 2 -not -path "./data/*" | sort | head -40)
    exit 0
fi
cd "$TMP/web"
npx --yes vercel deploy --prod --yes
