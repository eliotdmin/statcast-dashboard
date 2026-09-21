#!/usr/bin/env python3
"""Publish output/full_report.html into the deployed site as web/report.html.

    python3 publish_report.py

The report is written as a self-contained fragment (no doctype or head). This
adds just enough document around it to render in standards mode on the site,
plus a way back to the addendum; the report's own content and styling are left
untouched. Re-run after editing the report -- web/report.html is a build output.

Lives at the repo root rather than in web/ on purpose: a .py file inside web/ is
what made Vercel misdetect the project as Python (DECISIONS D30).
"""
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "output" / "full_report.html"
OUT = ROOT / "web" / "report.html"

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Skill, Luck and Forecasting in Statcast Data, 2023–2026: the technical report behind Statcast Reality Check, with primary, secondary and tertiary analyses and their caveats.">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
"""

BACK = """<nav style="font-family:'IBM Plex Sans',-apple-system,sans-serif;font-size:13px;
max-width:760px;margin:18px auto 0;padding:0 20px;display:flex;gap:18px;flex-wrap:wrap">
<a href="/addendum.html" style="color:inherit;opacity:.7">&larr; Back to the Method page</a>
<a href="/report.html" download="statcast-reality-check-technical-report.html"
style="color:inherit;opacity:.7">Download this report (HTML)</a></nav>
"""


def main():
    body = SRC.read_text()
    marker = "</style>"
    assert body.count(marker) == 1, "expected exactly one </style> in the report"
    body = body.replace(marker, marker + "\n</head>\n<body>\n" + BACK, 1)
    OUT.write_text(HEAD + body + "\n</body>\n</html>\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
