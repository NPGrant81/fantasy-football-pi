# Documentation Governance Sweep

This directory defines the timed review sweep for documentation currency.

## Files

- `doc_review_registry.json`: review cadence registry for key documentation files.

Current registry scope includes architecture, roadmap/status, UI standards,
data quality, deployment and cloudflare runbooks, security hardening,
CI observability, API page matrix, doc-issue mapping, dev environment notes,
and testing session summary.

## Steady-State Cadence

### Weekly

- Run `python -m scripts.docs_review_sweep --warn-days 14`
- Triage due-soon and overdue docs
- Update `last_reviewed` in `doc_review_registry.json` for completed reviews

### Monthly

- Run `python -m scripts.repo_hygiene_check`
- Review owner/cadence outliers in `doc_review_registry.json`
- Sample recent PRs for pattern-impact declaration compliance

### Quarterly

- Re-evaluate classification guardrails for taxonomy drift
- Re-assess archive candidates and move stale historical docs as needed
- Refresh long-term maintenance rows in pattern compliance tracking docs

## Registry Format

Each item must include:

- `path`: repository-relative document path
- `owner`: owning team/function label
- `cadence_days`: maximum days between reviews
- `last_reviewed`: ISO date (`YYYY-MM-DD`) when the document was last reviewed

Example:

```json
{
  "path": "docs/ARCHITECTURE.md",
  "owner": "engineering",
  "cadence_days": 90,
  "last_reviewed": "2026-03-21"
}
```

## Local Commands

Run the timed review sweep:

```bash
python -m scripts.docs_review_sweep --warn-days 14
```

Run full governance checks (same core checks used by scheduled CI):

```bash
python -m scripts.repo_hygiene_check
python -m scripts.docs_review_sweep --warn-days 14
python -m scripts.refresh_docs_index
git diff --exit-code docs/INDEX.md
```

## CI Schedule

The workflow `.github/workflows/docs-governance-sweep.yml` runs:

- every Monday at 13:00 UTC
- on manual dispatch

When checks fail, the workflow automatically creates or updates a GitHub issue
named `Docs Governance Sweep Failure` with the latest report and run link.

It fails when:

- governed docs are overdue for review
- required governed docs are missing
- docs index is not current
- repository hygiene checks fail

## Definition Of Healthy

- Governance coverage remains complete for active scoped docs
- No unclassified docs introduced
- Docs sweep and hygiene checks pass consistently

## Updating After Review

After reviewing a governed document, update its `last_reviewed` date in
`doc_review_registry.json` to the review day (`YYYY-MM-DD`).
