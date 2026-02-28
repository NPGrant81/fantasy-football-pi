#!/bin/bash
# Scans src for JSX files that lack Tailwind responsive prefixes

echo "Checking for missing breakpoints in .jsx files..."
grep -L -E "md:|lg:|xl:" src/**/*.jsx || true
