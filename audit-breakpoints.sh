#!/bin/bash
# Scans src for JSX files that lack Tailwind responsive prefixes

set -e

echo "Checking for missing breakpoints in .jsx files..."
# find all jsx files excluding non‑UI locations (context, tests, setup, entrypoint, api/hook/helper modules)
# grep -L prints those which do NOT contain any responsive prefixes
# find all JSX files under src, then remove known non-UI paths with grep -vE
missing=$(find src -type f -name "*.jsx" \
    | grep -vE '/context/|/tests/|/api/|/hooks/|/utils/|setupTests\.jsx$|main\.jsx$|App\.jsx$' \
    | xargs grep -L -E "sm:|md:|lg:|xl:|2xl:" || true)

final_missing=""
if [ -n "$missing" ]; then
  for file in $missing; do
    # skip files which include our opt-out comment
    if ! grep -q "ignore-breakpoints" "$file"; then
      final_missing="$final_missing$file\n"
    fi
  done
done

# drop empty lines
final_missing=$(echo -e "$final_missing" | sed '/^\s*$/d')

if [ -n "$final_missing" ]; then
  echo -e "\n🚨 The following files lack responsive prefixes:"
  echo "$final_missing"
  echo -e "\n👉 FIX: Add at least one sm:/md:/lg:/xl: utility to the file."
  echo "👉 OPT-OUT: If a component truly doesn't need responsiveness (like a Toast or Badge),"
  echo "   add this comment anywhere in the file to bypass this check: /* ignore-breakpoints */"
  exit 1
fi

echo "✅ All UI components passed the breakpoint audit!"

echo "All JSX files include responsive prefixes."
