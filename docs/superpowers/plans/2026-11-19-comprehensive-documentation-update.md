# Comprehensive Documentation Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile Sentinel's complete Markdown, evidence, automated checks, and eight Word records with `dev-branch` as of 2026-11-19.

**Architecture:** Keep `docs/documentation-evidence.json` as the normalized status and verification record. Core and component Markdown explain that evidence for developers; narrow READMEs/contracts retain exact subsystem instructions; `scripts/update_documentation_forms.py` projects the same facts into the existing Word templates; `tests/documentation/test_documentation.py` enforces cross-format consistency.

**Tech Stack:** Markdown, JSON, Python 3 standard library, `unittest`, Office Open XML (`.docx`), Mermaid, Node.js test runner, Playwright, scikit-learn/joblib, Python malware-analysis tests

**Spec:** `docs/superpowers/specs/2026-11-19-comprehensive-documentation-update-design.md`

## Global Constraints

- Describe only the current `dev-branch` snapshot dated `2026-11-19`; do not merge or document unmerged work from `EasyStart` or `StaticFeatures/README-Diego` as current behavior.
- Use only these maturity labels: `Implemented`, `Integrated`, `Partial`, `Stubbed/configurable`, `Planned/not present`, and `Not verified`.
- Do not modify product behavior or source code; findings about runtime defects become candid documentation limitations.
- Do not claim safe malware detonation, working containment, live sandbox telemetry, real-world ML accuracy, ATT&CK mapping, production threat intelligence, or provider evaluation without fresh evidence.
- Label all generated-data training/evaluation results as synthetic development evidence, never detector-performance evidence.
- Keep FR03 `Planned/not present`: no registered static-PE ML stage exists.
- Keep missing evidence distinct from benign, zero risk, a successful stage, or a passing test.
- Preserve all eight Word filenames and their existing historical rows; the new reconciliation row must use stable 2026-11-19 identifiers and remain idempotent.
- Preserve unrelated user changes. The worktree has pre-existing repository-wide CRLF-only changes; inspect authored changes with whitespace-at-EOL ignored and edit only approved documentation/tooling artifacts.
- Do not add secrets, malware samples, generated datasets, model artifacts, databases, uploads, browser binaries, or absolute workspace paths.
- Do not create commits unless the user explicitly requests them; use scoped test and diff checkpoints because the shared working tree is already dirty.

## Review Focus

- `dynamic_telemetry/` is present, but the docs must not imply that sample transfer, EVTX export, isolation, cleanup, or live detonation is verified.
- `llm-threat-intelligence/` can call Groq model `openai/gpt-oss-20b`, but missing credentials/errors are nonfatal and ATT&CK mapping remains absent.
- The reports UI is connected and tested, but its generic stage list omits `file_type` and `content_analysis`; detailed PE evidence is not a renderer for every report type.
- The ML workflow is reproducible on synthetic fixtures and has end-to-end tests, but no real dataset, committed trained artifact, held-out-family result, or static classifier exists.
- Current verification statements must match fresh command output; blocked or skipped suites must name the exact dependency, platform, browser, or external-service blocker.

---

### Task 1: Current Evidence Model and Documentation Guardrails

**Files:**
- Modify: `docs/documentation-evidence.json`
- Modify: `tests/documentation/test_documentation.py`

**Interfaces:**
- Consumes: current source/config/tests in `backend/`, `website/`, `ML/`, `dynamic_telemetry/`, `llm-threat-intelligence/`, and `malware_detection/`; existing evidence schema.
- Produces: the unchanged top-level evidence interface (`metadata`, `status_vocabulary`, `components`, `requirements`, `verification`, `risks`, `artifacts`) with a 2026-11-19 snapshot and current paths; tests that pin the new facts before prose and Word generation consume them.

- [ ] **Step 1: Run the current documentation suite as a baseline**

Run: `python3 -m unittest discover -s tests/documentation -v`

Expected: the current suite may pass because it encodes the stale 2026-11-03 package; record the exact count/result as baseline only.

- [ ] **Step 2: Update evidence tests to express the current snapshot**

In `DocumentationEvidenceTests`, add assertions that:

- `metadata.version_date == "2026-11-19"`.
- Frontend evidence cites `website/dashboard/reports.js`, `website/dashboard/static-evidence.js`, and browser/data tests.
- Backend evidence cites `file_type` and `content_analysis` source/tests.
- Dynamic evidence cites `dynamic_telemetry/api.py` but includes explicit unverified sample-transfer, EVTX-export, containment, and live-run limitations.
- LLM evidence cites `llm-threat-intelligence/llm_analyzer.py`, records Groq and `openai/gpt-oss-20b`, and keeps ATT&CK mapping absent.
- ML evidence cites the synthetic-data, split, threshold, metadata, training, and end-to-end modules while retaining real-data/artifact limitations.
- FR03 remains `Planned/not present`; every requirement and component still uses the controlled vocabulary.

- [ ] **Step 3: Run evidence tests to verify stale evidence fails**

Run: `python3 -m unittest tests.documentation.test_documentation.DocumentationEvidenceTests -v`

Expected: FAIL on the old date and missing current evidence/limitations.

- [ ] **Step 4: Reconcile `docs/documentation-evidence.json`**

Update all six component records, FR01-FR08, the five NFRs, verification records, risks, and artifact inventory. Reclassify source presence separately from verification; record frontend integration, multi-format static analysis, synthetic ML workflow, dynamic-service source with safety/operation gaps, and optional Groq output with missing ATT&CK mapping.

- [ ] **Step 5: Run evidence tests to verify the normalized record passes**

Run: `python3 -m unittest tests.documentation.test_documentation.DocumentationEvidenceTests -v`

Expected: PASS with no missing evidence paths or uncontrolled statuses.

- [ ] **Step 6: Inspect the Task 1 diff checkpoint**

Run: `git diff --ignore-space-at-eol -- docs/documentation-evidence.json tests/documentation/test_documentation.py`

Expected: only new evidence facts and their guardrail assertions; no product-code changes.

### Task 2: Core Documentation and System Navigation

**Files:**
- Modify: `README.md`
- Modify: `docs/project-overview.md`
- Modify: `docs/architecture.md`
- Modify: `docs/setup-and-operations.md`
- Modify: `docs/prototype-status.md`
- Modify: `docs/documentation-index.md`
- Modify: `tests/documentation/test_documentation.py`

**Interfaces:**
- Consumes: Task 1 evidence statuses/paths plus exact runtime contracts from `backend/src/pipeline/stages.js`, `backend/src/config.js`, and `backend/docs/api-contract.md`.
- Produces: the primary onboarding/navigation set; README links to every core/component document; architecture and setup commands agree with the active pipeline and environment template.

- [ ] **Step 1: Extend Markdown tests for the current architecture**

Add assertions to `MarkdownDocumentationTests` for the 2026-11-19 snapshot, stage names `file_type` and `content_analysis`, connected report history, synthetic-data caveats, dynamic-service presence plus unverified-safety warning, optional Groq behavior/model name, and absence of stale current-state claims such as “reports page disconnected” or “external component absent.” Exclude historical superpowers specs/plans from stale-current-state searches.

- [ ] **Step 2: Run Markdown tests to verify the old core documents fail**

Run: `python3 -m unittest tests.documentation.test_documentation.MarkdownDocumentationTests -v`

Expected: FAIL with stale-date/capability findings while existing-file/link checks continue to pass.

- [ ] **Step 3: Rewrite the root README as the current entry point**

Document the default multi-format pipeline, safe quick start, optional real PE analyzer, connected reports UI, optional ML/sandbox/LLM paths, current safety boundary, verification summary, repository map, and links to every core/component record. Remove the stale statement that the real analyzer rejects all non-PE submissions; explain routing instead.

- [ ] **Step 4: Reconcile project scope and architecture**

Update `project-overview.md` requirement/component summaries and `architecture.md` diagrams/tables for:

- Browser submission/history/detail flow.
- `signature` → `file_type` → predicate-gated `static_analysis` and/or `content_analysis` (unknown classifications run both) → optional sandbox/behavioral ML → optional LLM.
- Checked-in dynamic and LLM services as optional, partially verified implementations rather than absent directories.
- Current persistence, failure isolation, content-routing, privacy, and deployment boundaries.

- [ ] **Step 5: Reconcile setup and operations**

Document Node/Python prerequisites, default startup, optional content-analysis dependencies, real PE analyzer, ML synthetic workflow and HTTP service, Groq setup/fallback, dynamic-service environment-specific requirements, safe-use prohibition, current test commands, cleanup, and troubleshooting. Do not present the fixed sandbox address or deployment paths as portable defaults.

- [ ] **Step 6: Reconcile status and navigation**

Update `prototype-status.md` matrices/verification/risks/deferred work from Task 1 evidence. Update `documentation-index.md` status date, authoritative-source map, and maintenance flow.

- [ ] **Step 7: Run Markdown tests and local-link checks**

Run: `python3 -m unittest tests.documentation.test_documentation.MarkdownDocumentationTests -v`

Expected: PASS with all core links resolving and current capability/safety assertions present.

- [ ] **Step 8: Inspect the Task 2 diff checkpoint**

Run: `git diff --ignore-space-at-eol -- README.md docs/project-overview.md docs/architecture.md docs/setup-and-operations.md docs/prototype-status.md docs/documentation-index.md tests/documentation/test_documentation.py`

Expected: current system prose and tests only; no unsupported completion or safety claims.

### Task 3: Component Records and Narrow Authoritative Guides

**Files:**
- Modify: `docs/components/frontend.md`
- Modify: `docs/components/backend.md`
- Modify: `docs/components/malware-detection.md`
- Modify: `docs/components/machine-learning.md`
- Modify: `docs/components/dynamic-analysis.md`
- Modify: `docs/components/llm-threat-intelligence.md`
- Modify: `backend/README.md`
- Modify: `backend/docs/api-contract.md`
- Modify: `ML/SYNTHETIC_DATA.md` only if verification or source inspection finds an exact command/claim mismatch
- Modify: `dynamic_telemetry/README.md`
- Modify: `llm-threat-intelligence/README.md`
- Modify: `llm-threat-intelligence/STATUS.md`
- Modify: `tests/documentation/test_documentation.py`

**Interfaces:**
- Consumes: Task 1 evidence and Task 2 system terminology; exact component sources/tests.
- Produces: one current component record per team area and narrow setup/contract guides that do not contradict the core package.

- [ ] **Step 1: Add component/narrow-document drift tests**

Extend Markdown tests or add `ComponentDocumentationTests` requiring:

- Frontend docs to cite report history, PE detail rendering, data-model tests, and Playwright tests.
- Backend docs/API contract to list `file_type` and `content_analysis` and correctly describe LLM `generated|skipped|error|not_generated` status behavior.
- ML docs to cite generation, split, threshold, artifact metadata, and end-to-end test while warning that results are synthetic.
- Dynamic docs to cite `dynamic_telemetry/api.py` and explicitly state the unverified transfer/export/containment gaps.
- LLM docs to cite Groq, model `openai/gpt-oss-20b`, optional-failure fallback, demo indicator source, and absent ATT&CK mapping.

- [ ] **Step 2: Run component documentation tests to verify stale pages fail**

Run: `python3 -m unittest tests.documentation.test_documentation.ComponentDocumentationTests -v`

Expected: FAIL on old frontend/dynamic/LLM component claims.

- [ ] **Step 3: Reconcile frontend, backend, and malware-detection records**

Update frontend behavior/testing/gaps; update backend stage table/config/testing/default flow; update malware-detection integration wording only where multi-format routing or fresh test results affect it. Keep `malware_detection/REPORT_CONTRACT.md` authoritative for PE report fields.

- [ ] **Step 4: Reconcile the machine-learning record**

Document synthetic generation, strict export, split rules, classifier/anomaly training, validation threshold selection, feature-schema/artifact metadata, CLI/HTTP parity, and the end-to-end test. Preserve the distinction between behavioral ML and missing FR03 static ML, and between synthetic workflow verification and real-world efficacy.

- [ ] **Step 5: Reconcile the dynamic-analysis record and README**

Describe FastAPI endpoints, KVM/QEMU commands, snapshot intent, Sysmon parsing, service file, dependencies, backend contract, and environment-specific constants. Explicitly record that source inspection does not demonstrate a sample copy into the guest, EVTX export back to the host, network isolation, live telemetry, or safe reset; prohibit real-malware use.

- [ ] **Step 6: Reconcile the LLM/threat-intelligence record and guides**

Document demo indicator validation, Groq SDK/model, evidence prompt, bridge input/output, missing-key and provider-error fallback, configuration, privacy/prompt-injection concerns, and absent ATT&CK mapping/citations/versioned schema.

- [ ] **Step 7: Reconcile backend README and API output wording**

Ensure the quick-start/stage/config sections match current source; fix the API contract's stale `explanation_status` statement and any obsolete route/stage examples. Link to component guides instead of duplicating long implementation descriptions.

- [ ] **Step 8: Run evidence, Markdown, and component tests after reconciliation**

Run: `python3 -m unittest tests.documentation.test_documentation.DocumentationEvidenceTests tests.documentation.test_documentation.MarkdownDocumentationTests tests.documentation.test_documentation.ComponentDocumentationTests -v`

Expected: evidence, core Markdown, and component/narrow-document tests PASS. Word tests are intentionally deferred until Task 4 updates the generated snapshot.

- [ ] **Step 9: Inspect the Task 3 diff checkpoint**

Run: `git diff --ignore-space-at-eol -- docs/components backend/README.md backend/docs/api-contract.md ML/SYNTHETIC_DATA.md dynamic_telemetry/README.md llm-threat-intelligence/README.md llm-threat-intelligence/STATUS.md tests/documentation/test_documentation.py`

Expected: documentation-only reconciliation; no component source changes.

### Task 4: Word Generator and Eight Submission Records

**Files:**
- Modify: `scripts/update_documentation_forms.py`
- Modify: `tests/documentation/test_documentation.py`
- Modify: `Sentinel_Backend_Development_Documentation_Form.docx`
- Modify: `Sentinel_Documentation_All_Rounder_Documentation_Form.docx`
- Modify: `Sentinel_Dynamic_Analysis_Documentation_Form.docx`
- Modify: `Sentinel_Frontend_Development_Documentation_Form.docx`
- Modify: `Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx`
- Modify: `Sentinel_Machine_Learning_Documentation_Form.docx`
- Modify: `Sentinel_Malware_Detection_Documentation_Form.docx`
- Modify: `Sentinel_Project_Wide_Documentation_Record.docx`

**Interfaces:**
- Consumes: `docs/documentation-evidence.json`, current Markdown paths, and existing Office Open XML packages.
- Produces: `UPDATED = "2026-11-19"`; stable change IDs `BE-DOC-20261119`, `DOC-DOC-20261119`, `DA-DOC-20261119`, `FE-DOC-20261119`, `LLM-DOC-20261119`, `ML-DOC-20261119`, `MD-DOC-20261119`, and `PW-DOC-20261119`; eight idempotently regenerated `.docx` files.

- [ ] **Step 1: Update Word tests for the new snapshot and current claims**

Change `WORD_FORMS` IDs/date assertions to 2026-11-19. Add extracted-text assertions for current frontend, ML, dynamic, and LLM facts and for explicit safety/synthetic/ATT&CK limitations. Keep package, namespace, placeholder, incomplete-row, duplicate-ID, and cross-format checks.

- [ ] **Step 2: Run Word tests to verify the old generated records fail**

Run: `python3 -m unittest tests.documentation.test_documentation.WordDocumentationTests -v`

Expected: FAIL on the missing 2026-11-19 identifiers/current content.

- [ ] **Step 3: Update generator constants and current component records**

Set `UPDATED` and every `CHANGE_IDS` value to 2026-11-19. Replace hard-coded 2026-11-03 environment/result wording throughout `base_handoff()`, `form_specs()`, `populate_team_form()`, and `populate_project_record()` with current evidence and fresh verification records. Use stable decision IDs for the new snapshot and remove/upsert superseded generated current-state rows without deleting historical evidence.

- [ ] **Step 4: Update each team form projection**

Revise frontend, backend, ML, dynamic, LLM, malware-detection, and documentation form specs so their interfaces, dependencies, tests, risks, artifacts, milestones, and handoffs agree with the evidence JSON and Markdown. Update project-wide milestone, interface, safety, evaluation, verification, and handoff tables from the same facts.

- [ ] **Step 5: Generate previews and prove idempotence**

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir /tmp/sentinel-docs-20261119-a`

Run: `python3 scripts/update_documentation_forms.py --source-root /tmp/sentinel-docs-20261119-a --output-dir /tmp/sentinel-docs-20261119-b`

Expected: both runs succeed; extracted stable IDs occur once; second-generation structural/text output contains no duplicate current rows.

- [ ] **Step 6: Regenerate repository Word files and validate them**

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir .`

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`

Expected: eight valid forms; check exits 0.

- [ ] **Step 7: Run Word and cross-format tests**

Run: `python3 -m unittest tests.documentation.test_documentation.WordDocumentationTests tests.documentation.test_documentation.CrossFormatConsistencyTests -v`

Expected: PASS with current date/IDs, no placeholders/incomplete rows, and evidence/Markdown/Word status agreement.

- [ ] **Step 8: Inspect the Task 4 diff checkpoint**

Run: `git status --short`

Run: `git diff --ignore-space-at-eol -- scripts/update_documentation_forms.py tests/documentation/test_documentation.py`

Expected: generator/tests plus eight binary Word updates; no product-code changes.

### Task 5: Fresh Verification, Reconciliation, and Handoff

**Files:**
- Modify: `docs/documentation-evidence.json` only if command output differs from the provisional record
- Modify: `README.md`, `docs/prototype-status.md`, `docs/setup-and-operations.md`, and affected component docs only to record actual verification
- Modify: `scripts/update_documentation_forms.py` and regenerate Word files only if verification wording changes
- Modify: `tests/documentation/test_documentation.py` only if a valid consistency gap is discovered

**Interfaces:**
- Consumes: all Task 1-4 artifacts and fresh command output.
- Produces: one internally consistent documentation package whose verification statements are supported by this execution session.

- [ ] **Step 1: Run the full documentation and Word validation suite**

Run: `python3 -m unittest discover -s tests/documentation -v`

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`

Expected: all documentation tests PASS and all eight forms validate.

- [ ] **Step 2: Run contribution-tracker tests**

Run: `python3 -m unittest discover -s tests/contribution_tracker -v`

Expected: record the actual pass/fail count; do not reuse the 2026-11-03 result.

- [ ] **Step 3: Run the complete ML suite**

Run: `python3 -B -m unittest discover -s ML -p 'test_*.py' -v`

Expected: record the actual result. If dependencies are missing, name the precise import blocker; if tests pass, label the end-to-end metrics synthetic.

- [ ] **Step 4: Run the malware-detection suite**

Run: `python3 -m unittest discover -s malware_detection/tests -v`

Expected: record the actual result or exact missing optional/required dependency; never infer analyzer correctness from import success alone.

- [ ] **Step 5: Run backend unit/integration tests**

Run from `backend/`: `npm test`

Expected: record the actual Node test count/result or the exact platform/dependency blocker.

- [ ] **Step 6: Run dashboard browser tests when a compatible browser is available**

Run from `backend/`: `npm run test:dashboard`

Expected: record the actual result; if Playwright lacks a browser executable, record that blocker without downloading a browser unless separately authorized.

- [ ] **Step 7: Reconcile provisional verification text with actual output**

Update evidence JSON, Markdown, and generator records so every command, count, status, date, and blocker matches Steps 1-6. Regenerate and recheck Word files if any verification text changes.

- [ ] **Step 8: Search for stale or unsupported current-state claims**

Run: `rg -n "2026-11-03|reports page.*(disconnected|placeholder)|sandbox.*(absent|not contain)|external component.*absent|no (frontend|browser).*test|does not.*call an LLM" README.md docs/components docs/project-overview.md docs/architecture.md docs/setup-and-operations.md docs/prototype-status.md docs/documentation-index.md backend/README.md backend/docs/api-contract.md`

Expected: no stale current-state claims; historical references are explicitly labeled and old superpowers design/plan files are outside this search.

- [ ] **Step 9: Run final verification after all reconciliation edits**

Run: `python3 -m unittest discover -s tests/documentation -v`

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`

Run: `git diff --check`

Expected: documentation suite and Word validation PASS; `git diff --check` reports no newly introduced whitespace errors in authored documentation changes.

- [ ] **Step 10: Review final changed-file scope**

Run: `git status --short`

Run: `git diff --ignore-space-at-eol --stat`

Expected: meaningful changes are limited to approved documentation, evidence, documentation tests/tooling, design/plan, and eight Word records; unrelated product files remain only in their pre-existing CRLF-only state.

- [ ] **Step 11: Prepare the handoff**

Report updated artifact groups, fresh verification commands/results, blocked/live-external checks, the dynamic-sandbox safety warning, synthetic-ML qualification, and the Office visual-QA limitation if no Word-compatible renderer was used. Link the principal updated files.
