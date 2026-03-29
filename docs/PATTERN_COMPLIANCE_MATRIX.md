# Pattern Compliance Matrix

Updated: 2026-03-29
Owner: engineering
Tracking issues: #334, #333

## Purpose

Provide a single matrix for:

1. Verifying current compliance against defined standards.
2. Tracking short-term remediation progress.
3. Managing long-term maintenance cadence.

## Baseline Verification Snapshot

| Check | Current Result | Interpretation |
|---|---|---|
| `python -m scripts.repo_hygiene_check` | PASS | Scoped pattern and repo standards checks are healthy. |
| `python -m scripts.docs_review_sweep --warn-days 14` | PASS | Governed docs are fresh under current cadence thresholds. |
| Docs governance coverage | 85 / 85 (100.0%) | Full markdown governance coverage achieved, including archive scope. |

## Matrix: Short-Term Remediation (0-6 weeks)

Use this section to drive active remediation and sprint planning.

| Domain | Standard / Pattern | Current Coverage | Gap Type | Criticality | Short-Term Target | Owner | Verification Gate |
|---|---|---:|---|---|---|---|---|
| Backend rules | Commissioner deadline helper pattern | Scoped: trade + waiver | Coverage breadth | High | Extend to all deadline-gated flows touched this cycle | backend | `python -m scripts.repo_hygiene_check`; targeted pytest |
| Docs governance | Governed docs registry coverage | 100.0% | Steady-state maintenance | Low | Maintain 100% by failing hygiene checks on missing/uncategorized docs | product + engineering | `python -m scripts.repo_hygiene_check`; `python -m scripts.docs_review_sweep --warn-days 14` |
| PR governance | Pattern impact declaration | Enabled via PR template | Adoption discipline | Medium | 100% usage for cross-cutting PRs | reviewers | PR review checklist |
| Pattern lifecycle | Proposal + decision logging | In place | Process consistency | Medium | Ensure new cross-cutting patterns include decision log updates | engineering | diff checks on `docs/patterns/*` |
| Observability | Invalid deadline fallback logging | Implemented in helper | Expansion scope | Medium | Add log assertions where new fallback paths are introduced | backend | pytest log assertions |

### Initial Ungoverned Operational Docs Triage (first 15)

Use this table as the immediate remediation backlog for the current cycle.

| Document | Domain | Criticality | Status | Target Window | Owner | Why this level | Verification |
|---|---|---|---|---|---|---|---|
| `docs/API_INTEGRATION_PIPELINE.md` | API/contract | Critical | complete | 2026-04-05 | backend | Can misalign integration behavior if stale | Verified against `.github/workflows/ci.yml` (`api-integration`, `CI Observability Report`) and `backend/tests/test_api_integration_pipeline.py` references |
| `docs/API_PAGE_MATRIX.md` | API/contract | Critical | complete | 2026-04-05 | backend | Debug/reference matrix used for API-page coupling | Spot-checked endpoint mappings (`/trades/propose`, `/trades/pending`, `/waivers/claim`, `/players/waiver-wire`) against current routers |
| `docs/DEPLOYMENT_WORKFLOWS.md` | operations | High | complete | 2026-04-12 | platform | Used in deploy paths; drift can cause failed rollout | Verified workflow files and secret keys in `.github/workflows/deploy-staging.yml`, `.github/workflows/deploy-production.yml`, `.github/workflows/source-prechecks.yml` |
| `docs/RASPBERRY_PI_DEPLOYMENT.md` | operations | High | complete | 2026-04-12 | platform | Host setup/maintenance impact on production-like env | Verified referenced helper path `scripts/pi_update_plan.sh` and deploy/systemd/nginx/cloudflared artifact paths exist |
| `docs/CLOUDFLARE_TUNNEL_SETUP.md` | networking/ops | High | complete | 2026-04-12 | platform | Connectivity and ingress reliability impact | Verified referenced Cloudflare tunnel docs and deploy/systemd/cloudflared assets exist and are aligned to current repo paths |
| `docs/LIVE_SCORING_RELIABILITY_RUNBOOK.md` | runtime reliability | High | complete | 2026-04-12 | platform + backend | Incident handling guide must match system behavior | Verified live-score ingest and watchdog endpoints in `backend/routers/admin_tools.py` |
| `docs/DATA_QUALITY_RUNBOOK.md` | data quality | High | complete | 2026-04-19 | backend/data | Quality controls are operationally sensitive | Verified referenced guardrail test modules exist in `backend/tests` |
| `docs/DATA_VALIDATION_STRATEGY.md` | data validation | High | complete | 2026-04-19 | backend/data | Strategy drift can invalidate guardrails | Verified validation service functions and ETL validation hooks in `backend/services/validation_service.py` and `etl/load/load_to_postgres.py` |
| `docs/DB_MIGRATION_PHASE1.md` | data migration | High | complete | 2026-04-19 | backend/data | Migration guidance affects schema safety | Verified Alembic cutover settings in `backend/alembic.ini` (`script_location`/`version_locations` -> `db`) |
| `docs/PLAYER_API_FILTERING.md` | API behavior | High | complete | 2026-04-19 | backend | Behavior contract for user-facing filtering | Verified `ALLOWED_POSITIONS` usage in import/service/router code paths (`backend/scripts/import_espn_players.py`, `backend/services/player_service.py`, `backend/routers/players.py`) |
| `docs/SCORING_EDGE_CASE_TEST_MATRIX.md` | QA/testing | Medium | complete | 2026-04-26 | qa + backend | Test planning drift risk; lower immediate blast radius | Registry entry added; spot-checked listed test modules/scenarios align to `backend/tests/test_scoring_engine_service.py` and scoring integration suite references |
| `docs/CROSS_MODULE_EDGE_CASE_TEST_MATRIX.md` | QA/testing | Medium | complete | 2026-04-26 | qa + backend | Cross-module validation planning artifact | Registry entry added; spot-checked listed test references align to current router/service test modules |
| `docs/DRAFT_ANALYZER_API_AUDIT.md` | audit/reference | Medium | complete | 2026-04-26 | backend + frontend | Important for analyzer parity but less operationally urgent | Registry entry added; endpoint inventory and dataset health sections reviewed against current draft/advisor/player routes |
| `docs/ISSUE_STATUS.md` | project governance | Medium | complete | 2026-05-03 | product | Status drift impacts planning confidence | Registry already present; manual audit completed and tracked in governance cadence |
| `docs/PROJECT_MANAGEMENT.md` | project governance | Medium | complete | 2026-05-03 | product | Delivery planning baseline document | Registry already present; manual audit completed and tracked in governance cadence |

### Ungoverned Operational Docs Triage (wave 2)

Second onboarding wave focused on governance process docs, CI reliability docs, Cloudflare operating docs, and MFL data migration operating docs.

| Document | Domain | Criticality | Status | Target Window | Owner | Why this level | Verification |
|---|---|---|---|---|---|---|---|
| `docs/INDEX.md` | docs governance | High | complete | 2026-04-05 | engineering | Primary map for discoverability and stale-doc prevention | Verified referenced governance scripts (`scripts/docs_review_sweep.py`, `scripts/repo_hygiene_check.py`, `scripts/refresh_docs_index.py`) and workflow (`.github/workflows/docs-governance-sweep.yml`) exist |
| `docs/governance/README.md` | docs governance | High | complete | 2026-04-05 | engineering | Defines ownership and cadence contract for governed docs | Verified registry path and governance scripts/workflow references are current |
| `docs/DOCUMENTATION_UPDATE_PROCESS_PLAN.md` | docs governance | Medium | complete | 2026-04-12 | engineering | Process alignment artifact; lower runtime blast radius | Verified conflict-check and archival references align to current governance scripts and `docs/archive/` structure |
| `docs/DEPENDENCY_MAINTENANCE.md` | backend reliability | High | complete | 2026-04-12 | backend | Dependency drift can break CI/runtime unexpectedly | Verified dependency scripts in `backend/scripts/`, lock/requirements files, and `.github/workflows/dependency-check.yml` |
| `docs/BACKEND_CI_PIPELINE_OPTIMIZATION.md` | CI reliability | High | complete | 2026-04-12 | backend | CI optimization guidance impacts backend signal quality | Verified backend CI steps in `.github/workflows/ci.yml` and `.flake8` presence |
| `docs/FRONTEND_CI_PIPELINE_OPTIMIZATION.md` | CI reliability | High | complete | 2026-04-12 | frontend | CI guidance impacts frontend test quality gates | Verified frontend CI job and lint/type/test script references in `.github/workflows/ci.yml` |
| `docs/UI_UX_AUTOMATION_PIPELINE.md` | QA automation | High | complete | 2026-04-19 | qa | Automation drift risks UI regression blind spots | Verified `.github/workflows/ui-ux-automation.yml`, Cypress specs, and visual guard script exist |
| `docs/MFL_HISTORICAL_DATA_OPERATIONS.md` | data operations | High | complete | 2026-04-19 | data | Operational runbook for historical import pipeline | Verified `backend/manage.py` MFL commands and archive/manifest export directories |
| `docs/data-migration/README.md` | data migration | Medium | complete | 2026-04-19 | data | Index doc for migration workflow continuity | Verified linked migration docs and `scaffold-mfl-manual-csv` command |
| `docs/data-migration/mfl-migration-runbook.md` | data migration | High | complete | 2026-04-19 | data | Procedural runbook directly affects migration correctness | Verified `extract-mfl-history`, `import-mfl-csv`, `reconcile-mfl-import`, and `scaffold-mfl-manual-csv` CLI commands |
| `docs/data-migration/mfl-year-status-matrix.md` | data migration | Medium | complete | 2026-04-26 | data | Tracking aid for yearly coverage; lower immediate blast radius | Verified referenced `backend/exports/history_*` directories and year coverage artifacts |
| `docs/cloudflare-pi-handoff-checklist.md` | platform operations | High | complete | 2026-04-26 | platform | Handoff checklist affects deployment continuity | Verified `scripts/pi_update_plan.sh` and cloudflared config template paths |
| `docs/cloudflare-tunnel-cli.md` | platform networking | High | complete | 2026-04-26 | platform | Tunnel CLI operations can impact ingress health | Verified CLI config templates and systemd/watchdog assets in `deploy/systemd/` |
| `docs/cloudflare-tunnel-monitoring.md` | platform networking | High | complete | 2026-04-26 | platform | Monitoring guidance affects incident detection quality | Verified monitoring-related cloudflared templates and watchdog service files |
| `docs/cloudflare-tunnel-systemd.md` | platform networking | High | complete | 2026-04-26 | platform | Service management drift can cause tunnel downtime | Verified cloudflared systemd unit templates and installer script |

### Ungoverned Operational Docs Triage (wave 3)

Third onboarding wave focused on data contracts, MFL migration verification docs, and restore/runtime operations docs.

| Document | Domain | Criticality | Status | Target Window | Owner | Why this level | Verification |
|---|---|---|---|---|---|---|---|
| `docs/data_source_audit_issue_102.md` | data quality | High | complete | 2026-04-12 | data | Source audit traceability affects data trust in downstream pipelines | Verified backend data source inventory files in `backend/data/` are present and aligned |
| `docs/data-migration/mfl-data-requirements.md` | data migration | High | complete | 2026-04-12 | data | Requirements define expected year-level extraction/import coverage | Verified manage CLI command references in `backend/manage.py` and expected export structures |
| `docs/data-migration/mfl-extraction-matrix.md` | data migration | High | complete | 2026-04-12 | data | Extraction matrix guides reliable capture strategy per source/era | Verified extraction commands and `backend/exports/` history artifacts |
| `docs/data-migration/mfl-hardening-verification-gates.md` | data migration | High | complete | 2026-04-19 | qa + data | Verification gates protect import hardening quality | Verified validation/reconciliation command set in `backend/manage.py` |
| `docs/data-migration/mfl-html-records-normalization-plan.md` | data migration | Medium | complete | 2026-04-19 | data | Normalization guidance supports stable long-run ingestion quality | Verified HTML record export artifacts and normalization-plan references |
| `docs/data-migration/mfl-test-results-log.md` | migration QA | Medium | complete | 2026-04-19 | qa | Test outcome ledger is important for migration confidence trend | Verified command and export evidence path references |
| `docs/player-metadata-rules.md` | backend data contract | Medium | complete | 2026-04-26 | backend | Metadata contract drift affects player identity consistency | Verified player models/services and Alembic references |
| `docs/restore.md` | operations reliability | High | complete | 2026-04-26 | platform | Restore runbook drift increases recovery-time risk | Verified backup scripts, systemd deployment assets, and health endpoint references |
| `docs/pi-setup/docker.md` | platform setup | Medium | complete | 2026-04-26 | platform | Setup baseline for Pi environment consistency | Verified procedural steps remain aligned with current deployment layout |
| `docs/data-dictionary.md` | data contract | High | complete | 2026-04-26 | data | Canonical schema/legacy import field scope needed tightening to avoid confusion | Completed doc correction: explicitly separated legacy CSV ingestion contracts from canonical ORM runtime entities and clarified naming expectations |

### Ungoverned Operational Docs Triage (wave 4)

Fourth onboarding wave focused on planning/milestone governance and historical planning artifacts.

| Document | Domain | Criticality | Status | Target Window | Owner | Why this level | Verification |
|---|---|---|---|---|---|---|---|
| `docs/milestones/README.md` | planning governance | Medium | complete | 2026-04-12 | product | Milestone index drives cross-document planning consistency | Verified dependency chain and references to foundational docs are present and coherent |
| `docs/milestones/milestone-2-cross-platform-deployment.md` | platform planning | Medium | complete | 2026-04-12 | platform | Deployment sequencing document for milestone execution | Verified dependency links and supporting doc references are structurally aligned |
| `docs/milestones/milestone-3-security-hardening.md` | security planning | Medium | complete | 2026-04-12 | security | Security sequencing and issue decomposition artifact | Verified dependency and linked security documentation references are coherent |
| `docs/milestones/milestone-1-core-foundation.md` | planning governance | Medium | complete | 2026-04-19 | product | Foundational milestone status clarity affects downstream roadmap confidence | Added explicit status metadata and checklist-evidence hygiene guidance to remove status ambiguity |
| `docs/milestones/milestone-4-data-validation.md` | data planning | Medium | complete | 2026-04-19 | data | Validation milestone includes broad dependency chain and acceptance gates | Added explicit status metadata and standardized checklist semantics for evidence-based completion |
| `docs/milestones/milestone-5-gameplay-logic.md` | gameplay planning | Medium | complete | 2026-04-19 | backend | Gameplay milestone references completed stories without consistent trace links | Removed ambiguous completion markers and normalized note language to neutral workstream references |
| `docs/milestones/milestone-6-production-readiness.md` | release planning | Medium | complete | 2026-04-19 | platform | Production readiness gating is sensitive to status clarity | Replaced emoji status claims with neutral references and added explicit status metadata |
| `docs/milestones/milestone-7-release-1.0.md` | release planning | Medium | complete | 2026-04-26 | product | Release gate document drives final milestone confidence | Removed duplicated dependency-chain section, normalized dependency text, and added explicit status metadata |
| `docs/backlog_triage_2026-03-14.md` | project governance | Low | complete | 2026-04-26 | product | Historical triage snapshot can create planning confusion if treated as live source | Added historical-snapshot banner and canonical-source pointers for current backlog status |
| `docs/pr_notes.md` | engineering history | Low | complete | 2026-04-26 | engineering | PR recap doc is useful context but can drift from source-of-truth trackers | Added historical-snapshot banner and canonical-source pointers for live PR/issue state |

### Ungoverned Operational Docs Triage (wave 6)

Sixth onboarding wave focused on active UX/model docs plus UAT coverage docs and diagram governance.

| Document | Domain | Criticality | Status | Target Window | Owner | Why this level | Verification |
|---|---|---|---|---|---|---|---|
| `docs/UI_REFERENCE.md` | frontend standards | Medium | complete | 2026-04-12 | frontend | Canonical UI implementation reference affects consistency | Verified active standards content and implementation guidance alignment |
| `docs/ux-insights-spec.md` | product/UX | Medium | complete | 2026-04-12 | frontend | Insights vocabulary and thresholds guide analyzer UX behavior | Verified scope, issue linkage, and contract sections are current |
| `docs/model-serving-and-integration.md` | backend/model integration | High | complete | 2026-04-12 | backend | API/model serving contracts impact feature correctness | Verified request/response contracts, versioning, and fallback guidance |
| `docs/monte-carlo-simulation.md` | analytics/modeling | Medium | complete | 2026-04-12 | data | Simulation assumptions influence recommendation quality | Verified implementation paths and simulation constraints |
| `docs/permissions.md` | authorization policy | High | complete | 2026-04-12 | product | Permissions matrix governs critical access boundaries | Verified role matrix and testing guidance coverage |
| `docs/DRAFT_DAY_ADVISOR_MODE.md` | backend advisor behavior | Medium | complete | 2026-04-19 | backend | Advisor-mode contract guides endpoint and workflow behavior | Verified endpoint/event contract and operational constraints |
| `docs/RESPONSIVE_AUDIT_ENVIRONMENT.md` | frontend testing ops | Medium | complete | 2026-04-19 | frontend | Responsive audit setup impacts CI/dev parity quality | Verified environment instructions and CI runner alignment |
| `docs/uat/UAT_DECK_IMAGE_COVERAGE.md` | QA/UAT | Medium | complete | 2026-04-19 | qa | UAT slide coverage mapping is used for release verification | Verified slide-to-capture mapping and automation expectations |
| `docs/uat/UAT_MASTER_DOCUMENT_INSTRUCTIONS.md` | QA/UAT | Medium | complete | 2026-04-19 | qa | UAT authoring process controls execution quality and completeness | Verified template schema, rules, and execution workflow sections |
| `docs/diagrams/README.md` | engineering docs | Low | complete | 2026-04-26 | engineering | Diagram authoring standards reduce drift in visual architecture docs | Verified diagram inventory and authoring workflow guidance |

### Non-Essential Content Cleanup (wave 6)

| Document | Action | Status | Rationale |
|---|---|---|---|
| `docs/SESSION_COMPLETION_2026-03-21.md` | moved to `docs/archive/SESSION_COMPLETION_2026-03-21.md` | complete | Historical execution summary removed from top-level active doc surface |
| `docs/MARKDOWN_GOVERNANCE_SWEEP_REPORT.md` | moved to `docs/archive/MARKDOWN_GOVERNANCE_SWEEP_REPORT_2026-03-08.md` | complete | Superseded governance report archived to reduce active-document noise |

### Ungoverned Operational Docs Triage (wave 7)

Final onboarding wave closed the remaining markdown backlog and added automated classification guardrails.

| Document | Domain | Criticality | Status | Target Window | Owner | Why this level | Verification |
|---|---|---|---|---|---|---|---|
| `docs/CLI_CHECKIN_LESSONS_LEARNED.md` | engineering process | Low | complete | 2026-04-26 | engineering | Lessons-learned context for contributor workflow quality | Added to registry with cadence and ownership |
| `docs/PI_UPDATE_CHEATSHEET.md` | platform operations | Medium | complete | 2026-04-26 | platform | Operational cheat sheet used in Pi support flows | Added to registry with cadence and ownership |
| `docs/gaps/overview.md` | product planning | Low | complete | 2026-04-26 | product | Gap-analysis artifact requires periodic review to avoid stale direction | Added to registry with cadence and ownership |
| `docs/diagrams/draft-flow.md` | engineering diagrams | Low | complete | 2026-04-26 | engineering | Visual flow should stay aligned with current behavior | Added to registry with cadence and ownership |
| `docs/diagrams/ledger-model.md` | engineering diagrams | Low | complete | 2026-04-26 | engineering | Ledger diagram informs architecture communication | Added to registry with cadence and ownership |
| `docs/diagrams/simulation-pipeline.md` | engineering diagrams | Low | complete | 2026-04-26 | engineering | Simulation pipeline diagram needs managed refresh cadence | Added to registry with cadence and ownership |
| `docs/diagrams/waiver-flow.md` | engineering diagrams | Low | complete | 2026-04-26 | engineering | Waiver flow diagram supports shared mental model | Added to registry with cadence and ownership |
| `docs/patterns/PATTERN_PROPOSAL_TEMPLATE.md` | governance patterns | Medium | complete | 2026-04-26 | engineering | Pattern intake template must stay aligned with governance process | Added to registry with cadence and ownership |
| `docs/archive/commit-packages/2026-03-15-bundle-plan.md` | archive historical | Low | complete | 2026-04-26 | engineering | Archived bundle-plan artifact still requires low-frequency stewardship | Added to registry with archive cadence |
| `docs/archive/MARKDOWN_GOVERNANCE_SWEEP_REPORT_2026-03-08.md` | archive historical | Low | complete | 2026-04-26 | engineering | Archived governance snapshot retained as historical evidence | Added to registry with archive cadence |
| `docs/archive/SESSION_COMPLETION_2026-03-21.md` | archive historical | Low | complete | 2026-04-26 | engineering | Archived execution snapshot retained for traceability | Added to registry with archive cadence |
| `docs/governance/DOC_CLASSIFICATION_GUARDRAILS.md` | governance policy | High | complete | 2026-04-26 | engineering | Defines domain/type classification and drift warning triggers | Added guardrails doc and wired enforcement in hygiene checks |

## Matrix: Long-Term Maintenance (quarterly cadence)

Use this section to prevent drift after short-term remediation completes.

| Domain | Standard / Pattern | Maintenance Cadence | Health Signal | Trigger for Action | Owner |
|---|---|---|---|---|---|
| Pattern contracts | `docs/PATTERN_LIBRARY.md` currency | Monthly | No unresolved pattern drift findings | New cross-cutting behavior without mapped pattern | engineering |
| Decision traceability | `docs/patterns/PATTERN_DECISION_LOG.md` updates | Monthly | Decision log updated in same PR for pattern changes | Pattern PR missing decision entry | engineering |
| Docs governance breadth | Registry coverage trend | Quarterly | Coverage trend stable or increasing | Coverage drops or stale critical docs appear | product |
| Automated enforcement | Hygiene checks and docs sweep | Per CI run + weekly sweep | Stable pass rate | Repeated failures or bypass requests | platform |
| Review quality | Pattern-impact PR compliance | Monthly sample audit | >= 90% compliant PR samples | < 90% sample compliance | maintainers |

## Criticality Scale (for matrix triage)

- Critical: fix now (same sprint/hotfix)
- High: next sprint
- Medium: monthly batch
- Low: quarterly archive/defer

## Progress Monitoring Protocol

1. Weekly (short-term effort):
   - update short-term matrix rows with status and blockers
   - add newly discovered gaps
2. Monthly (steady state):
   - review long-term maintenance rows
   - refresh owner/cadence and health signals
3. Quarterly:
   - reassess standards scope
   - archive deprecated rows and add newly critical domains

## Suggested Status Markers

Add one status marker to each row as work progresses:

- `not-started`
- `in-progress`
- `blocked`
- `complete`
