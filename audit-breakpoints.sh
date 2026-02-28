#!/bin/bash
# Scans src for JSX files that lack Tailwind responsive prefixes

set -e

echo "Checking for missing breakpoints in .jsx files..."
# grep -L prints files that do NOT contain any of the prefixes; capture them
missing=$(grep -L -E "md:|lg:|xl:" src/**/*.jsx || true)
if [ -n "$missing" ]; then
  echo "The following files lack responsive prefixes:"
  echo "$missing"
  echo "Please add at least one md:/lg:/xl: utility to each JSX file."
  exit 1
fi

echo "All JSX files include responsive prefixes."
