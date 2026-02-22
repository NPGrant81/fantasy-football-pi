#!/usr/bin/env python3
"""Regenerate the documentation INDEX.md file from docs/ contents.

Usage:
    python scripts/refresh_docs_index.py

This script is also invoked by a pre-commit hook to keep the index current
whenever any file in `docs/` changes.
"""

from pathlib import Path

DOCS = Path(__file__).parent.parent / "docs"
INDEX = DOCS / "INDEX.md"

header = "# Project Documentation Index\n\n" + \
         "This folder contains high-level documentation for the Fantasy Football Pi project.\n" + \
         "Refer to the appropriate file for more information.\n\n"

# gather markdown files except INDEX.md itself
files = [p.name for p in sorted(DOCS.glob("*.md")) if p.name.lower() != "index.md"]

with open(INDEX, "w", encoding="utf-8") as f:
    f.write(header)
    for name in files:
        title = name.replace("_", " ").replace(".md", "").title()
        f.write(f"- [{title}]({name})\n")

print(f"Refreshed {INDEX}")

# automatically stage the index so the updated file is committed
try:
    import subprocess
    subprocess.check_call(["git", "add", str(INDEX)])
    print(f"Staged {INDEX}")
except Exception as exc:
    # if git isn't available or fails, log for later inspection
    print(f"Warning: could not stage {INDEX}: {exc}")
