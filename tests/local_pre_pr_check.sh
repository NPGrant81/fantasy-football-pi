#!/usr/bin/env bash
# tests/local_pre_pr_check.sh
#
# Local pre-PR gate — run before pushing a branch or opening a PR.
# Mirrors the CI checks so "works on my machine" failures are caught early.
#
# Usage:
#   ./tests/local_pre_pr_check.sh                 # changed files only (fast)
#   ./tests/local_pre_pr_check.sh changed          # same as default
#   ./tests/local_pre_pr_check.sh full             # all test lanes
#   ./tests/local_pre_pr_check.sh full --with-e2e  # all lanes + E2E (future)
#
# Exit codes:
#   0  — all checks passed
#   1  — one or more checks failed (summary printed at end)
#
# Environment variables:
#   SKIP_BACKEND=1   — skip backend pytest suite
#   SKIP_FRONTEND=1  — skip frontend vitest suite
#   SKIP_ETL=1       — skip ETL pytest suite

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$REPO_ROOT/.venv"
PYTEST="$VENV/bin/pytest"
PYTHON="$VENV/bin/python"

MODE="${1:-changed}"
WITH_E2E=0
[[ "${2:-}" == "--with-e2e" ]] && WITH_E2E=1

FAIL_COUNT=0
PASS_COUNT=0
SKIP_COUNT=0

# ── colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}[PASS]${RESET} $*"; ((PASS_COUNT++)) || true; }
fail() { echo -e "${RED}[FAIL]${RESET} $*"; ((FAIL_COUNT++)) || true; }
skip() { echo -e "${YELLOW}[SKIP]${RESET} $*"; ((SKIP_COUNT++)) || true; }
info() { echo -e "       $*"; }

# ── repo-root check ───────────────────────────────────────────────────────────
cd "$REPO_ROOT"

echo ""
echo "============================================================"
echo "  Fantasy Football Pi — Local Pre-PR Gate"
echo "  Mode: $MODE  |  E2E: $( [[ $WITH_E2E -eq 1 ]] && echo enabled || echo disabled )"
echo "============================================================"
echo ""

# ── helper: detect changed lanes ─────────────────────────────────────────────
changed_files() {
    # Files changed vs main (staged + unstaged + untracked)
    {
        git diff --name-only HEAD 2>/dev/null
        git diff --name-only --cached 2>/dev/null
        git ls-files --others --exclude-standard 2>/dev/null
    } | sort -u
}

backend_changed() {
    changed_files | grep -qE '^backend/' && return 0
    changed_files | grep -qE '^db/'      && return 0
    return 1
}

frontend_changed() {
    changed_files | grep -qE '^frontend/' && return 0
    return 1
}

etl_changed() {
    changed_files | grep -qE '^etl/' && return 0
    return 1
}

# ── 1. Python environment check ───────────────────────────────────────────────
echo "── Python environment ──────────────────────────────────────"
if [[ ! -x "$PYTEST" ]]; then
    fail "pytest not found at $PYTEST — activate venv or run: python -m venv .venv && pip install -r backend/requirements.txt"
else
    ok "pytest available: $($PYTEST --version 2>&1 | head -1)"
fi

# ── 2. Node environment check ─────────────────────────────────────────────────
echo ""
echo "── Node environment ────────────────────────────────────────"
if ! command -v node &>/dev/null; then
    fail "node not found in PATH"
elif [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
    fail "frontend/node_modules missing — run: cd frontend && npm install"
else
    ok "node $(node --version), node_modules present"
fi

# ── 3. Backend tests ──────────────────────────────────────────────────────────
echo ""
echo "── Backend tests (pytest) ──────────────────────────────────"
RUN_BACKEND=0
if [[ "${SKIP_BACKEND:-0}" == "1" ]]; then
    skip "backend (SKIP_BACKEND=1)"
elif [[ "$MODE" == "full" ]]; then
    RUN_BACKEND=1
elif backend_changed; then
    RUN_BACKEND=1
    info "backend/ or db/ changes detected"
else
    skip "backend (no changed files in backend/ or db/)"
fi

if [[ $RUN_BACKEND -eq 1 ]]; then
    if [[ ! -x "$PYTEST" ]]; then
        fail "backend — skipped (pytest not available)"
    elif "$PYTEST" backend/tests/ -q --tb=short 2>&1; then
        ok "backend tests"
    else
        fail "backend tests — see output above"
    fi
fi

# ── 4. Frontend tests ─────────────────────────────────────────────────────────
echo ""
echo "── Frontend tests (vitest) ─────────────────────────────────"
RUN_FRONTEND=0
if [[ "${SKIP_FRONTEND:-0}" == "1" ]]; then
    skip "frontend (SKIP_FRONTEND=1)"
elif [[ "$MODE" == "full" ]]; then
    RUN_FRONTEND=1
elif frontend_changed; then
    RUN_FRONTEND=1
    info "frontend/ changes detected"
else
    skip "frontend (no changed files in frontend/)"
fi

if [[ $RUN_FRONTEND -eq 1 ]]; then
    if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
        fail "frontend — skipped (node_modules missing)"
    elif (cd frontend && npm run test -- --run 2>&1); then
        ok "frontend tests"
    else
        fail "frontend tests — see output above"
    fi
fi

# ── 5. ETL tests ──────────────────────────────────────────────────────────────
echo ""
echo "── ETL tests (pytest) ──────────────────────────────────────"
RUN_ETL=0
if [[ "${SKIP_ETL:-0}" == "1" ]]; then
    skip "etl (SKIP_ETL=1)"
elif [[ "$MODE" == "full" ]]; then
    RUN_ETL=1
elif etl_changed; then
    RUN_ETL=1
    info "etl/ changes detected"
else
    skip "etl (no changed files in etl/)"
fi

if [[ $RUN_ETL -eq 1 ]]; then
    if [[ ! -x "$PYTEST" ]]; then
        fail "etl — skipped (pytest not available)"
    elif "$PYTEST" etl/ -q --tb=short --ignore=etl/test_fantasynerds_preprod.py --ignore=etl/test_yahoo_preprod.py 2>&1; then
        ok "etl tests"
    else
        fail "etl tests — see output above"
    fi
fi

# ── 6. E2E tests (future) ─────────────────────────────────────────────────────
echo ""
echo "── E2E tests ───────────────────────────────────────────────"
if [[ $WITH_E2E -eq 1 ]]; then
    skip "e2e — no E2E suite configured yet (planned: issue #375)"
else
    skip "e2e (pass --with-e2e to enable when configured)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Summary: ${PASS_COUNT} passed  |  ${FAIL_COUNT} failed  |  ${SKIP_COUNT} skipped"
echo "============================================================"
echo ""

if [[ $FAIL_COUNT -gt 0 ]]; then
    echo -e "${RED}Pre-PR gate FAILED — fix the issues above before pushing.${RESET}"
    exit 1
else
    echo -e "${GREEN}Pre-PR gate passed.${RESET}"
    exit 0
fi
