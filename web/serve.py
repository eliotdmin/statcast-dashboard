#!/usr/bin/env python3
"""Local dev server. No npm, no account, no build step.

    python3 serve.py            ->  http://localhost:8787

Serves the static files and implements POST /api/summary, which is the one route
Vercel would run as a serverless function. Two modes, chosen automatically:

    ANTHROPIC_API_KEY set    -> calls the real model, exactly as api/summary.js does
    not set                  -> returns a stored response, one per view

The point of the fallback is that you can see the whole design and the whole
interaction without spending a cent or creating an account. The moment you export
a key, the same button starts generating for any player and any window.

Why this exists alongside api/summary.js: `vercel dev` runs the real thing but
needs Node and a Vercel login. This needs neither, and it keeps the local
experience honest about which mode it is in -- the meter says "stored response"
in orange when there is no key.
"""
import http.server, socketserver, json, os, sys, urllib.request, mimetypes, functools

PORT = int(os.environ.get("PORT", 8787))
ROOT = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("PROFILE_MODEL", "claude-haiku-4-5-20251001")
PRICE_IN, PRICE_OUT = 1.0, 5.0      # Haiku 4.5, $ per million tokens

PROMPTS = os.path.join(ROOT, "prompts")
STORED = os.path.join(ROOT, "stored_summaries.json")
VIEWS = ("stretch", "changes", "carry", "planner", "breakouts", "card", "vs", "line", "hotcold")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")


def stream_model(handler, view, evidence):
    # Same two-block system as api/summary.js: the base rules are byte-identical
    # on every call so they cache, and the small per-view block sits after the
    # breakpoint. Keeping the two implementations in step matters -- if local and
    # deployed used different prompts, testing locally would prove nothing. Same
    # goes for the wire protocol: both relay Anthropic's SSE stream as the same
    # newline-delimited {delta|error|done} shape, so the browser needs only one
    # reader regardless of which backend answered it.
    base = open(os.path.join(PROMPTS, "base.md")).read()
    per = open(os.path.join(PROMPTS, view + ".md")).read()
    payload = {"view": view, "title": evidence.get("title"), "subject": evidence.get("sub"),
               "columns": [c["k"] for c in evidence.get("cols", [])],
               "rows": evidence.get("rows", []), "context": evidence.get("context")}
    body = json.dumps({
        "model": MODEL, "max_tokens": 500, "stream": True,
        "system": [{"type": "text", "text": base,
                    "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": per}],
        "messages": [{"role": "user", "content": json.dumps(payload)}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})

    # Open the upstream connection before committing to a local response: if
    # Anthropic refuses the request (bad key, rate limit, network failure), this
    # raises here and do_POST's except still turns it into a clean 502. Only once
    # the stream has actually started do we send our own 200 -- past that point a
    # failure can no longer become an HTTP error status, only an ndjson error line.
    with urllib.request.urlopen(req, timeout=60) as r:
        handler.send_response(200)
        handler.send_header("content-type", "application/x-ndjson")
        handler.send_header("cache-control", "no-store")
        handler.end_headers()

        usage = {"input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0}
        saw_error = False
        try:
            for raw_line in r:
                line = raw_line.decode("utf8").rstrip("\n")
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except Exception:
                    continue
                t = evt.get("type")
                if t == "message_start":
                    usage.update(evt.get("message", {}).get("usage", {}))
                elif t == "content_block_delta":
                    d = evt.get("delta", {})
                    if d.get("type") == "text_delta":
                        ndjson(handler, {"type": "delta", "text": d.get("text", "")})
                elif t == "message_delta" and evt.get("usage"):
                    usage.update(evt["usage"])
                elif t == "error":
                    saw_error = True
                    ndjson(handler, {"type": "error",
                                      "error": evt.get("error", {}).get("message", "stream error")})
        except Exception as e:
            ndjson(handler, {"type": "error", "error": "stream failed: %s" % e})
            return

    if not saw_error:
        billed_in = usage.get("input_tokens", 0) + 0.1 * usage.get("cache_read_input_tokens", 0)
        cost = (billed_in * PRICE_IN + usage.get("output_tokens", 0) * PRICE_OUT) / 1e6
        ndjson(handler, {"type": "done", "model": MODEL, "usage": usage, "cost": cost, "source": "live"})


def ndjson(handler, obj):
    handler.wfile.write((json.dumps(obj) + "\n").encode())
    handler.wfile.flush()


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):      # one tidy line per request
        sys.stderr.write("  %s\n" % (fmt % args))

    def end_headers(self):
        # Mirror vercel.json for the shards so local and deployed behave the same.
        # Everything else is no-store: this is a dev server, and the whole point
        # of it is that you edit site/, rebuild, and reload. Heuristic caching of
        # app.js silently serves the previous build, which looks exactly like a
        # change that did not work.
        if self.path.startswith("/data/"):
            self.send_header("Cache-Control", "public, max-age=300")
        else:
            self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if self.path != "/api/summary":
            return self._json(404, {"error": "no such route"})
        n = int(self.headers.get("content-length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad JSON"})
        view = req.get("view")
        evidence = req.get("evidence") or {}
        if view not in VIEWS:
            return self._json(400, {"error": "unknown view: %r" % (view,)})
        if not evidence.get("rows"):
            return self._json(400, {"error": "body must be { view, evidence } with evidence.rows"})

        if KEY:
            try:
                return stream_model(self, view, evidence)
            except Exception as e:
                return self._json(502, {"error": "upstream: %s" % e})

        # No key: hand back the stored response for this view, as a single delta
        # plus done -- same protocol as the live path, so the browser's reader
        # doesn't need to know which one answered it. Written against real output
        # from this dataset, and the meter labels it in orange, so nobody mistakes
        # it for something just generated.
        stored = json.load(open(STORED)) if os.path.exists(STORED) else {}
        text = stored.get(view)
        if not text:
            return self._json(404, {"error":
                "No ANTHROPIC_API_KEY is set and there is no stored response for "
                "the %s view. Export a key and restart to generate live." % view})
        words = len(text.split())
        self.send_response(200)
        self.send_header("content-type", "application/x-ndjson")
        self.send_header("cache-control", "no-store")
        self.end_headers()
        ndjson(self, {"type": "delta", "text": text})
        ndjson(self, {
            "type": "done", "model": MODEL, "source": "stored",
            "usage": {"input_tokens": 1800 + 40 * len(evidence.get("rows", [])),
                      "cache_read_input_tokens": 1650,
                      "output_tokens": int(words * 1.35)},
            "cost": 0.0})


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    mode = ("LIVE  -- ANTHROPIC_API_KEY found, profiles will be generated"
            if KEY else
            "STORED -- no ANTHROPIC_API_KEY; four demo players only")
    print("\n  Statcast Reality Check")
    print("  http://localhost:%d" % PORT)
    print("  profile mode: %s\n" % mode)
    with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped\n")
