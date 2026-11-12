# Prototype Documentation Package Design

## Intent

Create a detailed, evidence-first documentation package for the current Sentinel prototype in both repository-native Markdown and the eight existing Microsoft Word documentation forms. The package should help the course team submit this version, onboard a developer, run the prototype, understand its architecture, and see exactly which proposal requirements are implemented, partially integrated, stubbed, absent, or not verified.

The documentation must describe the code in this branch as it exists on 2026-11-03. It must not present proposal scope, comments, historical claims, or unavailable components as verified functionality.

## Goals

- Replace the root README placeholder with a useful project entry point.
- Provide a coherent system architecture, data-flow, setup, operation, testing, security, and troubleshooting narrative.
- Document every visible subsystem: frontend, backend, malware detection, machine learning, dynamic analysis integration, and LLM/threat-intelligence integration.
- Complete all role-specific Word forms and the project-wide Word record using repository evidence.
- Use consistent status language across every artifact.
- Preserve traceability to FR01-FR08 and the nonfunctional requirements already defined in `docs/project-overview.md`.
- Record evidence paths, test commands, known limitations, missing dependencies, and unresolved team decisions.
- Keep the Markdown useful after the course submission by making it maintainable and link-oriented rather than copying large source listings.

## Non-goals

- Implement, fix, or redesign prototype features.
- Claim production readiness, malware-containment guarantees, model performance, or end-to-end integration without evidence.
- Invent team approvals, reviewers, dates, credentials, datasets, benchmark results, deployment environments, or security validation.
- Add or execute real malware samples.
- Rewrite stable detailed contracts when an existing document is already the authoritative source.
- Resolve the repository-wide line-ending-only working-tree changes.

## Anti-goals

- A polished report that blurs planned and implemented scope.
- Eight Word files that contradict the Markdown or one another.
- Large duplicated passages that will immediately drift.
- Treating a unit-test count found in an old document as a result observed in the current environment.
- Describing optional adapters as though the corresponding external components are present in this branch.

## Constraints and Evidence Rules

- Repository source, configuration, schemas, tests, and current branch contents are primary evidence.
- Existing documentation is secondary evidence and must be reconciled against source before reuse.
- Historical commit IDs and author/reviewer statements may be retained only when already recorded; new personal attribution will not be inferred.
- Status terms have fixed meanings:
  - **Implemented:** code is present and has a concrete execution path.
  - **Integrated:** producer and consumer code/contracts are present in this branch.
  - **Partial:** meaningful code exists, but a required path or user-facing behavior is incomplete.
  - **Stubbed/configurable:** an adapter or placeholder exists but requires an unavailable component or configuration.
  - **Planned/not present:** required implementation is absent from this branch.
  - **Not verified:** code or a historical result exists, but it was not successfully exercised in the current environment.
- Test reporting will distinguish repository test inventory, historical results, and tests actually run during this documentation update.
- Current observed test constraints must be recorded: the contribution-tracker suite runs successfully; backend tests cannot start because the available `npm` reports unsupported WSL 1; malware-detection tests cannot import without `pefile`; ML tests cannot import without `joblib`.
- Word templates must retain their existing section structure and general styling. Unknown fields will say `Not recorded`, `Not available in this branch`, or `Requires team confirmation` rather than remain as template prompts.
- Generated Word files will be validated structurally by reopening them and checking required sections/tables. Visual fidelity will be reported as not visually verified if no Word-compatible renderer is available.
- No secrets, malware binaries, datasets, model artifacts, generated databases, uploads, or environment-specific absolute paths will be added.

## Chosen Approach

### Evidence-first package

Build a verified Markdown documentation set first, then populate the Word forms from the same component facts, requirement statuses, evidence paths, and limitations. Markdown remains the maintainable source of truth; the Word files are self-contained submission records that summarize and link to that evidence.

This approach was chosen because the user requested detailed deliverables in both formats and selected the evidence-first option. It trades more initial reconciliation work for consistency, accuracy, and long-term maintainability.

## Approaches Considered

### Evidence-first package — selected

Detailed Markdown plus fully populated Word forms, all driven by one evidence model. Highest consistency and clearest distinction between implemented and planned behavior; requires the most repository analysis.

### Submission-first package

Put most detail into Word and keep repository docs brief. Faster for form-centric grading, but harder for developers to maintain and more likely to duplicate or drift.

### Repository-first package

Make Markdown comprehensive and use the forms mainly as summaries and link indexes. Most maintainable, but the Word artifacts would be weaker as standalone submissions.

## Repository Documentation Structure

The implementation plan may refine filenames, but the package should have these responsibilities:

- `README.md`: project purpose, prototype status, major capabilities, quick start, high-level architecture, safety warning, test summary, and links to detailed docs.
- `docs/project-overview.md`: convert the existing proposal-centric overview into a current-version overview while preserving requirement identifiers and clearly separating baseline scope from current status.
- `docs/architecture.md`: end-to-end request/data flow, component boundaries, stage ordering, persistence, contracts, and deployment shape. Include Mermaid diagrams with text explanations.
- `docs/setup-and-operations.md`: prerequisites, dependency installation, environment configuration, startup paths, optional integrations, safe handling, troubleshooting, and cleanup notes.
- `docs/prototype-status.md`: requirement traceability, component maturity matrix, verified test evidence, known limitations, risks, and deferred work.
- `docs/components/frontend.md`: screens, authentication interaction, upload/link workflow, polling/progress behavior, reports-page state, accessibility observations, and gaps.
- `docs/components/backend.md`: concise current component record that points to the authoritative backend README/API/database docs and reconciles stage status.
- `docs/components/malware-detection.md`: concise current component record that points to the authoritative analyzer contract/integration/reputation docs.
- `docs/components/machine-learning.md`: feature schema, training/inference scripts, expected artifacts, HTTP service, evaluation support, missing datasets/artifacts, and test limitations.
- `docs/components/dynamic-analysis.md`: document only the adapter/configuration expectations visible in this branch, explicitly marking the sandbox implementation as absent.
- `docs/components/llm-threat-intelligence.md`: document only the bridge/input adapter and expected external directory, explicitly marking model invocation/explanation generation as unavailable in this branch.
- `docs/documentation-index.md`: map each audience and Word form to the authoritative Markdown/source evidence and record document ownership/status.

Existing detailed documents under `backend/docs/` and `malware_detection/` remain authoritative for their narrow contracts. They should be corrected only where source inspection proves them stale or contradictory; otherwise, new overview pages link to them.

## Word Deliverables

Update these existing templates in place, preserving filenames:

- `Sentinel_Backend_Development_Documentation_Form.docx`
- `Sentinel_Documentation_All_Rounder_Documentation_Form.docx`
- `Sentinel_Dynamic_Analysis_Documentation_Form.docx`
- `Sentinel_Frontend_Development_Documentation_Form.docx`
- `Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx`
- `Sentinel_Machine_Learning_Documentation_Form.docx`
- `Sentinel_Malware_Detection_Documentation_Form.docx`
- `Sentinel_Project_Wide_Documentation_Record.docx`

Each form will contain, as applicable:

- A current record header and explicit prototype status.
- A change-log entry for this documentation reconciliation without fabricating a commit or reviewer.
- Architecture/interface and dependency/configuration entries.
- Component-specific records populated from source evidence.
- Testing entries that distinguish observed results from blocked/not-run suites.
- Quality/security review entries with evidence and candid gaps.
- Risks, issues, technical debt, and artifact links.
- A handoff summary describing what exists, how to run it, what remains incomplete, and what needs team confirmation.

The project-wide record will compile the shared architecture, requirement matrix, integration status, test record, safety/demo readiness, risks, document index, and current-version handoff. Empty evaluation metric fields will explicitly state that no trained model artifacts, datasets, or reproducible benchmark outputs are present rather than supplying guessed values.

## Accuracy and Reconciliation Method

1. Inventory files, configuration, routes, stage definitions, schemas, tests, and existing docs.
2. Create a normalized evidence matrix keyed by component and requirement.
3. Reconcile contradictions, giving executable source/configuration precedence and recording uncertainty.
4. Write the Markdown package from that matrix.
5. Populate all Word forms from the same matrix and Markdown evidence paths.
6. Search for leftover template prompts and unsupported claims.
7. Validate links, commands, document structure, and changed-file scope.

## Verification

- Run Markdown link/path checks that do not require network access.
- Search all new/updated Markdown and extracted Word text for template placeholders such as `Enter current value`, `Enter milestone`, and generic status choices.
- Re-extract all eight Word files and confirm expected headings, nonempty table responses, current dates, and status labels.
- Confirm each FR01-FR08 row and each nonfunctional requirement has an evidence-based status in the project-wide artifacts.
- Re-run available repository tests after documenting prerequisites if dependencies can be used safely; never convert a blocked run into a passing claim.
- Inspect `git diff` narrowly and preserve unrelated user changes, including existing line-ending-only modifications.

## Builder Calls Left Open

- Exact prose organization and table density within each document.
- Whether a small fact belongs directly in a component page or is linked to an existing authoritative contract.
- The implementation mechanism for editing `.docx` files, provided the existing formatting is preserved and structural validation is performed. A temporary `python-docx` installation is preferred if available; a generator script may be kept only if it materially improves repeatability.
- Minor wording for unknown fields, provided it consistently avoids fabrication.

## Acceptance Criteria

- Both Markdown and all eight Word files are delivered.
- A new reader can install prerequisites, identify the runnable default path, start the backend/site, submit a sample or URL, understand stage results, and locate troubleshooting guidance.
- Architecture and component documents match current routes, configuration, pipeline order, and branch contents.
- Every component and requirement has a candid maturity/status classification backed by a repository path or test result.
- No template prompts remain in completed response fields except explanatory text that quotes a prompt intentionally.
- No benchmark, security, integration, approval, or test claim is invented.
- Word files remain valid Office Open XML documents and retain recognizable template structure.
- Unrelated code is not changed.
