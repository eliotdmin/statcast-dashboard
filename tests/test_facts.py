#!/usr/bin/env python3
"""Characterization tests over the archive and over published findings.

Run:  python3 tests/test_facts.py [--db data/statcast.db]

The point is not code correctness. It is that every number this project has
published is asserted against the data, so that a re-backfill, a provider schema
change, or a silent redefinition of a column makes a test FAIL rather than
quietly rotting a finding.

Two of these would have caught real bugs that cost days:
  * test_woba_reconciles  -> D24, woba_value credits reached-on-error as a hit
  * test_no_schema_drift  -> D15, sz_top redefined between 2025 and 2026

Every assertion names the finding it protects. If one fails, that finding is
suspect until re-derived. Do not simply update the expected constant.
"""
import argparse, math, sqlite3, sys
from pathlib import Path

HIT = ("events IN ('single','double','triple','home_run','walk','hit_by_pitch')")
FAILS, PASSES, ERRS = [], [], []


def check(name, protects):
    def deco(fn):
        fn._name, fn._protects = name, protects
        return fn
    return deco


def approx(got, want, tol, what):
    if got is None:
        raise AssertionError(f"{what}: got None")
    if abs(got - want) > tol:
        raise AssertionError(f"{what}: got {got:+.5f}, expected {want:+.5f} +/- {tol}")


def corr(pairs):
    n = len(pairs)
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    num = sum((u - mx) * (v - my) for u, v in pairs)
    den = math.sqrt(sum((u - mx) ** 2 for u, _ in pairs) * sum((v - my) ** 2 for _, v in pairs))
    return num / den if den else 0.0


# --------------------------------------------------------------- integrity
@check("archive shape", "the panel every result is computed on")
def test_a_shape(con):
    n, = con.execute("SELECT COUNT(*) FROM pitches").fetchone()
    assert n > 2_800_000, f"pitch count collapsed to {n:,}"
    for y, lo in ((2023, 700_000), (2024, 700_000), (2025, 700_000), (2026, 600_000)):
        c, = con.execute("SELECT COUNT(*) FROM pitches WHERE game_year=? AND game_type='R'",
                         (y,)).fetchone()
        assert c > lo, f"{y} regular season has only {c:,} pitches"


@check("wOBA reconciles", "D24 - woba_value is not wOBA")
def test_b_woba_reconciles(con):
    """THE test. Computed wOBA must match Savant's published figure for the same
    players. Also asserts the NAIVE version still fails, so this guard cannot
    silently become vacuous if the provider fixes the column."""
    for y in (2023, 2024, 2025, 2026):
        rows = con.execute(f"""
            SELECT e.woba,
              (SELECT SUM(CASE WHEN p.woba_denom=1 AND
                      p.events IN ('single','double','triple','home_run','walk','hit_by_pitch')
                    THEN p.woba_value ELSE 0 END)*1.0/NULLIF(SUM(p.woba_denom),0)
               FROM pitches p WHERE p.batter=e.player_id AND p.game_year=e.year
                 AND p.game_type='R'),
              (SELECT SUM(CASE WHEN p.woba_denom=1 THEN p.woba_value END)*1.0
                      /NULLIF(SUM(p.woba_denom),0)
               FROM pitches p WHERE p.batter=e.player_id AND p.game_year=e.year
                 AND p.game_type='R')
            FROM expected_stats e
            WHERE e.year=? AND e.player_type='batter' AND e.pa>=300""", (y,)).fetchall()
        good = [r for r in rows if r[1] is not None and r[2] is not None]
        assert len(good) > 150, f"{y}: only {len(good)} players to reconcile"
        fixed = sum(r[1] - r[0] for r in good) / len(good)
        naive = sum(r[2] - r[0] for r in good) / len(good)
        assert abs(fixed) < 0.005, (
            f"{y}: corrected wOBA is {fixed:+.5f} off Savant across {len(good)} players. "
            "The numerator definition has drifted.")
        assert naive > 0.004, (
            f"{y}: the raw woba_value column no longer over-credits ({naive:+.5f}). "
            "If the provider fixed it, retire D24 and delete this guard deliberately.")


@check("no schema drift", "D15 - sz_top was redefined in 2026")
def test_c_no_schema_drift(con):
    """A column whose distinct-value count jumps by orders of magnitude between
    seasons has changed meaning. This is the check that would have caught sz_top
    (353,643 distinct in 2025, 390 in 2026) before it produced a backwards
    conclusion about the strike zone."""
    WATCH = ["release_speed", "plate_x", "plate_z", "launch_speed", "launch_angle",
             "bat_speed", "attack_angle", "estimated_woba_using_speedangle"]
    bad = []
    for c in WATCH:
        d = {}
        for y in (2025, 2026):
            d[y], = con.execute(
                f'SELECT COUNT(DISTINCT "{c}") FROM pitches WHERE game_year=? '
                "AND game_type='R'", (y,)).fetchone()
        a, b = d[2025], d[2026]
        if a > 1000 and b > 0 and (a / b > 5 or b / a > 5):
            bad.append(f"{c}: {a:,} distinct in 2025 -> {b:,} in 2026")
    assert not bad, "column meaning may have changed:\n        " + "\n        ".join(bad)
    a, = con.execute("SELECT COUNT(DISTINCT sz_top) FROM pitches WHERE game_year=2025 "
                     "AND game_type='R'").fetchone()
    b, = con.execute("SELECT COUNT(DISTINCT sz_top) FROM pitches WHERE game_year=2026 "
                     "AND game_type='R'").fetchone()
    assert a > 100_000 and b < 2_000, (
        f"sz_top pattern changed: {a:,} -> {b:,}. D15 may need revisiting.")


# --------------------------------------------------------------- findings
@check("count spread", "TAKEAWAYS 5 - the count matters ~2x the hitter")
def test_d_counts(con):
    q = """WITH pa AS (SELECT game_pk, at_bat_number, MAX(woba_denom) wd,
             MAX(CASE WHEN events IN ('single','double','triple','home_run','walk',
                 'hit_by_pitch') THEN woba_value ELSE 0 END) wv
           FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
           GROUP BY 1,2),
         r AS (SELECT DISTINCT game_pk, at_bat_number FROM pitches
           WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
             AND balls=? AND strikes=?)
         SELECT SUM(p.wv)*1.0/SUM(p.wd) FROM r JOIN pa p
           ON r.game_pk=p.game_pk AND r.at_bat_number=p.at_bat_number"""
    w02, = con.execute(q, (0, 2)).fetchone()
    w30, = con.execute(q, (3, 0)).fetchone()
    assert w30 > w02, "count ordering inverted"
    assert w30 - w02 > 0.30, (
        f"count spread collapsed to {w30-w02:.4f} (0-2 {w02:.4f}, 3-0 {w30:.4f}); "
        "the finding was roughly .35 on the corrected numerator")


@check("popup bias / GB retraction", "TAKEAWAYS 4 - xwOBA over-rates popups")
def test_e_batted_ball_bias(con):
    out = {}
    for bt in ("ground_ball", "popup"):
        n, w, x = con.execute(f"""SELECT COUNT(*),
            AVG(CASE WHEN {HIT} THEN woba_value ELSE 0 END),
            AVG(estimated_woba_using_speedangle) FROM pitches
          WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R' AND type='X'
            AND woba_denom=1 AND estimated_woba_using_speedangle IS NOT NULL
            AND bb_type=?""", (bt,)).fetchone()
        out[bt] = w - x
    approx(out["popup"], -0.0176, 0.005, "popup gap")
    assert abs(out["ground_ball"]) < 0.006, (
        f"ground-ball gap is {out['ground_ball']:+.4f}. The +.0234 version was an "
        "artifact of crediting reached-on-error (D24). If it is large again, the "
        "numerator has regressed.")


@check("pitcher gap is noise", "TAKEAWAYS 4 - persists for hitters, not pitchers")
def test_f_pitcher_gap(con):
    piv = {}
    for pid, y, bf, w, x in con.execute(f"""SELECT pitcher, game_year, SUM(woba_denom),
        SUM(CASE WHEN woba_denom=1 AND {HIT} THEN woba_value ELSE 0 END),
        SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,
            CASE WHEN {HIT} THEN woba_value ELSE 0 END) END)
      FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
      GROUP BY 1,2 HAVING SUM(woba_denom)>=300"""):
        piv.setdefault(pid, {})[y] = (w - x) / bf
    cors = []
    for a, b in ((2023, 2024), (2024, 2025), (2025, 2026)):
        d = [(piv[p][a], piv[p][b]) for p in piv if a in piv[p] and b in piv[p]]
        if len(d) > 40:
            cors.append(corr(d))
    assert len(cors) >= 2, "not enough season pairs"
    assert max(cors) < 0.25, (
        f"pitcher gap now correlates {max(cors):+.3f} season to season; the finding "
        "was that it does not persist (max +0.16)")


@check("skills stable, results not", "TAKEAWAYS 3 - the slump result")
def test_g_stability(con):
    """Bat speed must repeat far better month to month than wOBA does. This is
    the backbone of the slump finding."""
    rows = con.execute(f"""SELECT batter, game_year, CAST(substr(game_date,6,2) AS INT) mon,
        SUM(woba_denom) pa,
        SUM(CASE WHEN woba_denom=1 AND {HIT} THEN woba_value ELSE 0 END) wn,
        SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs, SUM(bat_speed) sbs
      FROM pitches WHERE game_year BETWEEN 2024 AND 2026 AND game_type='R'
      GROUP BY 1,2,3 HAVING pa>=40 AND nbs>=40""").fetchall()
    idx = {(r[0], r[1], r[2]): r for r in rows}
    pw, pb = [], []
    for (b, y, m), r in idx.items():
        n = idx.get((b, y, m + 1))
        if not n: continue
        pw.append((r[4] / r[3], n[4] / n[3]))
        pb.append((r[6] / r[5], n[6] / n[5]))
    assert len(pw) > 500, f"only {len(pw)} adjacent month pairs"
    rw, rb = corr(pw), corr(pb)
    assert rb > 0.85, f"bat speed month-to-month correlation fell to {rb:.3f}"
    assert rw < 0.35, f"wOBA month-to-month correlation rose to {rw:.3f}"
    assert rb - rw > 0.5, (
        f"the skill/result stability gap narrowed to {rb-rw:.3f}; the finding was "
        f"bat speed ~.92 against wOBA ~.14")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).resolve().parent.parent / "data" / "statcast.db"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v) and hasattr(v, "_name")]
    print(f"running {len(tests)} fact tests against {a.db}\n")
    for t in tests:
        try:
            t(con)
            PASSES.append(t._name)
            print(f"  PASS   {t._name:<26} guards: {t._protects}")
        except AssertionError as e:
            FAILS.append(t._name)
            print(f"  FAIL   {t._name:<26} guards: {t._protects}\n         {e}")
        except Exception as e:
            ERRS.append(t._name)
            print(f"  ERROR  {t._name:<26} {type(e).__name__}: {e}")
    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed, {len(ERRS)} errored")
    if FAILS:
        print("\nA FAILING FACT TEST MEANS A PUBLISHED FINDING IS NOW SUSPECT.")
        print("Re-derive it. Do not simply update the expected constant.")
    return 1 if (FAILS or ERRS) else 0


if __name__ == "__main__":
    sys.exit(main())
