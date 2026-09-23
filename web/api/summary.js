// POST /api/summary  ->  { summary, model, usage, cost, source }
//
// The only reason this file exists is ANTHROPIC_API_KEY. Everything else here
// could run in the browser; the key cannot, because anything the browser can read
// is readable in devtools about four seconds after the page loads.
//
// Deploy:  vercel env add ANTHROPIC_API_KEY   (Production + Preview)
// Locally: serve.py does the same job without Node.

const fs = require("node:fs");
const path = require("node:path");

const MODEL = process.env.PROFILE_MODEL || "claude-haiku-4-5-20251001";
const DIR   = path.join(process.cwd(), "prompts");
const BASE  = fs.readFileSync(path.join(DIR, "base.md"), "utf8");
const VIEWS = ["stretch", "changes", "carry", "planner", "breakouts", "card", "vs", "line", "hotcold"];
const VIEW_PROMPT = Object.fromEntries(
  VIEWS.map(v => [v, fs.readFileSync(path.join(DIR, v + ".md"), "utf8")]));

// $ per million tokens. Overridable so a model swap does not need a code change.
const PRICE = { in: +(process.env.PRICE_IN || 1), out: +(process.env.PRICE_OUT || 5) };   // Haiku 4.5

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
  if (throttled(ip)) return res.status(429).json({ error: "Too many summaries, wait a minute." });

  const { view, evidence } = req.body || {};
  if (!VIEWS.includes(view)) return res.status(400).json({ error: "unknown view: " + view });
  if (!evidence || !Array.isArray(evidence.rows) || !evidence.rows.length)
    return res.status(400).json({ error: "body must be { view, evidence } with evidence.rows" });
  if (!process.env.ANTHROPIC_API_KEY)
    return res.status(500).json({ error: "ANTHROPIC_API_KEY is not set on this deployment" });

  // The client already built the evidence and is showing it to the reader. Trusting
  // it keeps the audit table and the model's input identical by construction --
  // rebuilding it here would let the two drift, which is the one thing that would
  // make the "check every sentence" claim false.
  const payload = { view, title: evidence.title, subject: evidence.sub,
                    columns: evidence.cols.map(c => c.k), rows: evidence.rows,
                    context: evidence.context };

  const upstream = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 500,
      stream: true,
      // BASE is byte-identical on every call, so it caches: reads bill at 0.1x.
      // The per-view block sits after the cache breakpoint and is cheap.
      system: [
        { type: "text", text: BASE, cache_control: { type: "ephemeral" } },
        { type: "text", text: VIEW_PROMPT[view] },
      ],
      messages: [{ role: "user", content: JSON.stringify(payload) }],
    }),
  });

  if (!upstream.ok || !upstream.body) {
    return res.status(502).json({ error: "upstream " + upstream.status, detail: await upstream.text() });
  }

  // Relayed as newline-delimited JSON, not raw SSE: the browser gets exactly the
  // three event shapes it needs (delta / error / done) instead of having to
  // understand Anthropic's event framing too. usage arrives split across
  // message_start (input + cache) and message_delta (output, cumulative), so it
  // is accumulated here and only reported once, in the final "done" line.
  res.writeHead(200, {
    "content-type": "application/x-ndjson",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });

  const usage = { input_tokens: 0, cache_read_input_tokens: 0, output_tokens: 0 };
  const reader = upstream.body.getReader();
  const dec = new TextDecoder();
  let buf = "", sawError = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const dataLine = raw.split("\n").find(l => l.startsWith("data:"));
        if (!dataLine) continue;
        let evt;
        try { evt = JSON.parse(dataLine.slice(5).trim()); } catch { continue; }

        if (evt.type === "message_start") {
          Object.assign(usage, evt.message.usage);
        } else if (evt.type === "content_block_delta" && evt.delta && evt.delta.type === "text_delta") {
          res.write(JSON.stringify({ type: "delta", text: evt.delta.text }) + "\n");
        } else if (evt.type === "message_delta" && evt.usage) {
          Object.assign(usage, evt.usage);
        } else if (evt.type === "error") {
          sawError = true;
          res.write(JSON.stringify({ type: "error", error: (evt.error && evt.error.message) || "stream error" }) + "\n");
        }
      }
    }
  } catch (e) {
    res.write(JSON.stringify({ type: "error", error: "stream failed: " + e.message }) + "\n");
    return res.end();
  }

  if (!sawError) {
    const billedIn = (usage.input_tokens || 0) + 0.1 * (usage.cache_read_input_tokens || 0);
    const cost = (billedIn * PRICE.in + (usage.output_tokens || 0) * PRICE.out) / 1e6;
    res.write(JSON.stringify({ type: "done", model: MODEL, usage, cost, source: "live" }) + "\n");
  }
  res.end();
};
