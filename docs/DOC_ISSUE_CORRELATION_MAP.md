# Document-to-Issue Correlation Map

Updated: 2026-03-08
Tracker: #156

This table links key markdown documents to governing GitHub issues/epics so implementation and documentation stay synchronized.

| Document | Primary Purpose | Related Issue(s) |
|---|---|---|
| `docs/PROJECT_MANAGEMENT.md` | Current roadmap and story state guidance | #156, #154, #43, #100, #155 |
| `docs/ISSUE_STATUS.md` | Story status and closure hygiene tracking | #156, #154, #24, #22, #93 |
| `PROJECT_MANAGEMENT.md` | Root-level roadmap mirror for contributors | #156 |
| `ISSUE_STATUS.md` | Root-level issue status mirror | #156 |
| `docs/SCORING_EDGE_CASE_TEST_MATRIX.md` | Concrete scoring edge-case matrix and coverage state | #43, #100, #155 |
| `docs/CLI_CHECKIN_LESSONS_LEARNED.md` | Operational learnings and break/fix guardrails | #156 |
| `docs/TESTING_SESSION_SUMMARY.md` | Historical testing snapshot (not source of current status) | #156 |
| `docs/PR_NOTES.md` | Close-out notes and PR/session evidence | #156, #22, #93, #24 |
| `docs/FRONTEND_UI_STANDARDS.md` | Shared UI/layout/page token standards and alignment matrix | #163, #164, #74, #91, #92 |
| `RESPONSIVE_STANDARDS.md` | Responsive breakpoint and mobile-first layout policy | #163, #164, #91, #92 |
| `docs/UI_REFERENCE.md` | Consolidated UI implementation reference and practical patterns | #163, #164, #74 |
| `docs/PATTERN_LIBRARY.md` | Canonical repository for cross-cutting implementation patterns and contracts | #333, #307, #156 |
| `docs/PATTERN_COMPLIANCE_MATRIX.md` | Short-term and long-term pattern compliance tracking matrix | #334, #333 |
| `docs/PATTERN_STANDARDIZATION_PLAN.md` | Phased plan for pattern compliance regression checks and convergence | #334, #333 |
| `docs/DEPENDENCY_MAINTENANCE.md` | Dependency hygiene process | #113 |
| `docs/SECURITY_HARDENING.md` | Security hardening standards | #113 |

## Maintenance Rule
- When a document's operational behavior changes, update this map in the same PR/commit and reference the related issue IDs.
- If no related issue exists for a doc-impacting change, create one before merge to prevent drift.
