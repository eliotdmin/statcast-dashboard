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
set -uo pipefail
cd "$(dirname "$0")"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
[ -f .refreshrc ] && . ./.refreshrc   # may export VERCEL_TOKEN; gitignored

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

# The CLI's interactive login expires about 8 hours after it is issued, so the 11:00 job always
# starts with a stale one: the CLI refreshes it mid-command and the deploy itself still dies with
# "Error: Not authorized" (logs/refresh.log, 2026-09-22 and 09-23). Two defences:
#   1. VERCEL_TOKEN, a long-lived access token from the Vercel dashboard, is the supported way to
#      deploy unattended. Put it in .refreshrc (gitignored): echo 'export VERCEL_TOKEN=…' >> .refreshrc
#   2. Without one, refresh the session first with a throwaway command, then retry once.
TOKEN_ARG=()
[ -n "${VERCEL_TOKEN:-}" ] && TOKEN_ARG=(--token "$VERCEL_TOKEN")
[ ${#TOKEN_ARG[@]} -eq 0 ] && npx --yes vercel whoami >/dev/null 2>&1

if npx --yes vercel deploy --prod --yes "${TOKEN_ARG[@]+"${TOKEN_ARG[@]}"}"; then
    exit 0
fi
echo "deploy: first attempt failed; retrying once with refreshed credentials"
sleep 5
npx --yes vercel deploy --prod --yes "${TOKEN_ARG[@]+"${TOKEN_ARG[@]}"}"
