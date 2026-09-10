#!/usr/bin/env python3
"""Render DATA_DICTIONARY.md from schema.yaml.

    python3 make_dictionary.py

The markdown is a build artifact. Edit schema.yaml.
"""
from pathlib import Path

import schema

OUT = Path(__file__).parent / "DATA_DICTIONARY.md"
WARN = "\u26a0\ufe0f"


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_columns(cols):
    rows = ["| Column | Unit | Meaning |", "|---|---|---|"]
    for name, spec in cols.items():
        bits = [spec["desc"]]
        if spec.get("since"):
            bits.append(f"*Available from {spec['since']}.*")
        if spec.get("applies_label") and spec["applies_label"] != "all pitches":
            bits.append(f"Populated on {spec['applies_label']}.")
        if spec.get("range"):
            lo, hi = spec["range"]
            bits.append(f"Plausible range {lo} to {hi}.")
        if spec.get("gotcha"):
            bits.append(f"{WARN} **{spec['gotcha']}**")
        rows.append(f"| `{name}` | {cell(spec.get('unit') or '')} | {cell(' '.join(bits))} |")
    return "\n".join(rows)


def main():
    d = schema.load()
    m = d["meta"]
    out = [f"# {m['title']}", "", m["intro"], ""]

    for tname, t in d["tables"].items():
        out += ["---", "", f"## `{tname}`", "", t["description"], ""]
        if t.get("key_note"):
            out += [t["key_note"], ""]
        for g in t["groups"]:
            if len(t["groups"]) > 1 or g["name"] != "Columns":
                out += [f"### {g['name']}", ""]
            if g.get("note"):
                out += [g["note"], ""]
            out += [render_columns(g["columns"]), ""]

    dv = d["derived"]
    out += ["---", "", "## Derived metrics", "", dv["note"], "",
            "| Metric | Definition | What it assumes |", "|---|---|---|"]
    for k, v in dv["metrics"].items():
        out.append(f"| `{k}` | {cell(v['formula'])} | {cell(v['assumes'])} |")
    out.append("")

    out += ["---", "", "## The five gotchas most likely to produce a wrong answer", ""]
    for i, g in enumerate(m["gotchas"], 1):
        out.append(f"{i}. {g}")
    out += ["", "---", "", m["closing"], ""]
    out += ["", f"<!-- {m['generated_by']} -->", ""]

    OUT.write_text("\n".join(out))
    n = sum(len(g["columns"]) for t in d["tables"].values() for g in t["groups"])
    print(f"wrote {OUT} -- {n} columns across {len(d['tables'])} tables, {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
