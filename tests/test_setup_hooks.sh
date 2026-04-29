#!/usr/bin/env bash
# tests/test_setup_hooks.sh
#
# Tests for scripts/setup-hooks.sh
# Run from repo root: bash tests/test_setup_hooks.sh
# Exit 0 = all pass, Exit 1 = failures.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP_HOOKS="$REPO_ROOT/scripts/setup-hooks.sh"
GITHOOKS_SRC="$REPO_ROOT/.githooks"

PASS=0
FAIL=0

ok()   { echo "  [PASS] $*"; ((PASS++)) || true; }
fail() { echo "  [FAIL] $*"; ((FAIL++)) || true; }

echo ""
echo "=== tests/test_setup_hooks.sh ==="
echo ""

# ── Setup: work in a temp dir with a fake .git/hooks ─────────────────────────
TMPDIR_ROOT="$(mktemp -d)"
FAKE_REPO="$TMPDIR_ROOT/repo"
mkdir -p "$FAKE_REPO/.git/hooks"
mkdir -p "$FAKE_REPO/.githooks"
mkdir -p "$FAKE_REPO/scripts"
mkdir -p "$FAKE_REPO/tests"

# Copy the real scripts into the fake repo
cp "$SETUP_HOOKS"                     "$FAKE_REPO/scripts/setup-hooks.sh"
cp "$GITHOOKS_SRC/pre-push"           "$FAKE_REPO/.githooks/pre-push"

# Minimal gate script so the pre-push hook has something to call
cat > "$FAKE_REPO/tests/local_pre_pr_check.sh" <<'EOF'
#!/usr/bin/env bash
echo "[gate] mode=${1:-changed} — stub pass"
exit 0
EOF
chmod +x "$FAKE_REPO/tests/local_pre_pr_check.sh"

cleanup() { rm -rf "$TMPDIR_ROOT"; }
trap cleanup EXIT

# ── Test 1: setup-hooks.sh exits 0 ───────────────────────────────────────────
echo "1. setup-hooks.sh exits 0 in a valid repo"
if (cd "$FAKE_REPO" && bash scripts/setup-hooks.sh >/dev/null 2>&1); then
    ok "exits 0"
else
    fail "non-zero exit code"
fi

# ── Test 2: pre-push hook file is installed ────────────────────────────────────
echo "2. pre-push hook is installed to .git/hooks/"
if [[ -f "$FAKE_REPO/.git/hooks/pre-push" ]]; then
    ok "file exists"
else
    fail "file missing"
fi

# ── Test 3: installed hook is executable ─────────────────────────────────────
echo "3. installed hook is executable"
if [[ -x "$FAKE_REPO/.git/hooks/pre-push" ]]; then
    ok "executable"
else
    fail "not executable"
fi

# ── Test 4: re-running setup-hooks.sh succeeds (idempotent) ──────────────────
echo "4. setup-hooks.sh is idempotent (re-run succeeds)"
if (cd "$FAKE_REPO" && bash scripts/setup-hooks.sh >/dev/null 2>&1); then
    ok "second run exits 0"
else
    fail "second run failed"
fi

# ── Test 5: existing hook is backed up before overwrite ──────────────────────
echo "5. existing .git/hooks/pre-push is backed up when not managed by us"
# Remove the managed copy and place a foreign hook
rm "$FAKE_REPO/.git/hooks/pre-push"
echo "#!/bin/sh\necho old-hook" > "$FAKE_REPO/.git/hooks/pre-push"
chmod +x "$FAKE_REPO/.git/hooks/pre-push"

(cd "$FAKE_REPO" && bash scripts/setup-hooks.sh >/dev/null 2>&1)

BACKUPS=$(ls "$FAKE_REPO/.git/hooks/" | grep -c "pre-push.bak" || true)
if [[ $BACKUPS -ge 1 ]]; then
    ok "backup created ($BACKUPS file(s))"
else
    fail "no backup created"
fi

# ── Test 6: fails gracefully when .git/hooks dir is absent ───────────────────
echo "6. fails gracefully when .git directory is missing"
FAKE_NO_GIT="$TMPDIR_ROOT/no-git"
mkdir -p "$FAKE_NO_GIT/scripts" "$FAKE_NO_GIT/.githooks"
cp "$SETUP_HOOKS"             "$FAKE_NO_GIT/scripts/setup-hooks.sh"
cp "$GITHOOKS_SRC/pre-push"   "$FAKE_NO_GIT/.githooks/pre-push"

if ! (cd "$FAKE_NO_GIT" && bash scripts/setup-hooks.sh >/dev/null 2>&1); then
    ok "exits non-zero without .git/hooks"
else
    fail "should have failed without .git/hooks"
fi

# ── Test 7: pre-push hook passes when gate exits 0 ───────────────────────────
echo "7. pre-push hook passes when local_pre_pr_check.sh exits 0"
HOOK="$FAKE_REPO/.git/hooks/pre-push"
# Simulate git calling the hook: local_ref local_sha remote_ref remote_sha
PUSH_LINE="refs/heads/feat/foo abc123 refs/heads/feat/foo 000000"
if echo "$PUSH_LINE" | (cd "$FAKE_REPO" && bash "$HOOK" origin https://example.com 2>&1) >/dev/null 2>&1; then
    ok "hook exits 0 when gate passes"
else
    fail "hook unexpectedly failed"
fi

# ── Test 8: pre-push hook skips when pushing a deletion (zero sha) ───────────
echo "8. pre-push hook skips branch deletion (zero sha)"
DELETE_LINE="refs/heads/feat/old 0000000000000000000000000000000000000000 refs/heads/feat/old 0000000000000000000000000000000000000000"
if echo "$DELETE_LINE" | (cd "$FAKE_REPO" && bash "$HOOK" origin https://example.com 2>&1) >/dev/null 2>&1; then
    ok "hook exits 0 on branch deletion"
else
    fail "hook failed on branch deletion"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== $PASS passed | $FAIL failed ==="
echo ""
[[ $FAIL -eq 0 ]]
