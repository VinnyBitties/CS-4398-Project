# Prototype Documentation Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a detailed, evidence-based Markdown documentation set and eight completed Word documentation forms for the current Sentinel prototype.

**Architecture:** A normalized JSON evidence record will capture component maturity, requirements, verification results, limitations, and source paths. Human-readable Markdown will explain that evidence for developers and evaluators; an idempotent `python-docx` generator will apply the same evidence to the existing Word templates while preserving their section structure.

**Tech Stack:** Markdown, Mermaid, JSON, Python 3 standard library, `python-docx`, `unittest`, Microsoft Office Open XML (`.docx`)

**Spec:** `docs/superpowers/specs/2026-11-03-prototype-documentation-design.md`

## Global Constraints

- Describe the repository as it exists on 2026-11-03; do not turn proposal scope or historical claims into current verified behavior.
- Use only these maturity terms: `Implemented`, `Integrated`, `Partial`, `Stubbed/configurable`, `Planned/not present`, and `Not verified`.
- Do not invent team approvals, reviewers, milestone dates, credentials, datasets, metrics, deployment environments, or safety validation.
- Distinguish test inventory, historical test claims, and results observed during this documentation update.
- Record the observed environment limitations exactly: backend tests cannot start because available `npm` reports unsupported WSL 1; malware-detection tests cannot import without `pefile`; ML tests cannot import without `joblib`; contribution-tracker tests ran 30/30 successfully.
- Preserve the eight existing Word filenames, recognizable template structure, existing recorded history, and unrelated user changes.
- Do not add secrets, malware samples, datasets, model artifacts, databases, uploads, or machine-specific absolute paths.
- Keep `backend/docs/` and `malware_detection/` documents authoritative for their narrow contracts; link rather than duplicate unless source inspection proves a contradiction.

## Review Focus

- A proposal requirement with no implementation must be labeled `Planned/not present`, with no wording that implies completion.
- An adapter whose external component is absent must be labeled `Stubbed/configurable`, and setup instructions must not imply a default end-to-end path.
- A historical passing-test count must never appear as a test result observed on 2026-11-03.
- Unknown Word-form fields must contain a candid marker such as `Not recorded` or `Requires team confirmation`, not a template prompt or fabricated value.
- Re-running the Word generator must not duplicate change-log, risk, test, or artifact rows.

---

### Task 1: Normalized Evidence Record and Documentation Checks

**Files:**
- Create: `docs/documentation-evidence.json`
- Create: `tests/documentation/test_documentation.py`

**Interfaces:**
- Consumes: current source/configuration in `backend/`, `ML/`, `malware_detection/`, `website/`; existing docs; test commands and their observed results.
- Produces: `docs/documentation-evidence.json` with top-level keys `metadata`, `status_vocabulary`, `components`, `requirements`, `verification`, `risks`, and `artifacts`; reusable validation helpers in `tests/documentation/test_documentation.py`.

- [ ] **Step 1: Write failing evidence-schema and path tests**

Add `DocumentationEvidenceTests` assertions that load `docs/documentation-evidence.json`, require all top-level keys, require components `frontend`, `backend`, `malware_detection`, `machine_learning`, `dynamic_analysis`, and `llm_threat_intelligence`, require FR01-FR08 plus the five named NFR entries, restrict every status to the six values in Global Constraints, and verify every repository-relative evidence path exists.

- [ ] **Step 2: Run the evidence tests to verify they fail**

Run: `python3 -m unittest tests.documentation.test_documentation.DocumentationEvidenceTests -v`

Expected: FAIL because `docs/documentation-evidence.json` does not exist.

- [ ] **Step 3: Create the normalized evidence record**

Record for each component: purpose, current status, present implementation, interfaces, dependencies/configuration, tests, limitations, risks, and repository evidence. Record each requirement with responsible components, status, implementation evidence, test evidence, and a plain-language gap. Record observed verification separately from historical claims.

- [ ] **Step 4: Run evidence tests to verify they pass**

Run: `python3 -m unittest tests.documentation.test_documentation.DocumentationEvidenceTests -v`

Expected: PASS with all components, requirements, statuses, and evidence paths validated.

- [ ] **Step 5: Commit**

```bash
git add docs/documentation-evidence.json tests/documentation/test_documentation.py
git commit -m "docs: add prototype evidence record"
```

### Task 2: Core and Component Markdown Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/project-overview.md`
- Create: `docs/architecture.md`
- Create: `docs/setup-and-operations.md`
- Create: `docs/prototype-status.md`
- Create: `docs/documentation-index.md`
- Create: `docs/components/frontend.md`
- Create: `docs/components/backend.md`
- Create: `docs/components/malware-detection.md`
- Create: `docs/components/machine-learning.md`
- Create: `docs/components/dynamic-analysis.md`
- Create: `docs/components/llm-threat-intelligence.md`
- Modify: `tests/documentation/test_documentation.py`

**Interfaces:**
- Consumes: the schema and facts in `docs/documentation-evidence.json`; authoritative contracts in `backend/docs/` and `malware_detection/`.
- Produces: a navigable Markdown documentation package whose requirement statuses, component statuses, commands, configuration names, routes, and evidence links agree with the evidence record.

- [ ] **Step 1: Write failing Markdown coverage and local-link tests**

Add `MarkdownDocumentationTests` assertions for all required files; README navigation to every core document; FR01-FR08 and all five NFR identifiers in `docs/prototype-status.md`; all six component names and maturity labels; no absolute workspace paths; no unresolved template phrases; and resolution of every repository-relative Markdown link and inline code path that is declared as an artifact.

- [ ] **Step 2: Run Markdown tests to verify they fail**

Run: `python3 -m unittest tests.documentation.test_documentation.MarkdownDocumentationTests -v`

Expected: FAIL listing the missing Markdown files and README navigation.

- [ ] **Step 3: Replace the root README placeholder**

Write a concise entry point covering purpose, research/prototype disclaimer, current implemented path, six-stage conceptual pipeline versus actual stage availability, quick start, safe-sample warning, observed test status, repository map, and links to the detailed docs.

- [ ] **Step 4: Reconcile the project overview and write core documents**

Update `docs/project-overview.md` to preserve baseline scope and requirement IDs while adding current implementation status. Write `architecture.md` with Mermaid system-context and scan-sequence diagrams plus text alternatives; `setup-and-operations.md` with prerequisites, backend/site startup, mock versus real analyzer setup, optional integrations, configuration groups, troubleshooting, and safe cleanup; `prototype-status.md` with the component maturity matrix, traceability matrix, verification record, risks, limitations, and deferred work; and `documentation-index.md` with audience, owner/status, authoritative artifact, and Word-form mappings.

- [ ] **Step 5: Write the six component documents**

Each component page must contain purpose, source layout, current behavior, interfaces/data flow, dependencies/configuration, run or integration instructions, testing evidence, limitations, security/safety notes, and next work. Dynamic-analysis and LLM pages must describe only the adapters/contracts present in this branch and clearly state that their implementations are absent.

- [ ] **Step 6: Run Markdown tests to verify they pass**

Run: `python3 -m unittest tests.documentation.test_documentation.MarkdownDocumentationTests -v`

Expected: PASS with all documents present, linked, and free of unsupported template language.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/project-overview.md docs/architecture.md docs/setup-and-operations.md docs/prototype-status.md docs/documentation-index.md docs/components tests/documentation/test_documentation.py
git commit -m "docs: document current Sentinel prototype"
```

### Task 3: Repeatable Word-Form Population

**Files:**
- Create: `docs/requirements-documentation.txt`
- Create: `scripts/update_documentation_forms.py`
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
- Consumes: `docs/documentation-evidence.json`, current Markdown paths, and the eight existing `.docx` files as templates.
- Produces: `update_documentation_forms.py` command `python3 scripts/update_documentation_forms.py --source-root <path> --output-dir <path>`; eight structurally valid, populated `.docx` files. The generator must use stable change/test/risk/artifact IDs to remain idempotent.

- [ ] **Step 1: Write failing Word validation tests**

Using only `zipfile` and `xml.etree.ElementTree`, add `WordDocumentationTests` that require all eight files to be valid ZIP/Office Open XML documents, extract their text, require a `2026-11-03` update marker and the expected team title, reject response placeholders (`Enter current value`, `Enter milestone`, `Enter link or path`, generic status choices), require status/evidence/limitations/handoff content, and require FR01-FR08 in the project-wide record. Add a duplicate-ID check for the documentation reconciliation entry.

- [ ] **Step 2: Run Word tests to verify they fail**

Run: `python3 -m unittest tests.documentation.test_documentation.WordDocumentationTests -v`

Expected: FAIL because six forms and the project-wide record still contain template prompts and the populated forms lack the current reconciliation entry.

- [ ] **Step 3: Add the documentation-generation dependency and CLI skeleton**

Add `python-docx` to `docs/requirements-documentation.txt`. Implement argument parsing for `--source-root`, `--output-dir`, and `--check`; load and validate `docs/documentation-evidence.json`; resolve the exact eight template filenames; and refuse to overwrite a non-`.docx` target.

- [ ] **Step 4: Implement template-preserving table updates**

Implement helpers with exact responsibilities:

- `set_field(table, label: str, value: str) -> None` updates a two-column response row.
- `upsert_row(table, key_column: int, key: str, values: list[str]) -> None` replaces or appends one stable-ID row without duplication.
- `replace_response_placeholders(document, replacement: str) -> None` clears remaining response prompts without altering instructional text.
- `populate_team_form(document, form_key: str, evidence: dict) -> None` fills metadata, interfaces, dependencies, component-specific records, tests, quality/security review, risks, artifacts, and handoff.
- `populate_project_record(document, evidence: dict) -> None` fills the cross-team matrices, milestones/status, interfaces, risks, integration tests, safety readiness, evaluation gaps, document index, and handoff.
- `validate_document(document, form_key: str) -> list[str]` returns structural or placeholder errors for `--check`.

Preserve existing backend and malware-detection history rows, add stable documentation change IDs, and use `Not recorded`, `Not available in this branch`, or `Requires team confirmation` for unknowns.

- [ ] **Step 5: Generate to a temporary directory and verify idempotence**

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir /tmp/sentinel-documentation-preview`

Run the same command a second time using the generated directory as the source and a second temporary output directory.

Expected: both runs succeed; extracted stable IDs occur once per document; the second run introduces no duplicate rows.

- [ ] **Step 6: Update the repository Word forms and run structural checks**

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir .`

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`

Expected: eight files updated; check exits 0 and reports every form valid.

- [ ] **Step 7: Run Word tests to verify they pass**

Run: `python3 -m unittest tests.documentation.test_documentation.WordDocumentationTests -v`

Expected: PASS with no response placeholders, missing requirement IDs, invalid packages, or duplicate reconciliation entries.

- [ ] **Step 8: Commit**

```bash
git add docs/requirements-documentation.txt scripts/update_documentation_forms.py tests/documentation/test_documentation.py Sentinel_*_Documentation_*.docx
git commit -m "docs: complete Sentinel documentation forms"
```

### Task 4: Cross-Format Consistency and Final Verification

**Files:**
- Modify: `docs/documentation-evidence.json` only if verification finds a factual mismatch
- Modify: affected Markdown or Word-generation files only if verification finds a mismatch
- Modify: `tests/documentation/test_documentation.py`

**Interfaces:**
- Consumes: all artifacts from Tasks 1-3.
- Produces: one internally consistent documentation package with recorded verification output and no unrelated source changes.

- [ ] **Step 1: Add cross-format consistency tests**

Add `CrossFormatConsistencyTests` that compare evidence-record requirement statuses with `docs/prototype-status.md` and extracted project-wide Word text; require every component's evidence page in both the documentation index and its role form; verify all eight filenames are indexed; and require the same observed test outcomes in Markdown and the relevant Word records.

- [ ] **Step 2: Run cross-format tests and fix only evidenced mismatches**

Run: `python3 -m unittest tests.documentation.test_documentation.CrossFormatConsistencyTests -v`

Expected: PASS after reconciling any status, path, or verification wording mismatch.

- [ ] **Step 3: Run the full documentation suite**

Run: `python3 -m unittest discover -s tests/documentation -v`

Expected: all documentation evidence, Markdown, Word structure, idempotence, and cross-format consistency tests pass.

- [ ] **Step 4: Re-run available project verification**

Run: `python3 -m unittest discover -s tests/contribution_tracker -v`

Expected: 30 tests pass.

Run: `python3 -m unittest discover -s malware_detection/tests -v`

Expected in the current environment: import errors explicitly caused by missing `pefile`; if the dependency is installed during execution, record the actual result instead.

Run from `ML/`: `python3 -m unittest test_report_parser -v`

Expected in the current environment: import error explicitly caused by missing `joblib`; if documentation dependencies or project dependencies change the environment, record the actual result instead.

Run from `backend/`: `npm test`

Expected in the current environment: startup failure reporting unsupported WSL 1; do not report repository tests as failed assertions.

- [ ] **Step 5: Inspect changed-file scope and Office package integrity**

Run: `git status --short`

Run: `git diff -- README.md docs scripts/update_documentation_forms.py tests/documentation`

Run: `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`

Expected: only documentation artifacts, documentation tooling/tests, the pre-existing line-ending-only changes, and the approved design/plan are present; all eight Word packages validate.

- [ ] **Step 6: Record visual-QA limitation if necessary**

If no Word-compatible renderer is available, state in the handoff that Office Open XML structure and extracted content were verified but pagination and visual layout require opening the files in Microsoft Word or LibreOffice. Do not claim visual verification without rendering.

- [ ] **Step 7: Commit**

```bash
git add README.md docs scripts/update_documentation_forms.py tests/documentation Sentinel_*_Documentation_*.docx
git commit -m "docs: verify prototype documentation package"
```
