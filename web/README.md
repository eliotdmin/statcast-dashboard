# web/ — the deployable site

The same four views as the artifact, restructured the way a real site is: markup,
styles, script and data in separate files, with one serverless function.

## Run it locally

```bash
cd web
python3 serve.py          # -> http://localhost:8787
```

No npm, no build step, no account. `serve.py` serves the static files and
implements `POST /api/profile`, the one route Vercel would run as a function.

Two modes, chosen automatically:

| | behaviour |
|---|---|
| `ANTHROPIC_API_KEY` **not** set | returns a stored profile; only the four demo players (Bregman, Raleigh, Walker, Cease). The meter says so in orange. |
| `ANTHROPIC_API_KEY` set | calls the model for any player and window, exactly as `api/profile.js` does |

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
lib/packet.js     evidence-packet builder, UMD-wrapped so the browser and the
                  function share ONE implementation. The audit table and the
                  model's input cannot drift apart.
api/profile.js    Vercel function. The only reason it exists is that the key
                  cannot live in the browser.
serve.py          local equivalent, zero dependencies.
data/*.json       per-(type, season) shards + blocks_index.json
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
