# web/ — the deployable site

The same four views as the artifact, restructured the way a real site is: markup,
styles, script and data in separate files, with one serverless function.

## Run it locally

```bash
cd web
python3 serve.py          # -> http://localhost:8787
```

No npm, no build step, no account. `serve.py` serves the static files and
implements `POST /api/summary`, the one route Vercel would run as a function.

Two modes, chosen automatically:

| | behaviour |
|---|---|
| `ANTHROPIC_API_KEY` **not** set | returns a stored profile; only the four demo players (Bregman, Raleigh, Walker, Cease). The meter says so in orange. |
| `ANTHROPIC_API_KEY` set | calls the model for any player and window, exactly as `api/summary.js` does |

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 serve.py
```

Do not open `index.html` from the filesystem — `fetch()` refuses `file://` URLs
and the data will not load.

## Deploy it

```bash
vercel                              # first deploy, links the project
vercel env add ANTHROPIC_API_KEY    # Production + Preview
vercel --prod
```

`vercel dev` runs the real Node function locally if you prefer that to `serve.py`;
it needs Node and a Vercel login.

## Layout

```
index.html        markup only. Real <head>: description, OG tags, theme-color,
                  favicon, a preload hint for the first shard.
styles.css        every visual decision. Tokens in :root; components read from
                  them, so retheming the site is one block.
app.js            the client. Fetches shards on demand.
lib/evidence.js   evidence builder, UMD-wrapped so the browser and the
                  function share ONE implementation. The audit table and the
                  model's input cannot drift apart.
api/summary.js    Vercel function. The only reason it exists is that the key
                  cannot live in the browser.
serve.py          local equivalent, zero dependencies.
report.html       GENERATED from ../output/full_report.html by ../publish_report.py.
                  Edit the source report and re-run the script; never edit this copy.
img/ball.svg      the small baseball icon in the masthead (also the favicon).
img/hero-batter.jpg  landing-page photo. CC0 1.0 (public domain dedication) by
                  joshchristiane, https://www.flickr.com/photos/200661331@N05/53858412166
                  CC0 covers copyright only: he is an identifiable minor-league player
                  and team/brand logos are visible. Fine for this non-commercial site;
                  replace it before any commercial use.
og.png            1200x630 link-preview image (og:image on all three pages).
                  Built by `python3 make_og.py` from img/og-batter.jpg -- edit the
                  script, never the PNG.
img/og-batter.jpg CC0 1.0, rawpixel.com/image/6112394 (found via Openverse).
                  Public domain: no attribution required, commercial use fine.
data/*.json       per-(type, season) shards + blocks_index.json
data/breakouts.json  Streak history tab: two views (career-to-date |z|>=2 hot+cold, and
                  earlier-season hot streaks), each a ladder + case studies, written by
                  `python3 breakouts.py --export web/data/breakouts.json` (not refreshed
                  by the pipeline; re-run it by hand).
prompts/breakouts.md  summary prompt for the Streak history tab
vercel.json       cache headers; the shards get s-maxage=86400 so a repeat
                  visitor downloads nothing.
```

## Keeping the data fresh

`run_pipeline.py` writes `output/blocks/` on every daily refresh. Point the deploy
at those files — either copy them into `web/data/` as a build step, or serve
`output/blocks/` directly:

```bash
cp ../output/blocks/*.json data/
```

For a real deployment, do that in a GitHub Action on a schedule, or have the
launchd job push. The shards are content-stable, so a no-op day is a no-op deploy.

## What the first paint costs

| | gzipped |
|---|---|
| artifact version, all four seasons inlined | 1,866 KB |
| this, default view | **187 KB** |

Everything else loads only when the selector asks for it.
