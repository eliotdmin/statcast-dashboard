// api/profile.js -- serverless endpoint for the stretch profile.
//
// SECURITY: the Anthropic key lives here, in a server-side environment variable, and
// never reaches the browser. The client posts {kind, player, season, from, to}; this
// function builds the evidence packet, calls the model, and returns prose. If you are
// ever tempted to call api.anthropic.com from client JS to "keep it simple", don't --
// the key is readable in devtools within about four seconds of the page loading.
//
// Deploy: Vercel (or Netlify/Cloudflare with trivial edits).
//   vercel env add ANTHROPIC_API_KEY
// Cost note: the system prompt is ~2k tokens and identical on every request, so it is
// marked cache_control ephemeral -- cache reads bill at 0.1x input. A profile is then
// roughly 2-3k uncached tokens in, ~350 out. On Sonnet that is well under a cent each.

import fs from "node:fs";
import path from "node:path";
import { buildPacket } from "../lib/packet.js";   // JS port of profile.py's build()

const SYSTEM = fs.readFileSync(path.join(process.cwd(), "profile_prompt.md"), "utf8");
const BLOCKS = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "output", "blocks_all.json"), "utf8"));

const LIMIT = new Map();                     // naive per-IP throttle; swap for KV in prod
function throttled(ip, perMin = 10) {
  const now = Date.now(), w = LIMIT.get(ip) || [];
  const recent = w.filter(t => now - t < 60_000);
  recent.push(now); LIMIT.set(ip, recent);
  return recent.length > perMin;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const ip = req.headers["x-forwarded-for"] || "local";
  if (throttled(ip)) return res.status(429).json({ error: "slow down" });

  const { kind, player, season, from, to } = req.body || {};
  if (!["bat", "pit"].includes(kind)) return res.status(400).json({ error: "bad kind" });

  let packet;
  try { packet = buildPacket(BLOCKS[kind], kind, player, season, from, to); }
  catch (e) { return res.status(404).json({ error: String(e.message || e) }); }

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-5",
      max_tokens: 700,
      system: [{ type: "text", text: SYSTEM, cache_control: { type: "ephemeral" } }],
      messages: [{ role: "user", content: JSON.stringify(packet) }],
    }),
  });
  if (!r.ok) return res.status(502).json({ error: "upstream", detail: await r.text() });
  const j = await r.json();

  // Return the packet alongside the prose. The page renders both, so a reader can check
  // every sentence against the numbers it came from -- which is the whole point.
  res.status(200).json({
    profile: j.content.filter(c => c.type === "text").map(c => c.text).join(""),
    packet,
    usage: j.usage,
  });
}
