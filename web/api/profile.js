// POST /api/profile  ->  { profile, model, usage, cost }
//
// The only reason this file exists is ANTHROPIC_API_KEY. Everything else here
// could run in the browser; the key cannot, because anything the browser can read
// is readable in devtools about four seconds after the page loads.
//
// Deploy:  vercel env add ANTHROPIC_API_KEY   (Production + Preview)
// Locally: serve.py does the same job without Node.

const fs = require("node:fs");
const path = require("node:path");

const MODEL  = process.env.PROFILE_MODEL || "claude-sonnet-4-5";
const SYSTEM = fs.readFileSync(path.join(process.cwd(), "profile_prompt.md"), "utf8");

// $ per million tokens. Overridable so a model swap does not need a code change.
const PRICE = { in: +(process.env.PRICE_IN || 3), out: +(process.env.PRICE_OUT || 15) };

const seen = new Map();                    // naive per-IP throttle; use KV in production
function throttled(ip, perMin = 12) {
  const now = Date.now();
  const hits = (seen.get(ip) || []).filter(t => now - t < 60_000);
  hits.push(now); seen.set(ip, hits);
  return hits.length > perMin;
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const ip = req.headers["x-forwarded-for"] || "local";
  if (throttled(ip)) return res.status(429).json({ error: "Too many profiles, wait a minute." });

  const { packet } = req.body || {};
  if (!packet || !Array.isArray(packet.metrics))
    return res.status(400).json({ error: "body must be { kind, packet }" });
  if (!process.env.ANTHROPIC_API_KEY)
    return res.status(500).json({ error: "ANTHROPIC_API_KEY is not set on this deployment" });

  // The client already built the packet and is showing it to the reader. Trusting
  // it keeps the audit table and the model's input identical by construction --
  // rebuilding it here from a player id would let the two drift, which is the one
  // thing that would make the "check every sentence" claim false.
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 700,
      // Identical on every call, so it caches: reads bill at 0.1x input.
      system: [{ type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } }],
      messages: [{ role: "user", content: JSON.stringify(packet) }],
    }),
  });

  if (!r.ok) return res.status(502).json({ error: "upstream " + r.status, detail: await r.text() });
  const j = await r.json();
  const u = j.usage || {};
  const billedIn = (u.input_tokens || 0) + 0.1 * (u.cache_read_input_tokens || 0);
  const cost = (billedIn * PRICE.in + (u.output_tokens || 0) * PRICE.out) / 1e6;

  res.setHeader("cache-control", "no-store");
  res.status(200).json({
    profile: j.content.filter(c => c.type === "text").map(c => c.text).join(""),
    model: MODEL, usage: u, cost, source: "live",
  });
};
