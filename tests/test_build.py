#!/usr/bin/env python3
"""Smoke tests for the site build. No database, no network -- safe to run in CI.

    python3 tests/test_build.py

`site/mksite.py` assembles `web/app.js` by running str.replace sixteen times over body.html's
script. str.replace does not raise when its pattern is missing, so a stale anchor yields a
working-looking file with a feature quietly gone (CLAUDE.md). These tests rebuild the site and
then check three things:

  1. every feature the rewrites are supposed to inject is present in the built app.js;
  2. every element id the script addresses exists in the page it addresses it in;
  3. rebuilding changes nothing that is committed -- i.e. web/ really is the build of site/.

(3) is the one that catches the common mistake: editing site/ and forgetting to rebuild.
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
FAILS = []


def check(name, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'' if ok else '  -- ' + detail}")
    if not ok:
        FAILS.append(name)


def test_build_runs():
    r = subprocess.run([sys.executable, "site/mksite.py"], cwd=ROOT,
                       capture_output=True, text=True)
    check("site/mksite.py runs", r.returncode == 0, r.stderr.strip()[-400:])
    return r.returncode == 0


def test_rewrites_applied(app):
    """One marker per thing mksite injects or rewrites. A silent no-op drops its marker."""
    wanted = {
        "summary component": "window.SUM",
        "summary mounted at boot": "SUM.mount(sumSection(active))",
        "analysis row built": "function initSubs()",
        "tab switching": "function show(i, sid)",
        "season line": "function renderLine()",
        "career lines": "function careerFor(",
        "key-numbers summary": "function runLineSum()",
        "head-to-head naive table": "function renderNaive(",
        "carry board as-of": "k-asof",
        "held over a fixed horizon": "HELD_BLOCKS",
        "evidence builder": "Evidence.build",
        "masthead nav": "window.onTabShow",
        "history fetch": "/data/history.json",
        "nav marks the open tab": "aria-current",
    }
    for name, marker in wanted.items():
        check(f"app.js carries the {name}", marker in app, f"missing marker {marker!r}")


def test_ids_exist(app, pages):
    """Every $("#id") the script uses must exist somewhere in the HTML it ships with."""
    used = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', app))
    used |= set(re.findall(r'getElementById\("([A-Za-z0-9_-]+)"\)', app))
    have = set()
    for p in pages:
        have |= set(re.findall(r'id="([A-Za-z0-9_-]+)"', p.read_text()))
    # ids the script creates at runtime rather than finding in the markup
    runtime = {"sum", "sum-go", "sum-again", "sum-title", "sum-sub", "sum-body", "sum-evwrap",
               "sum-evn", "sum-evnote", "sum-ev", "sum-meta", "sum-err", "pc-to-stretch",
               "pc-to-changes"}
    missing = sorted(used - have - runtime)
    check("every id the script addresses exists in the markup", not missing, ", ".join(missing))


def test_prompts_match_views():
    """Both backends whitelist the same views, and every view has a prompt file."""
    fn = (WEB / "api" / "summary.js").read_text()
    serve = (WEB / "serve.py").read_text()
    js = set(re.search(r"const VIEWS = \[(.*?)\];", fn, re.S).group(1).replace('"', "").split(", "))
    py = set(re.search(r"VIEWS = \((.*?)\)", serve, re.S).group(1).replace('"', "").split(", "))
    js = {v.strip() for v in js if v.strip()}
    py = {v.strip() for v in py if v.strip()}
    check("api/summary.js and serve.py whitelist the same views", js == py, f"{js ^ py}")
    missing = sorted(v for v in js if not (WEB / "prompts" / f"{v}.md").exists())
    check("every view has a prompt file", not missing, ", ".join(missing))


def test_data_contract():
    """The client reads these files by name; the pipeline writes them."""
    if not (WEB / "data").exists():          # gitignored: present on the Mac, absent in CI
        print("  skip  web/data checks (no web/data in this checkout)")
        return
    need = ["blocks_index.json", "bat-2026.json", "pit-2026.json", "history.json",
            "matchup-bat.json", "reliability-bat.json", "lines-bat.json", "careers-bat.json"]
    missing = [f for f in need if not (WEB / "data" / f).exists()]
    check("web/data holds every file the client fetches", not missing,
          ", ".join(missing) + " (run the pipeline)")
    if not missing:
        shard = json.loads((WEB / "data" / "bat-2026.json").read_text())
        surface = {"g", "ab", "h1", "hr", "bb", "k", "pa", "wn"} <= set(shard["fields"])
        check("the hitter shard carries the surface fields", surface)


def test_build_is_committed():
    """web/ is generated; if it differs from HEAD after a rebuild, someone edited one and not the other."""
    r = subprocess.run(["git", "status", "--porcelain", "--", "web"], cwd=ROOT,
                       capture_output=True, text=True)
    dirty = [l for l in r.stdout.splitlines() if not l.split()[-1].startswith("web/data/")]
    check("rebuilding site/ leaves web/ unchanged", not dirty,
          "rebuild and commit: " + "; ".join(dirty[:5]))


def main():
    print("site build")
    if not test_build_runs():
        sys.exit(1)
    app = (WEB / "app.js").read_text()
    test_rewrites_applied(app)
    test_ids_exist(app, [WEB / "app" / "index.html", WEB / "index.html"])
    test_prompts_match_views()
    test_data_contract()
    test_build_is_committed()
    print(f"\n{'FAILED: ' + ', '.join(FAILS) if FAILS else 'all build checks passed'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
