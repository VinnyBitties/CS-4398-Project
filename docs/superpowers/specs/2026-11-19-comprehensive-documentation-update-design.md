# Comprehensive Documentation Update Design

## Intent

Reconcile Sentinel's complete documentation package with `dev-branch` as it exists on 2026-11-19. The update must cover repository-native Markdown, machine-readable evidence, documentation integrity tests, and all eight generated Microsoft Word records. It should let a new developer understand, run, verify, and safely evaluate the current prototype without confusing committed code with verified real-world capability.

The current package describes the repository as of 2026-11-03. Since then, the project has added a scan-history and detailed-results dashboard, static PE evidence rendering, multi-format file identification and content analysis, a synthetic behavioral-ML training and validation workflow, a dynamic telemetry service implementation, and an optional Groq explanation path. Those changes make several existing status statements and setup instructions materially inaccurate.

## Goals

- Audit current source, configuration, routes, pipeline stages, interfaces, tests, and narrow component documentation.
- Update the root entry point, project overview, architecture, setup and operations guide, prototype status, documentation index, and all six component records.
- Reconcile the backend API and component documentation where exact fields, stages, or setup instructions have changed.
- Update `docs/documentation-evidence.json` so every status and limitation cites current repository evidence.
- Update documentation tests to detect the new stage inventory, current date, component paths, navigation, local links, generated Word content, and cross-format drift.
- Update the Word-form generator and regenerate all eight existing `.docx` records from the same evidence model.
- Record fresh verification results, distinguishing passing tests, blocked tests, structural checks, and capabilities that were not exercised.
- Preserve unrelated user changes and avoid touching product code.

## Non-goals

- Fix product bugs, redesign interfaces, or change runtime behavior found during the audit.
- Assert that real malware can be detonated safely or that the committed sandbox has passed containment, transfer, cleanup, or live-telemetry validation.
- Present synthetic ML fixtures or their metrics as real-world detector accuracy.
- Add a static-PE machine-learning stage that does not exist in the backend pipeline.
- Invent approvals, milestones, model quality, data provenance, production deployment details, or MITRE ATT&CK mappings.
- Merge work from other branches such as `EasyStart` or `StaticFeatures/README-Diego` that is not contained in the current `dev-branch`.
- Resolve repository-wide CRLF-only working-tree changes outside files intentionally updated for documentation.

## Anti-goals

- A cosmetic date bump that leaves old architectural claims in place.
- Documentation that calls a checked-in service "integrated" merely because source exists.
- Setup steps that encourage real-malware use before containment is independently validated.
- Duplicate explanations that drift from the API contract, report contract, or component-specific README.
- Word records whose statuses or verification claims differ from the Markdown evidence package.

## Current Evidence Requiring Reconciliation

### Frontend

- `website/dashboard/reports.js`, `reports-data.js`, and `static-evidence.js` now load paged history, poll active scans, render behavioral summaries, and display detailed PE evidence.
- Home now accepts a broad, explicit list of executable, Office, PDF, script, source, archive, shortcut, and web extensions, while the server identifies content from bytes.
- Node data-model tests and Playwright browser tests are present, including a real-backend/inert-fixture workflow.
- The report UI still does not provide a generic renderer for every stage, and its main stage summary omits the new `file_type` and `content_analysis` stages.

### Backend and static/content analysis

- The default file pipeline is now `signature`, `file_type`, then predicate-gated `static_analysis` and/or `content_analysis`; unknown classifications currently run both. Optional `sandbox`, `behavioral_ml`, and `llm` stages follow.
- `backend/scripts/content_analyze.py` identifies and statically inspects numerous non-PE formats with bounded reads and optional archive/macro dependencies.
- Static ML remains absent from the registered pipeline.
- The backend API contract already contains much of the new file/content-stage detail but has stale LLM wording and must be checked against runtime output.

### Behavioral machine learning

- The repository now includes reproducible synthetic-report generation, strict dataset export, stratified train/validation/test splitting, classifier and anomaly training, validation-only threshold tuning, artifact/schema metadata, and an end-to-end saved-model HTTP test.
- Synthetic data and synthetic evaluation remain development evidence, not real malware performance evidence.
- No trained artifact or real dataset is committed, and FR03's static-PE classifier remains absent.

### Dynamic analysis

- `dynamic_telemetry/` now contains a FastAPI service, KVM/QEMU and snapshot commands, Sysmon EVTX parsing, a client example, dependency manifest, and systemd unit.
- Presence of this implementation supersedes the old claim that the service is absent.
- Source inspection does not prove a working sample-transfer or EVTX-export path, live detonation, containment, network policy, or reliable snapshot cleanup. Documentation must classify it as present but not safely or operationally verified.
- The committed README and example expose a fixed service address and deployment-specific paths; these must be described as environment-specific examples, not portable defaults.

### LLM and threat intelligence

- `llm-threat-intelligence/` now provides demo indicator validation and a Groq-backed explanation using model `openai/gpt-oss-20b` when `GROQ_API_KEY` is present.
- The backend bridge returns prompt and demo threat intelligence even when explanation is skipped or errors, so missing credentials do not fail the stage.
- ATT&CK mapping, versioned output schema, evidence citations, production intelligence feeds, prompt-injection controls, and provider evaluation remain absent.

## Status and Evidence Rules

- Continue using only: `Implemented`, `Integrated`, `Partial`, `Stubbed/configurable`, `Planned/not present`, and `Not verified`.
- A source implementation may be `Partial` or `Not verified` even if it has a runnable entry point.
- `Integrated` requires both producer and consumer paths in the current branch plus an exercised contract or test; it does not imply production readiness.
- Historical results remain labeled historical. Only commands run during this update may be reported as current verification.
- Synthetic ML results must always be labeled synthetic and must not support accuracy claims.
- Sandbox safety requires evidence beyond source presence. Until inert live tests and containment review exist, documentation must prohibit real-malware use.
- Missing evidence is never translated into a benign verdict, a zero score, or a successful stage.
- Unknown team decisions use `Not recorded`, `Not available in this branch`, or `Requires team confirmation`.

## Approaches Considered

### Comprehensive evidence-driven reconciliation — selected

Audit current behavior, revise the normalized evidence model, update every affected Markdown and narrow contract, extend documentation tests, and regenerate all Word records. This is the most work, but it is the only approach that satisfies the requested full-scale update without leaving contradictory submission artifacts.

### Markdown-only reconciliation

Update developer-facing prose and contracts but leave evidence automation and Word records unchanged. This would be faster, but it would immediately leave the repository's submission package internally inconsistent.

### Full documentation rewrite

Replace the existing information architecture and generator with a new documentation system. This could reduce historical complexity, but it would discard working traceability and Word-template automation without a demonstrated need.

## Documentation Deliverables

### Core Markdown

- `README.md`: current capabilities, safe quick start, default stages, optional integrations, verification summary, limitations, and navigation.
- `docs/project-overview.md`: baseline intent versus current scope, requirements, stack, responsibilities, and updated evidence date.
- `docs/architecture.md`: current stage routing, multi-format analysis, dashboard/report flow, optional services, persistence, failure behavior, and deployment/safety boundaries.
- `docs/setup-and-operations.md`: platform prerequisites, dependencies, default startup, content analysis, real PE analysis, ML workflow/service, optional LLM, sandbox prerequisites, tests, cleanup, and troubleshooting.
- `docs/prototype-status.md`: current component maturity, FR/NFR traceability, integration matrix, fresh verification, risks, and deferred work.
- `docs/documentation-index.md`: authoritative-source map and regenerated Word-record mapping.

### Component and narrow documentation

- Update all six files under `docs/components/`.
- Reconcile `backend/README.md`, `backend/docs/api-contract.md`, and other narrow backend documents only where current source proves them stale.
- Reconcile `ML/SYNTHETIC_DATA.md`, `dynamic_telemetry/README.md`, `llm-threat-intelligence/README.md`, and their status/handoff documents where necessary to prevent setup or capability contradictions.
- Preserve `malware_detection/` contracts when unchanged; update links or integration notes only when needed.

### Evidence, automation, and Word records

- Update `docs/documentation-evidence.json` to the 2026-11-19 snapshot and cite newly present source/tests.
- Extend `tests/documentation/test_documentation.py` for the current stage/component inventory, date/change IDs, required claims and warnings, link integrity, and cross-format consistency.
- Update `scripts/update_documentation_forms.py` to generate the new snapshot date, change identifiers, component summaries, verification record, and limitations idempotently.
- Regenerate the existing eight `Sentinel_*.docx` records in place and structurally validate their Office Open XML packages.

## Implementation Method

1. Establish the code delta from the 2026-11-03 documentation commit and inspect every changed subsystem.
2. Run a baseline verification inventory without changing product dependencies unless already available.
3. Update documentation tests first where the old assertions encode stale facts.
4. Reconcile the evidence JSON and core/component Markdown against source.
5. Reconcile narrow contracts and setup documents, favoring links over duplicated field-by-field prose.
6. Update the Word generator, regenerate all forms, and check idempotence.
7. Run the full documentation suite, relevant backend/ML/static-analysis tests that the environment supports, and structural Word validation.
8. Inspect meaningful diffs with line-ending whitespace ignored so unrelated CRLF churn is not mistaken for authored work.

## Verification

- `python3 -m unittest discover -s tests/documentation -v`
- `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`
- `python3 -m unittest discover -s tests/contribution_tracker -v`
- `python3 -B -m unittest discover -s ML -p 'test_*.py' -v`
- `python3 -m unittest discover -s malware_detection/tests -v`
- `npm test` from `backend/`
- `npm run test:dashboard` from `backend/` when a compatible Playwright browser is installed
- Markdown local-link validation and extracted Word-text checks through the documentation suite
- Final `git diff --check`, changed-file review, and search for stale `2026-11-03` current-state claims or statements that present the new services as absent

If a command is blocked by missing dependencies, browser binaries, platform restrictions, or unavailable external services, the final record will state the exact blocker and will not convert it into an assertion failure or passing result.

## Acceptance Criteria

- All current pipeline stages and routing rules are accurately documented.
- Frontend report history, detailed static evidence, browser tests, and multi-format upload behavior are represented without overstating full-stage rendering.
- The synthetic ML workflow is reproducible from documented commands and clearly separated from real-world model validation.
- Dynamic-service source is acknowledged, while containment, transfer, telemetry export, and live-operation gaps remain explicit.
- Optional Groq behavior, model name, failure fallback, demo threat intelligence, and missing ATT&CK mapping are accurately recorded.
- FR01-FR08 and all named NFRs have current, evidence-backed statuses in JSON, Markdown, and the project-wide Word record.
- All eight Word records are regenerated without duplicate change rows or unresolved response placeholders.
- Documentation integrity tests and all available relevant project tests have fresh, honestly reported results.
- No product code, secrets, malware samples, generated datasets, model artifacts, or unrelated working-tree changes are introduced.

## Builder Calls

- Exact prose compression and table layout, provided all evidence and cautions remain.
- Whether a narrow fact belongs in a component page or is linked to its authoritative README/contract.
- Final component maturity labels when multiple vocabulary terms could apply, provided the chosen label is justified by current source and verification evidence.
- Which optional test suites are feasible in the current environment without changing the user's dependency setup.
