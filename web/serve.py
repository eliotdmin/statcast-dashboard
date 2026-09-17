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
MODEL = os.environ.get("PROFILE_MODEL", "claude-sonnet-4-5")
PRICE_IN, PRICE_OUT = 3.0, 15.0

PROMPTS = os.path.join(ROOT, "prompts")
STORED = os.path.join(ROOT, "stored_summaries.json")
VIEWS = ("stretch", "changes", "carry", "planner")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")


def call_model(view, packet):
    # Same two-block system as api/summary.js: the base rules are byte-identical
    # on every call so they cache, and the small per-view block sits after the
    # breakpoint. Keeping the two implementations in step matters -- if local and
    # deployed used different prompts, testing locally would prove nothing.
    base = open(os.path.join(PROMPTS, "base.md")).read()
    per = open(os.path.join(PROMPTS, view + ".md")).read()
    payload = {"view": view, "title": packet.get("title"), "subject": packet.get("sub"),
               "columns": [c["k"] for c in packet.get("cols", [])],
               "rows": packet.get("rows", []), "context": packet.get("context")}
    body = json.dumps({
        "model": MODEL, "max_tokens": 900,
        "system": [{"type": "text", "text": base,
                    "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": per}],
        "messages": [{"role": "user", "content": json.dumps(payload)}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    u = j.get("usage", {})
    billed_in = u.get("input_tokens", 0) + 0.1 * u.get("cache_read_input_tokens", 0)
    cost = (billed_in * PRICE_IN + u.get("output_tokens", 0) * PRICE_OUT) / 1e6
    text = "".join(c["text"] for c in j["content"] if c["type"] == "text")
    return {"summary": text, "model": MODEL, "usage": u, "cost": cost, "source": "live"}


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):      # one tidy line per request
        sys.stderr.write("  %s\n" % (fmt % args))

    def end_headers(self):
        # Mirror vercel.json so local and deployed behave the same.
        if self.path.startswith("/data/"):
            self.send_header("Cache-Control", "public, max-age=300")
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
        packet = req.get("packet") or {}
        if view not in VIEWS:
            return self._json(400, {"error": "unknown view: %r" % (view,)})
        if not packet.get("rows"):
            return self._json(400, {"error": "body must be { view, packet } with packet.rows"})

        if KEY:
            try:
                return self._json(200, call_model(view, packet))
            except Exception as e:
                return self._json(502, {"error": "upstream: %s" % e})

        # No key: hand back the stored response for this view. It was written
        # against real output from this dataset, and the meter labels it in
        # orange, so nobody mistakes it for something just generated.
        stored = json.load(open(STORED)) if os.path.exists(STORED) else {}
        text = stored.get(view)
        if not text:
            return self._json(404, {"error":
                "No ANTHROPIC_API_KEY is set and there is no stored response for "
                "the %s view. Export a key and restart to generate live." % view})
        words = len(text.split())
        return self._json(200, {
            "summary": text, "model": MODEL, "source": "stored",
            "usage": {"input_tokens": 1800 + 40 * len(packet.get("rows", [])),
                      "cache_read_input_tokens": 1650,
                      "output_tokens": int(words * 1.35)},
            "cost": 0.0})


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    mode = ("LIVE  -- ANTHROPIC_API_KEY found, profiles will be generated"
            if KEY else
            "STORED -- no ANTHROPIC_API_KEY; four demo players only")
    print("\n  Stretch Finder")
    print("  http://localhost:%d" % PORT)
    print("  profile mode: %s\n" % mode)
    with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  stopped\n")
