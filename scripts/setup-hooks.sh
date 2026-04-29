#!/usr/bin/env bash
# scripts/setup-hooks.sh
#
# Installs the repository's git hooks from .githooks/ into .git/hooks/.
# Run once after cloning, or re-run after hook updates.
#
# Usage:
#   bash scripts/setup-hooks.sh
#
# What it installs:
#   .githooks/pre-push  →  .git/hooks/pre-push
#     Runs `tests/local_pre_pr_check.sh changed` before every push to a
#     non-main branch, mirroring CI checks locally.
#
# To uninstall / disable a hook:
#   rm .git/hooks/pre-push
#
# To bypass one push without uninstalling:
#   git push --no-verify

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SRC="$REPO_ROOT/.githooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [[ ! -d "$HOOKS_DST" ]]; then
    echo "ERROR: .git/hooks directory not found. Are you in the repo root?"
    exit 1
fi

echo "Installing git hooks from .githooks/ → .git/hooks/ ..."

INSTALLED=0
SKIPPED=0

for hook_src in "$HOOKS_SRC"/*; do
    hook_name="$(basename "$hook_src")"
    hook_dst="$HOOKS_DST/$hook_name"

    # Skip backup+copy if the destination already matches the source (idempotent)
    if [[ -f "$hook_dst" ]] && cmp -s "$hook_src" "$hook_dst"; then
        echo "  Already up-to-date: $hook_name"
        ((SKIPPED++)) || true
        continue
    fi

    # Back up any existing hook that isn't already a symlink to ours
    if [[ -f "$hook_dst" && ! -L "$hook_dst" ]]; then
        ts="$(date +%s)"
        backup="$hook_dst.bak.$ts"
        echo "  Backing up existing $hook_name → $hook_name.bak.$ts"
        mv "$hook_dst" "$backup"
    fi

    cp "$hook_src" "$hook_dst"
    chmod +x "$hook_dst"
    echo "  Installed: $hook_name"
    ((INSTALLED++)) || true
done

echo ""
echo "Done. $INSTALLED hook(s) installed, $SKIPPED already up-to-date."
echo ""
echo "Hooks installed:"
echo "  pre-push  — runs 'tests/local_pre_pr_check.sh changed' before every push"
echo "              (skips pushes to main; bypass any push with: git push --no-verify)"
echo ""
echo "To verify:"
echo "  cat .git/hooks/pre-push"
