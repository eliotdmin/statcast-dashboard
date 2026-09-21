/* Evidence builder.
 *
 * Deliberately dependency-free and written for both runtimes: the browser
 * imports it with a <script> tag, the serverless function require()s it. One
 * implementation means the numbers the reader audits in the "evidence" table are
 * byte-for-byte the numbers the model was given -- if these drifted apart, the
 * whole auditability claim would be a lie.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Evidence = factory();
})(typeof self !== "undefined" ? self : this, function () {

  function relAt(rel, label, n) {
    var r = rel[label];
    if (!r || n <= 0) return 0;
    var k = n / r.n0, p = r.sb;
    return Math.max(0, Math.min(1, k * p / (1 + (k - 1) * p)));
  }
  function pctOf(pool, v) {
    if (!pool.length) return null;
    var c = 0; for (var i = 0; i < pool.length; i++) if (pool[i] < v) c++;
    return 100 * c / pool.length;
  }
  function sd(a) {
    if (a.length < 3) return 0;
    var m = 0, i; for (i = 0; i < a.length; i++) m += a[i]; m /= a.length;
    var s = 0; for (i = 0; i < a.length; i++) s += (a[i] - m) * (a[i] - m);
    return Math.sqrt(s / a.length);
  }
  function sum(row, keys, nf) {
    var out = new Array(nf).fill(0), j;
    keys.forEach(function (k) {
      var v = row.b[k]; if (!v) return;
      for (j = 0; j < nf; j++) out[j] += v[j];
    });
    return out;
  }

  /* metrics: [{k,n,d,hi,g}], where n/d are numerator and denominator fields */
  function build(shard, metrics, paKey, playerId, fromBlock, toBlock) {
    var F = {}; shard.fields.forEach(function (f, i) { F[f] = i; });
    var nf = shard.fields.length;
    var me = shard.rows.filter(function (r) { return String(r.id) === String(playerId); })[0];
    if (!me) throw new Error("no such player in this shard: " + playerId);

    var span = [], base = [];
    shard.blocks.forEach(function (b) {
      (b >= fromBlock && b <= toBlock ? span : base).push(b);
    });
    var now = sum(me, span, nf), bas = sum(me, base, nf);
    var n = now[F[paKey]], bn = bas[F[paKey]];

    var peers = shard.rows.map(function (r) { return sum(r, span, nf); })
                          .filter(function (v) { return v[F[paKey]] >= 20; });

    var rows = metrics.map(function (m) {
      var dv = now[F[m.d]];
      if (!dv) return { metric: m.k, group: m.g, available: false };
      var v = now[F[m.n]] / dv;
      var pool = peers.filter(function (x) { return x[F[m.d]] > 0; })
                      .map(function (x) { return x[F[m.n]] / x[F[m.d]]; });
      var raw = pctOf(pool, v); if (!m.hi) raw = 100 - raw;
      var rel = relAt(shard.rel, m.k, n);
      var o = { metric: m.k, group: m.g, available: true, value: v,
                higher_is_better: !!m.hi, pct_raw: raw, reliability: rel,
                pct_shrunk: 50 + rel * (raw - 50), change: null };
      if (bas[F[m.d]] && bn >= 60) {
        var b0 = bas[F[m.n]] / bas[F[m.d]], SD = sd(pool) || 1e-9;
        var vt = SD * SD * rel;
        var s1 = Math.sqrt(Math.max(1e-12, SD * SD - vt));
        var s2 = Math.sqrt(Math.max(1e-12, (SD * SD - vt) * (n / bn)));
        var se = Math.sqrt(s1 * s1 + s2 * s2), z = (v - b0) / se, a = Math.abs(z);
        var dsd = (v - b0) / SD, ad = Math.abs(dsd);
        o.change = { base_value: b0, delta: v - b0, se_noise: se, delta_z: z,
                     delta_sd: dsd,
                     verdict: a >= 2.5 ? "real" : (a >= 1.5 ? "weak" : "noise"),
                     size: ad >= 0.8 ? "large" : (ad >= 0.4 ? "moderate" : "small") };
      }
      return o;
    });

    return { player: me.n, mlbam_id: me.id, season: me.y,
             span: { from: fromBlock, to: toBlock, n: Math.round(n) },
             baseline: { n: Math.round(bn), usable: bn >= 60 },
             peer_pool: { n_players: peers.length },
             metrics: rows };
  }

  return { build: build, relAt: relAt, pctOf: pctOf, sd: sd, sum: sum };
});
