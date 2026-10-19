"""Exit 0 when new.json differs from old.json in anything but its timestamps, else 1.

Usage: python3 -I changed.py <old.json> <new.json>
Lets the scheduled refreshes skip commits that would only move "updated at" times.
"""
import json
import sys

STAMPS = {"updatedAt", "analysedAt", "asOf"}


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in STAMPS}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


try:
    old = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit(0)
sys.exit(0 if strip(old) != strip(json.load(open(sys.argv[2]))) else 1)
