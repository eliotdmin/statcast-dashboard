"""Loader for schema.yaml -- the single source of truth for column definitions.

audit.py and make_dictionary.py both read through here, so a fact stated once in
the YAML reaches the checks and the documentation without being retyped.
"""
from pathlib import Path

import yaml

PATH = Path(__file__).parent / "schema.yaml"


def load():
    return yaml.safe_load(PATH.read_text())


def columns(table="pitches"):
    """Flat {column: spec} for one table, groups collapsed."""
    out = {}
    for g in load()["tables"][table]["groups"]:
        for name, spec in g["columns"].items():
            out[name] = spec
    return out


def applicability(table="pitches"):
    """{column: (sql_predicate, human_label)} for every column with a condition."""
    return {c: (s["applies_when"], s["applies_label"])
            for c, s in columns(table).items() if s.get("applies_when")}


def plausible(table="pitches"):
    """{column: (low, high)} for every column with a stated physical range."""
    return {c: tuple(s["range"]) for c, s in columns(table).items() if s.get("range")}


def dead(table="pitches"):
    return [c for c, s in columns(table).items() if s.get("dead")]
