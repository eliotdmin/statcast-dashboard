#!/usr/bin/env python3
"""Local dev server. No npm, no account, no build step.

    python3 serve.py            ->  http://localhost:8787

Serves the static files and implements POST /api/profile, which is the one route
Vercel would run as a serverless function. Two modes, chosen automatically:

    ANTHROPIC_API_KEY set    -> calls the real model, exactly as api/profile.js does
    not set                  -> returns a stored profile for the four demo players

The point of the fallback is that you can see the whole design and the whole
interaction without spending a cent or creating an account. The moment you export
a key, the same button starts generating for any player and any window.

Why this exists alongside api/profile.js: `vercel dev` runs the real thing but
needs Node and a Vercel login. This needs neither, and it keeps the local
experience honest about which mode it is in -- the meter says "stored profile"
in orange when there is no key.
"""
import http.server, socketserver, json, os, sys, urllib.request, mimetypes, functools

PORT = int(os.environ.get("PORT", 8787))
ROOT = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("PROFILE_MODEL", "claude-sonnet-4-5")
PRICE_IN, PRICE_OUT = 3.0, 15.0

PROMPT = os.path.join(os.path.dirname(ROOT), "profile_prompt.md")
STORED = os.path.join(ROOT, "stored_profiles.json")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")


def call_model(packet):
    system = open(PROMPT).read()
    body = json.dumps({
        "model": MODEL, "max_tokens": 700,
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": json.dumps(packet)}],
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
    return {"profile": text, "model": MODEL, "usage": u, "cost": cost, "source": "live"}


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
        if self.path != "/api/profile":
            return self._json(404, {"error": "no such route"})
        n = int(self.headers.get("content-length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad JSON"})
        packet = req.get("packet") or {}
        if not packet.get("metrics"):
            return self._json(400, {"error": "body must be { kind, packet }"})

        if KEY:
            try:
                return self._json(200, call_model(packet))
            except Exception as e:
                return self._json(502, {"error": "upstream: %s" % e})

        stored = json.load(open(STORED)) if os.path.exists(STORED) else {}
        rec = stored.get(str(packet.get("mlbam_id")))
        if not rec:
            names = ", ".join(v["player"] for v in stored.values())
            return self._json(404, {"error":
                "No ANTHROPIC_API_KEY is set, so only the stored profiles are "
                "available: " + names + ". Export a key and restart to generate "
                "for any player."})
        return self._json(200, {
            "profile": rec["text"], "model": MODEL, "source": "stored",
            "usage": {"input_tokens": rec["tokens_in"],
                      "cache_read_input_tokens": rec["cached_in"],
                      "output_tokens": rec["tokens_out"]},
            "cost": rec["cost"]})


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
