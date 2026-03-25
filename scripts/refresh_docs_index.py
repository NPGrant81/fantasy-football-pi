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

# Gather all markdown files recursively, excluding INDEX.md itself.
# Sort: top-level files first (alphabetically), then subdirectory files
# grouped by directory to keep the index readable.
all_md = sorted(DOCS.rglob("*.md"))
top_level = [p for p in all_md if p.parent == DOCS and p.name.lower() != "index.md"]
subdirs = [p for p in all_md if p.parent != DOCS]

with open(INDEX, "w", encoding="utf-8") as f:
    f.write(header)
    for p in top_level:
        title = p.name.replace("_", " ").replace(".md", "").title()
        f.write(f"- [{title}]({p.name})\n")
    if subdirs:
        f.write("\n## Sub-directories\n\n")
        current_dir = None
        for p in subdirs:
            rel = p.relative_to(DOCS).as_posix()
            if p.parent != current_dir:
                current_dir = p.parent
                f.write(f"\n### {p.parent.name.title()}\n\n")
            title = p.name.replace("_", " ").replace(".md", "").title()
            f.write(f"- [{title}]({rel})\n")

print(f"Refreshed {INDEX}")

# automatically stage the index so the updated file is committed
try:
    import subprocess
    subprocess.check_call(["git", "add", str(INDEX)])
    print(f"Staged {INDEX}")
except Exception as exc:
    # if git isn't available or fails, log for later inspection
    print(f"Warning: could not stage {INDEX}: {exc}")
