#!/bin/bash
# Scans src for JSX files that lack Tailwind responsive prefixes

set -e

echo "Checking for missing breakpoints in .jsx files..."
# find all jsx files excluding non‑UI locations (context, tests, setup, entrypoint, api/hook/helper modules)
# use NUL-delimited output so filenames with spaces/newlines are handled safely

final_missing=""
while IFS= read -r -d '' file; do
  # skip files which include our opt-out comment
  if ! grep -q "ignore-breakpoints" "$file"; then
    # check if file lacks any responsive prefix
    if ! grep -qE "sm:|md:|lg:|xl:|2xl:" "$file"; then
      final_missing="$final_missing$file\n"
    fi
  fi
done < <(find src -type f -name "*.jsx" \
    | grep -vE '/context/|/tests/|/api/|/hooks/|/utils/|setupTests\.jsx$|main\.jsx$|App\.jsx$' \
    | tr '\n' '\0')

# drop empty lines
final_missing=$(printf '%b' "$final_missing" | sed '/^\s*$/d')

if [ -n "$final_missing" ]; then
  echo -e "\n🚨 The following files lack responsive prefixes:"
  echo "$final_missing"
  echo -e "\n👉 FIX: Add at least one sm:/md:/lg:/xl: utility to the file."
  echo "👉 OPT-OUT: If a component truly doesn't need responsiveness (like a Toast or Badge),"
  echo "   add this comment anywhere in the file to bypass this check: /* ignore-breakpoints */"
  exit 1
fi

echo "✅ All UI components passed the breakpoint audit!"
