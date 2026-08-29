# Agent Catalog Consumer Bootstrap Plan

## Scope

This repo is enrolled as a consumer of `NPGrant81/agent-catalog@v0.2.1` using local control surfaces only.

Included in this slice:

- `agent_catalog.lock.json`
- `sync_agents.ps1`
- `.github/workflows/agent-catalog-guard.yml`
- this local plan file

Excluded from this slice:

- business logic changes
- skill migration
- fabricated `.github/agents/*.agent.md` payloads

## Sync Status

The repo is enrolled with non-deferred sync enabled.

- Approved source `NPGrant81/agent-catalog@v0.2.1` is available locally.
- Local sync validates configuration and materializes only lock-managed payloads.
- Managed payloads are copied from source and not fabricated locally.

## Ownership Policy

Catalog owns `.github/agents/*.agent.md` in active mode.

- Check mode reports unmanaged `.agent.md` files as a contract violation.
- Active sync removes unmanaged `.agent.md` files before copying lock-managed payloads.

## Unlock Condition

Unlock condition is satisfied.

1. catalog source for `NPGrant81/agent-catalog@v0.2.1` is available to the local operator
2. deferred mode was removed by approved follow-up work

## First Real Sync Path

Executed path:

1. approved source access was provided for `NPGrant81/agent-catalog@v0.2.1`
2. `sync_agents.ps1` now materializes only managed payloads declared in the lock file
3. guard-equivalent path and active sync were re-run in non-deferred mode

## Override Rationale Expectations

Any override that disables deferred mode should document:

- why source access is now approved
- which agent payloads are expected to be synced
- how drift against the declared catalog ref will be checked