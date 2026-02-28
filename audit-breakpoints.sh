#!/bin/bash
# Scans src for JSX files that lack Tailwind responsive prefixes

set -e

echo "Checking for missing breakpoints in .jsx files..."
# find all jsx files excluding the context directory
# grep -L prints those which do NOT contain any responsive prefixes
missing=$(find src -name "*.jsx" ! -path "*/context/*" | xargs grep -L -E "md:|lg:|xl:" || true)
if [ -n "$missing" ]; then
  echo "The following files lack responsive prefixes:"
  echo "$missing"
  echo "Please add at least one md:/lg:/xl: utility to each JSX file."
  exit 1
fi

echo "All JSX files include responsive prefixes."
