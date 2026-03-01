#!/usr/bin/env bash
# Scans src for JSX files that lack Tailwind responsive prefixes

set -euo pipefail

echo "Checking for missing breakpoints in .jsx files..."

missing=$(find src -type f -name "*.jsx" \
    | grep -vE '/context/|/tests/|/api/|/hooks/|/utils/|setupTests\.jsx$|main\.jsx$|App\.jsx$' \
    | xargs grep -L -E "sm:|md:|lg:|xl:|2xl:" || true)

final_missing=()

if [ -n "$missing" ]; then
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    if ! grep -q "ignore-breakpoints" "$file"; then
      final_missing+=("$file")
    fi
  done <<< "$missing"
fi

if [ "${#final_missing[@]}" -gt 0 ]; then
  echo
  echo "🚨 The following files lack responsive prefixes:"
  printf '%s\n' "${final_missing[@]}"
  echo
  echo "👉 FIX: Add at least one sm:/md:/lg:/xl: utility to the file."
  echo "👉 OPT-OUT: If a component truly doesn't need responsiveness (like a Toast or Badge),"
  echo "   add this comment anywhere in the file to bypass this check: /* ignore-breakpoints */"
  exit 1
fi

echo "✅ All UI components passed the breakpoint audit!"
