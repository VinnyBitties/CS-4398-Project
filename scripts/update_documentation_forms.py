#!/usr/bin/env python3
"""Populate Sentinel's Word documentation templates from repository evidence.

The script intentionally uses only Python's standard library. A .docx file is
an Office Open XML ZIP package; this tool updates word/document.xml while
copying every other package part and the existing table formatting unchanged.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W = f"{{{W_NS}}}"

IGNORABLE_NAMESPACES = {
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
}

ET.register_namespace("w", W_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("mc", MC_NS)
ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
ET.register_namespace("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
ET.register_namespace("wp14", "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing")

UPDATED = "2026-11-03"
REPOSITORY = "https://github.com/VinnyBitties/CS-4398-Project, branch dev-branch"
UNKNOWN = "Not recorded; requires team confirmation."
NOT_AVAILABLE = "Not available in this branch."


FORM_FILES = {
    "backend": "Sentinel_Backend_Development_Documentation_Form.docx",
    "documentation": "Sentinel_Documentation_All_Rounder_Documentation_Form.docx",
    "dynamic_analysis": "Sentinel_Dynamic_Analysis_Documentation_Form.docx",
    "frontend": "Sentinel_Frontend_Development_Documentation_Form.docx",
    "llm_threat_intelligence": "Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx",
    "machine_learning": "Sentinel_Machine_Learning_Documentation_Form.docx",
    "malware_detection": "Sentinel_Malware_Detection_Documentation_Form.docx",
    "project": "Sentinel_Project_Wide_Documentation_Record.docx",
}

FORM_TITLES = {
    "backend": "Backend Development Documentation Form",
    "documentation": "Documentation and All Rounder Documentation Form",
    "dynamic_analysis": "Dynamic Analysis Documentation Form",
    "frontend": "Frontend Development Documentation Form",
    "llm_threat_intelligence": "LLM and Threat Intelligence Documentation Form",
    "machine_learning": "Machine Learning Documentation Form",
    "malware_detection": "Malware Detection Documentation Form",
    "project": "Project Wide Documentation Record",
}

CHANGE_IDS = {
    "backend": "BE-DOC-20261103",
    "documentation": "DOC-DOC-20261103",
    "dynamic_analysis": "DA-DOC-20261103",
    "frontend": "FE-DOC-20261103",
    "llm_threat_intelligence": "LLM-DOC-20261103",
    "machine_learning": "ML-DOC-20261103",
    "malware_detection": "MD-DOC-20261103",
    "project": "PW-DOC-20261103",
}


def element_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(f"{W}t")).strip()


def set_cell_text(cell: ET.Element, value: str) -> None:
    """Replace a cell's text while retaining cell and first-paragraph styling."""

    first_paragraph = cell.find(f"{W}p")
    paragraph_properties = None
    run_properties = None
    if first_paragraph is not None:
        existing_ppr = first_paragraph.find(f"{W}pPr")
        if existing_ppr is not None:
            paragraph_properties = deepcopy(existing_ppr)
        first_run = first_paragraph.find(f"{W}r")
        if first_run is not None:
            existing_rpr = first_run.find(f"{W}rPr")
            if existing_rpr is not None:
                run_properties = deepcopy(existing_rpr)

    for child in list(cell):
        if child.tag != f"{W}tcPr":
            cell.remove(child)

    paragraph = ET.SubElement(cell, f"{W}p")
    if paragraph_properties is not None:
        paragraph.append(paragraph_properties)

    lines = str(value).split("\n")
    for index, line in enumerate(lines):
        run = ET.SubElement(paragraph, f"{W}r")
        if run_properties is not None:
            run.append(deepcopy(run_properties))
        text = ET.SubElement(run, f"{W}t")
        if line.startswith(" ") or line.endswith(" "):
            text.set(f"{{{XML_NS}}}space", "preserve")
        text.text = line
        if index < len(lines) - 1:
            ET.SubElement(run, f"{W}br")


def table_rows(table: ET.Element) -> list[ET.Element]:
    return table.findall(f"{W}tr")


def row_cells(row: ET.Element) -> list[ET.Element]:
    return row.findall(f"{W}tc")


def set_field(table: ET.Element, label: str, value: str) -> None:
    """Update a two-column field/value row by its first-cell label."""

    for row in table_rows(table)[1:]:
        cells = row_cells(row)
        if len(cells) >= 2 and element_text(cells[0]) == label:
            set_cell_text(cells[1], value)
            return
    raise KeyError(f"Field not found: {label}")


def upsert_row(table: ET.Element, key_column: int, key: str, values: list[str]) -> None:
    """Replace or append a table row identified by a stable key."""

    rows = table_rows(table)
    target = None
    for row in rows[1:]:
        cells = row_cells(row)
        if key_column < len(cells) and element_text(cells[key_column]) == key:
            target = row
            break

    if target is None:
        for row in rows[1:]:
            cells = row_cells(row)
            if key_column < len(cells) and not element_text(cells[key_column]):
                target = row
                break

    if target is None:
        target = deepcopy(rows[-1])
        table.append(target)

    cells = row_cells(target)
    if len(cells) != len(values):
        raise ValueError(f"Row for {key!r} needs {len(cells)} values, received {len(values)}")
    for cell, value in zip(cells, values):
        set_cell_text(cell, value)


def remove_rows_by_key(table: ET.Element, key_column: int, keys: set[str]) -> None:
    """Remove superseded current-state records while retaining dated history."""

    for row in table_rows(table)[1:]:
        cells = row_cells(row)
        if key_column < len(cells) and element_text(cells[key_column]) in keys:
            table.remove(row)


def complete_record_tables(document: ET.Element) -> None:
    """Remove unused template rows and mark unknown cells in retained records."""

    generic_types = {"Risk / Issue / Debt", "Risk / Issue / Dependency"}
    for table in document.iter(f"{W}tbl"):
        for row in table_rows(table)[1:]:
            cells = row_cells(row)
            values = [element_text(cell) for cell in cells]
            if not any(values) or any(value in generic_types for value in values):
                table.remove(row)
                continue
            for cell, value in zip(cells, values):
                if not value:
                    set_cell_text(cell, UNKNOWN)


def preserve_ignorable_namespaces(document: ET.Element) -> None:
    """Declare every known namespace named by the root mc:Ignorable attribute."""

    ignorable = document.get(f"{{{MC_NS}}}Ignorable", "")
    for prefix in ignorable.split():
        namespace = IGNORABLE_NAMESPACES.get(prefix)
        if namespace:
            document.set(f"xmlns:{prefix}", namespace)


def replace_response_placeholders(document: ET.Element, replacement: str) -> None:
    """Replace response-cell prompts without changing instructional paragraphs."""

    generic_status = "Planned / In progress / Blocked / Ready for review / Complete"
    for table in document.iter(f"{W}tbl"):
        for row in table_rows(table)[1:]:
            cells = row_cells(row)
            for cell in cells[1:]:
                current = element_text(cell)
                if current.startswith("Enter ") or current == generic_status:
                    set_cell_text(cell, replacement)


def fill_quality_review(table: ET.Element, owner: str, component_status: str) -> None:
    explanations = {
        "Inputs are validated": ("Partial", "Validation exists at documented API/parser boundaries; component gaps remain."),
        "Errors fail safely and are observable": ("Partial", "Structured errors or explicit unavailable states exist; full deployment observability is not implemented."),
        "Sensitive data and secrets are protected": ("Partial", "Secrets are excluded from source, but retention/redaction and production secrets handling require policy."),
        "Dependencies and versions are recorded": ("Partial", "Repository manifests are present; external sandbox/provider versions are not recorded."),
        "User-facing behavior is understandable": (component_status, "Current behavior and limitations are documented; usability review remains where noted."),
        "Relevant safety and isolation controls are tested": ("Not verified", "No real sandbox isolation test is available in this branch."),
    }
    for row in table_rows(table)[1:]:
        cells = row_cells(row)
        if len(cells) < 5:
            continue
        label = element_text(cells[0])
        status, explanation = explanations.get(label, ("Not verified", UNKNOWN))
        set_cell_text(cells[1], status)
        set_cell_text(cells[2], explanation)
        set_cell_text(cells[3], owner)
        set_cell_text(cells[4], "Requires team scheduling")


def base_handoff(component: dict[str, Any], component_doc: str) -> dict[str, str]:
    tests = component["tests"]
    return {
        "What the team delivered": " ".join(component["present_implementation"]),
        "How the implementation works": " ".join(component["interfaces"]),
        "Requirements satisfied": "See docs/prototype-status.md for requirement-by-requirement status; this component is " + component["status"] + ".",
        "Setup and run instructions": "See README.md, docs/setup-and-operations.md, and " + component_doc + ".",
        "Test results and metrics": "Observed: " + " ".join(tests["observed"]) + " Inventory: " + " ".join(tests["inventory"]),
        "Known limitations": " ".join(component["limitations"]),
        "Open defects or deferred work": " ".join(component["risks"]),
        "Operational or safety notes": "Research prototype only. Use inert fixtures; do not infer benign status from missing evidence. See docs/prototype-status.md.",
        "Files that must appear in the final report": f"{component_doc}; docs/prototype-status.md; docs/architecture.md; relevant contracts and test evidence.",
        "Team approval and date": "Requires team confirmation; documentation reconciled 2026-11-03.",
    }


def form_specs(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = evidence["components"]
    shared = {
        "repository": REPOSITORY,
        "scope": "Current branch reconciled against source on 2026-11-03; unimplemented proposal scope is labeled explicitly.",
    }
    return {
        "backend": {
            **shared,
            "component": components["backend"],
            "owner": "D.G (assigned member; confirmation required)",
            "milestone": "Prototype API/orchestration reconciliation",
            "status": "Partial; core API implemented, optional stages incomplete",
            "requirements": "FR01-FR08; NFR Safety, Performance, Maintainability",
            "special": {
                "Method and route": "GET /api/health; POST /api/auth/register, login, logout; GET /api/auth/me; POST /api/samples; POST /api/links; GET /api/samples; GET /api/samples/:id.",
                "Purpose": "Account/guest access, submission, queued analysis, status/results, and paged history.",
                "Authentication": "Optional HttpOnly cookie session; history and item access are scoped to signed-in user or guest.",
                "Request schema": "JSON for auth/links; multipart field file for samples; query parameters wait, limit, offset.",
                "Response schema": "JSON sample view containing job status and stage results; stable JSON error codes.",
                "Status codes": "200/201/202 success; 400 validation; 401 auth; 404 scope/not found; 409 conflict; 413 upload; 429 lockout; 500 unexpected.",
                "Validation": "JSON body limit, upload size, URL scheme/length, identifiers, usernames/passwords, catalog schema, analyzer output schema.",
                "Rate or size limits": "25 MiB upload default; 100 KiB JSON body; failed-login lockout; no general API rate limit.",
                "Example request": "curl -F file=@backend/test/fixtures/sample.bin http://localhost:3000/api/samples?wait=true",
                "Example response": "Sample JSON with sample_id, submission_type, status, job, and results array; see backend/docs/api-contract.md.",
                "Engine and version": "SQLite through better-sqlite3 by default; PostgreSQL through pg when DATABASE_URL is set.",
                "Schema or migration version": "Tables are created/updated at startup in backend/src/db.js; no numbered migration system.",
                "Table or collection": "users, sessions, samples, jobs, results, threat-intelligence indicator results.",
                "Purpose": "Persist accounts, session hashes, submissions, queue state, and stage output.",
                "Key fields": "Numeric IDs, owner/user ID, submission type, SHA-256/URL, stored path, status, worker ID, report JSON, timestamps.",
                "Relationships": "Users own optional sessions/samples; samples have jobs and results; results are keyed by sample/stage.",
                "Indexes": "Defined by backend/src/db.js for lookup and queue/history paths.",
                "Retention": "Not defined; no deletion endpoint or retention job.",
                "Sensitive fields": "Password hashes, session-token hashes, filenames/paths, URLs, reports, indicator results.",
                "Backup or reset procedure": "SQLite file backup or PostgreSQL platform process; destructive reset only in disposable test database.",
                "Stage": "signature → static_analysis → optional sandbox → behavioral_ml → optional llm; static_ml is not registered.",
                "Trigger": "Queued file or URL submission; stage appliesTo and configuration gates decide execution.",
                "Input": "Stored sample record and prior successful reports.",
                "Output": "Per-stage running/completed/failed row with JSON report and stable error code/message.",
                "Timeout": "Analyzer 15 s; wait 30 s; sandbox 120 s; behavioral ML 15 s; LLM 30 s by default.",
                "Retry policy": "Interrupted owned jobs re-queue at startup; individual stages do not automatically retry.",
                "Failure state": "Stage failure is stored and later stages are considered; job failure is separate.",
                "Status exposed to UI": "queued, running, completed, failed plus every stage state.",
                "Owning interface": "backend/src/pipeline/stages.js and backend/docs/api-contract.md.",
            },
            "interfaces": [
                ["Dashboard REST API", "Backend", "Frontend", "JSON/multipart HTTP", "backend/docs/api-contract.md", "Current prototype", "Stable JSON error; per-stage failures", "D.G / Sebastian"],
                ["Static analyzer subprocess", "malware_detection or mock", "Backend", "JSON stdout", "malware_detection/REPORT_CONTRACT.md", "1.0.0-1.2.0 accepted", "Timeout/nonzero/bad JSON/schema stored", "Kyle / D.G"],
                ["Behavioral ML service", "ML/predict.py --serve", "Backend", "POST normalized telemetry JSON; score/evidence JSON", "ML/predict.py; backend/src/adapters/sandboxToMl.js", "Unversioned", "Timeout/connection/status/JSON failure stored", "Axel, Diego / D.G"],
            ],
            "dependencies": [
                ["Node.js/npm", "22 LTS documented", "Backend runtime", "package.json", "No", "npm install", "Node/project licenses"],
                ["SQLite/PostgreSQL", "better-sqlite3 11.x / pg 8.x manifests", "Persistence", "DATABASE_PATH or DATABASE_URL", "Database contains user/scan data", "See backend/docs/azure-database.md", "Dependency licenses"],
            ],
            "test": ["DOC-VER-002", "FR01-FR08", "Automated inventory / environment check", "cd backend && npm test", "Node suite starts and runs", "Did not start: npm reported WSL 1 unsupported", "Blocked by environment", "backend/test/; docs/prototype-status.md", UPDATED],
            "risk": ["RISK-BE-001", "Integration", "Static ML absent; sandbox/LLM external", "No complete layered pipeline", "Certain by default", "Expose stage status honestly; integrate one versioned boundary at a time", "D.G / integration", "Requires scheduling", "Open"],
            "artifact": ["Backend component record", "Current status and handoff", "docs/components/backend.md", UPDATED, "Documentation update", "Requires team confirmation", "Links authoritative backend contracts"],
            "doc": "docs/components/backend.md",
        },
        "documentation": {
            **shared,
            "component": {
                "title": "Documentation and all-rounder record",
                "status": "Implemented",
                "present_implementation": [
                    "Evidence JSON, root README, project overview, architecture, setup/operations, prototype status, document index, and six component records were created or reconciled.",
                    "All seven team forms and the project-wide Word record were populated from the same evidence and retain explicit unknown markers for facts requiring team confirmation.",
                ],
                "interfaces": [
                    "Source, configuration, schemas, and observed test commands feed docs/documentation-evidence.json.",
                    "Markdown and Word records consume the same maturity vocabulary, repository paths, risks, and verification outcomes.",
                ],
                "tests": {
                    "inventory": ["Documentation tests cover evidence schema/paths, Markdown files/links, Office package structure/placeholders, and cross-format consistency."],
                    "observed": ["Evidence and Markdown checks passed before Word generation; Word ZIP/XML checks passed after generation."],
                    "historical": [],
                },
                "limitations": [
                    "Component-owner review and approval are not recorded.",
                    "Word package structure and extracted content were checked, but pagination and visual layout require Microsoft Word or LibreOffice review.",
                    "Several application test suites remain blocked by the documented environment/dependency limitations.",
                ],
                "risks": [
                    "Unknown team decisions may require revisions after owner review.",
                    "Documentation will drift if future code changes do not update the evidence record and regenerate forms.",
                ],
            },
            "owner": "Cade (assigned member; confirmation required)",
            "milestone": "Current-version documentation package",
            "status": "Ready for team review; approvals and missing team evidence remain",
            "requirements": "FR01, FR07, FR08; NFR Usability, Maintainability; project-wide traceability",
            "special": {
                "Artifact": "Evidence-first Markdown package and eight role/project Word records.",
                "Owner": "Cade / assigned component owners; confirmation required.",
                "Purpose": "Record architecture, setup, maturity, requirements, tests, risks, and handoff without overstating the prototype.",
                "Location": "README.md; docs/; Sentinel_*_Documentation_*.docx.",
                "Version or date": UPDATED,
                "Status": "Generated from source evidence; team review pending.",
                "Reviewer": "Requires team confirmation.",
                "Missing information": "Approvals, actual milestone dates, sandbox environment, dataset/model metrics, provider/model details, and visual Word QA.",
                "Flow name": "Local username/password session authentication (not Gmail/OAuth).",
                "Provider": "Sentinel backend; no external identity provider in this branch.",
                "Entry point": "website/index.html and /api/auth/register or /api/auth/login.",
                "Callback or redirect": "No OAuth callback; browser redirects to dashboard/home.html after success.",
                "Scopes": "No roles/scopes; signed-in owner or guest scan scope.",
                "Token or session storage": "HttpOnly cookie; SHA-256 of random session token stored server-side.",
                "User record fields": "id, normalized username/display username, scrypt password hash, timestamps.",
                "Failure behavior": "Stable JSON errors; generic invalid credentials; temporary lockout after configured failures.",
                "Security controls": "Scrypt, HttpOnly/SameSite cookie, optional Secure, hashed tokens, CORS allowlist.",
                "Setup steps": "Run backend, register/login or use guest; see docs/setup-and-operations.md.",
                "Test evidence": "backend/test/auth.test.js inventory; current execution blocked by WSL 1 npm.",
                "Milestone": "Documentation reconciliation for current prototype.",
                "Planned date": "Not recorded.",
                "Actual date": UPDATED,
                "Completed work": "README, overview, architecture, setup, status, index, six component records, evidence JSON, Word forms.",
                "Evidence": "docs/documentation-index.md and docs/prototype-status.md.",
                "Open dependencies": "Team review plus missing sandbox/model/LLM evidence.",
                "Documentation received": "Backend and malware-detection detailed records; source-derived records for remaining components.",
                "Follow-up owner": "Cade and each assigned component owner; confirmation required.",
            },
            "interfaces": [["Documentation evidence record", "Source/config/tests", "Markdown and Word forms", "JSON plus repository paths", "docs/documentation-evidence.json", UPDATED, "Validation rejects missing paths/statuses", "Cade / integration"]],
            "dependencies": [["Python 3 standard library", "System Python", "Word generation and validation", "scripts/update_documentation_forms.py", "No", "No third-party documentation package required", "PSF"]],
            "test": ["DOC-VER-DOC", "NFR Maintainability", "Automated documentation integrity", "python3 -m unittest discover -s tests/documentation -v", "Evidence, links, Word structure, and consistency pass", "See current command output", "Pass when generator completes", "tests/documentation/test_documentation.py", UPDATED],
            "risk": ["RISK-DOC-001", "Documentation", "Team approvals and several subsystem facts are unavailable", "Submission may lack authoritative owner confirmation", "High", "Mark unknowns explicitly; obtain owner review", "Cade / component owners", "Before documentation freeze", "Open"],
            "artifact": ["Documentation index", "Map authoritative sources and Word forms", "docs/documentation-index.md", UPDATED, "Documentation update", "Requires team confirmation", "Primary navigation record"],
            "doc": "docs/documentation-index.md",
        },
        "dynamic_analysis": {
            **shared,
            "component": components["dynamic_analysis"],
            "owner": "Vincent and Jarrel (assigned members; confirmation required)",
            "milestone": "Sandbox implementation and safety evidence required",
            "status": "Stubbed/configurable; real isolation not verified",
            "requirements": "FR04, FR05, FR06, FR07; NFR Safety, Maintainability",
            "special": {
                "Hypervisor and version": NOT_AVAILABLE,
                "Guest OS image and patch level": NOT_AVAILABLE,
                "Network isolation mode": "Not recorded; must be validated before real detonation.",
                "Snapshot or reset strategy": "Not recorded; referenced behavior is absent from this branch.",
                "Execution timeout": "Backend requests 15 seconds by default; guest enforcement is not verified.",
                "Resource limits": "Not recorded.",
                "Host protections": "Backend serializes calls; this is not host containment evidence.",
                "Malware sample handling procedure": "Not recorded. Use inert fixtures only until approved.",
                "Event source": "Expected sandbox/Sysmon-like JSON; producer implementation absent.",
                "Fields captured": "Expected processes, files, registry, network, DNS, remote threads, summary counts.",
                "Timestamp format": "Not confirmed with a producer.",
                "Process correlation method": "Not recorded.",
                "Output format and location": "JSON response to POST /detonate; backend stores raw stage report.",
                "Example or schema link": "backend/src/adapters/sandboxToMl.js; docs/components/dynamic-analysis.md.",
                "Known blind spots": "No implementation; remote threads may be zero-filled with an adapter note.",
                "Isolation test performed": "No real isolation test performed from this branch.",
                "Expected result": "Guest cannot reach prohibited resources; host remains isolated; snapshot restores known state.",
                "Actual result": "Not verified.",
                "Evidence link": "docs/components/dynamic-analysis.md.",
                "Reviewer": "Requires independent safety review.",
                "Date": UPDATED,
                "Open safety concern": "Critical: executing real malware without validated containment could compromise host/network.",
            },
            "interfaces": [["Sandbox detonation HTTP", "External sandbox (absent)", "Backend", "Multipart /detonate → JSON", "backend/src/stages/sandboxClient.js", "Unversioned", "Timeout/status/JSON/telemetry failure stored", "Vincent, Jarrel / D.G"]],
            "dependencies": [["Sandbox service and Windows VM", NOT_AVAILABLE, "Isolated execution and telemetry", "SANDBOX_URL", "Malware and telemetry", "Do not enable for real malware without validation", "Not recorded"]],
            "test": ["DOC-VER-DA", "FR04-FR05 / NFR Safety", "Mock integration inventory", "backend/test/sandboxStages.test.js", "Client/adapter failure behavior passes; real isolation separately validated", "Node suite did not start; no real VM test", "Not verified", "docs/components/dynamic-analysis.md", UPDATED],
            "risk": ["RISK-001", "Safety", "Sandbox implementation and containment evidence absent", "Critical host/network compromise risk", "Medium if real malware used", "Use inert fixtures; require independent isolation/reset validation", "Vincent / Jarrel", "Before detonation", "Open"],
            "artifact": ["Dynamic-analysis component record", "Present adapter and missing safety controls", "docs/components/dynamic-analysis.md", UPDATED, "Documentation update", "Requires team confirmation", "No sandbox source in branch"],
            "doc": "docs/components/dynamic-analysis.md",
        },
        "frontend": {
            **shared,
            "component": components["frontend"],
            "owner": "Sebastian (assigned member; confirmation required)",
            "milestone": "Submission/progress integrated; reports view pending",
            "status": "Partial",
            "requirements": "FR01-FR08; NFR Usability, Performance, Maintainability",
            "special": {
                "Screen or route": "index.html; dashboard/home.html; dashboard/reports.html.",
                "User goal": "Authenticate or enter as guest, submit file/URL, watch stage progress, later review history.",
                "Components": "Static HTML/CSS/JS, api.js Fetch wrapper, progress/coin UI.",
                "Data source": "Backend /api auth and sample endpoints; reports page currently uses empty array.",
                "Loading state": "Buttons disabled; Submitting/Scanning messages; per-stage Running labels.",
                "Empty state": "Reports page is blank/unexplained; requires implementation.",
                "Error state": "Backend message or safe fallback; polling retries network failures.",
                "Accessibility notes": "Text labels accompany animation; live announcements, focus management, and audit remain.",
                "Screenshot or design link": "Not recorded; source is website/.",
                "Accepted type": "Browser file picker accepts .exe; API also supports HTTP(S) URL.",
                "Client validation": "Extension check, nonempty URL/password, matching registration passwords.",
                "Maximum size": "Backend default 25 MiB; frontend does not display the limit.",
                "Progress behavior": "Polls sample view and maps stored stages to six conceptual steps.",
                "Cancellation behavior": "No server cancellation; Scan another clears UI polling after completion.",
                "Success transition": "Shows terminal summary and Scan another button.",
                "Failure message": "Uses backend message when present; otherwise local fallback.",
                "Security warning": "No in-page malware safety warning; documentation says inert fixtures only.",
                "Metric or telemetry displayed": "Stage status only in current UI; detailed scores/telemetry/report not rendered.",
                "Visual form": "Animated coins plus Waiting/Running/Complete/Failed/Skipped text.",
                "Scale or threshold": "Not applicable; scores not displayed.",
                "Interpretation shown to user": "Completion/skipping summary; no risk interpretation.",
                "Color accessibility": "Text status is present; contrast and color-blind testing not recorded.",
                "Source field": "sample.status and results[].stage/status/error.",
                "Test evidence": "No frontend suite; backend endpoint tests exist but were not run here.",
            },
            "interfaces": [["Dashboard REST API", "Backend", "Browser frontend", "JSON/multipart plus HttpOnly cookie", "website/api.js; backend/docs/api-contract.md", "Current prototype", "Network retry or visible error", "Sebastian / D.G"]],
            "dependencies": [["Modern browser", "Fetch/FormData support", "Render dashboard and call API", "window.SENTINEL_API_BASE / CORS_ORIGINS", "Session cookie and report data", "Serve from backend at localhost:3000", "Browser-dependent"]],
            "test": ["DOC-VER-FE", "FR01 / FR07 / NFR Usability", "Source and API inventory", "Manual/browser suite not present", "Submission, polling, failure, history, accessibility tested", "No browser automation run; reports page disconnected", "Not verified", "docs/components/frontend.md", UPDATED],
            "risk": ["RISK-FE-001", "Usability/Security", "Reports page will need safe server-data rendering", "XSS or misleading empty/history view if integrated poorly", "Medium", "Use DOM textContent, scope by owner, add browser/accessibility tests", "Sebastian", "Before history integration", "Open"],
            "artifact": ["Frontend component record", "Screens, workflow, API, gaps", "docs/components/frontend.md", UPDATED, "Documentation update", "Requires team confirmation", "Reports integration explicitly partial"],
            "doc": "docs/components/frontend.md",
        },
        "llm_threat_intelligence": {
            **shared,
            "component": components["llm_threat_intelligence"],
            "owner": "J.J (assigned member; confirmation required)",
            "milestone": "Versioned report/LLM implementation required",
            "status": "Stubbed/configurable; external component absent",
            "requirements": "FR06, FR07; NFR Explainability, Usability, Maintainability",
            "special": {
                "Provider and model": NOT_AVAILABLE,
                "API or SDK version": NOT_AVAILABLE,
                "Temperature and limits": "Provider settings not recorded; adapter bounds event and indicator counts.",
                "Prompt version": "Not recorded; external component absent.",
                "Input fields": "Signature/static/sandbox/behavioral reports plus file hash, submitted URL/host, public domains/IPs.",
                "Output schema": "Bridge returns threat-intelligence results and prompt; explanation/ATT&CK schema not defined.",
                "Timeout and retry behavior": "30-second backend default; no retry; failure isolated to llm stage.",
                "Cost or token controls": "Not recorded.",
                "Data sent externally": "No provider call in this branch. If enabled, the bridge receives bounded reports, submitted URLs, raw telemetry fields, and candidate indicators.",
                "Redaction or minimization": "Selected standalone private/loopback/link-local IP indicators are filtered. Submitted URLs and raw telemetry are not redacted; lists are only bounded and no full policy exists.",
                "Prompt purpose": "Planned evidence-grounded explanation, ATT&CK mapping, and recommendations.",
                "System instructions": "Not recorded.",
                "Evidence supplied": "Earlier stage reports and bounded indicator list; failed/missing stages remain absent.",
                "Required citations or evidence references": "Not implemented; should link each claim to stage/field.",
                "Hallucination controls": "Not implemented beyond bounded structured input.",
                "Fallback behavior": "Stage fails independently; structured earlier results remain available.",
                "Prompt artifact link": "Not available in this branch.",
                "Observed behavior": "No generated LLM explanation or real MITRE mapping available.",
                "Mapped tactic": "Not evaluated.",
                "Mapped technique": "Not evaluated.",
                "Evidence": "backend/src/adapters/llmInput.js and docs/components/llm-threat-intelligence.md.",
                "Confidence": "Not defined.",
                "Reviewer decision": "Requires threat-intelligence review after implementation.",
                "False mapping notes": "No mapping dataset/results available.",
            },
            "interfaces": [["Threat-intelligence bridge", "Backend pipeline", "External Python component (absent)", "JSON stdin/stdout", "backend/scripts/llm_bridge.py", "Unversioned", "Missing/import/timeout/nonzero/JSON failures stored", "J.J / D.G"]],
            "dependencies": [["External component/provider", NOT_AVAILABLE, "Enrichment and report generation", "LLM_DIR and external credentials", "Telemetry, indicators, credentials", "Privacy/cost review required", "Not recorded"]],
            "test": ["DOC-VER-LLM", "FR06 / NFR Explainability", "Mock adapter/bridge inventory", "backend/test/llmStage.test.js", "Filtering, bounding, ordering, failures pass; real mapping separately validated", "Node suite did not start; no provider tested", "Not verified", "docs/components/llm-threat-intelligence.md", UPDATED],
            "risk": ["RISK-LLM-001", "Privacy/accuracy", "External disclosure and unsupported generated claims", "Sensitive data exposure or analyst misdirection", "High if enabled without controls", "Versioned schema, citations, redaction, provider policy, human mapping review", "J.J / integration", "Before provider use", "Open"],
            "artifact": ["LLM/threat-intelligence component record", "Present adapter and missing implementation controls", "docs/components/llm-threat-intelligence.md", UPDATED, "Documentation update", "Requires team confirmation", "No provider/model claim"],
            "doc": "docs/components/llm-threat-intelligence.md",
        },
        "machine_learning": {
            **shared,
            "component": components["machine_learning"],
            "owner": "Axel P and Diego (assigned members; confirmation required)",
            "milestone": "Dataset/model evidence and static ML integration required",
            "status": "Partial",
            "requirements": "FR03, FR05-FR08; NFR Explainability, Performance, Maintainability",
            "special": {
                "Dataset name and version": NOT_AVAILABLE,
                "Source and license": "Not recorded; no dataset committed.",
                "Collection dates": "Not recorded.",
                "Benign count": "Not recorded.",
                "Malicious count": "Not recorded.",
                "Families represented": "Not recorded.",
                "Label method": "Not recorded.",
                "Deduplication method": "Not recorded.",
                "Train validation test split": "Not recorded.",
                "Leakage checks": "Not recorded.",
                "Storage and access controls": "No data committed; required before dataset use.",
                "Model name and version": "No artifact included; scripts support Random Forest and Isolation Forest.",
                "Task": "Behavioral malicious-risk classification and novelty detection; static classifier missing.",
                "Algorithm and library versions": "scikit-learn via requirements.txt; exact installed version not observed.",
                "Input feature schema": "Nine behavioral counts/flags documented in docs/components/machine-learning.md.",
                "Training configuration": "Random Forest default 200 trees; Isolation Forest configurable contamination; no recorded run.",
                "Threshold selection": "Default heuristic/model threshold from ML/config.py; no calibration evidence.",
                "Accuracy": "Not available; no evaluation artifact.",
                "Precision": "Not available; no evaluation artifact.",
                "Recall": "Not available; no evaluation artifact.",
                "F1": "Not available; no evaluation artifact.",
                "ROC AUC": "Not available; no evaluation artifact.",
                "False positive rate": "Not available; no evaluation artifact.",
                "False negative rate": "Not available; no evaluation artifact.",
                "Explainability method": "Heuristic evidence strings; trained feature importance not exported.",
                "Known limitations": "No dataset/artifact/metrics/static model; heuristic score is not calibrated probability.",
                "Artifact location": "No .joblib artifact committed.",
                "Families withheld": "Not recorded; experiment not run.",
                "Reason for selection": "Not recorded.",
                "Sample counts": "Not recorded.",
                "Baseline result": "Not available.",
                "Layered pipeline result": "Not available.",
                "Interpretation": "No held-out-family conclusion can be made.",
                "Reproduction command": "Not available until dataset/model versions exist.",
                "Evidence link": "docs/components/machine-learning.md; docs/prototype-status.md.",
            },
            "interfaces": [["Behavioral ML HTTP", "ML/predict.py", "Backend", "POST telemetry JSON → score/evidence JSON", "ML/predict.py; backend/src/adapters/sandboxToMl.js", "Unversioned", "400 for invalid input; backend stores stage failure", "Axel P, Diego / D.G"]],
            "dependencies": [["Python ML stack", "joblib, numpy, scikit-learn", "Training/inference/evaluation", "requirements.txt", "Models/data may be sensitive", "Use isolated environment and trusted joblib files", "Dependency licenses"]],
            "test": ["DOC-VER-004", "FR05 / NFR Maintainability", "Unit/integration module", "cd ML && python3 -m unittest test_report_parser -v", "15 tests run", "Import blocked: joblib missing; no assertions ran", "Blocked by dependency", "ML/test_report_parser.py", UPDATED],
            "risk": ["RISK-003", "Data/model quality", "No provenance, artifact, metrics, or held-out-family evidence", "Cannot assess accuracy, bias, leakage, or licensing", "Certain", "Create dataset/model cards and reproducible evaluation", "Axel P / Diego", "Before performance claims", "Open"],
            "artifact": ["Machine-learning component record", "Feature/model/data/evaluation status", "docs/components/machine-learning.md", UPDATED, "Documentation update", "Requires team confirmation", "Metrics intentionally not invented"],
            "doc": "docs/components/machine-learning.md",
        },
        "malware_detection": {
            **shared,
            "component": components["malware_detection"],
            "owner": "Kyle (assigned member; confirmation required)",
            "milestone": "Analyzer 1.2.0 implemented; current-environment verification pending",
            "status": "Implemented; tests blocked locally by missing pefile",
            "requirements": "FR02, FR03, FR06, FR07; NFR Explainability, Performance, Maintainability",
            "special": {
                "Catalog or source": "Optional offline SQLite SHA-256 reputation cache; backend also has a separate safe demonstration catalog.",
                "Version or retrieval date": "Cache-specific metadata; no production cache committed or selected.",
                "Lookup method": "Exact lowercase SHA-256 in offline cache; no network access during analysis.",
                "Update process": "update_reputation.py imports hash list/MalwareBazaar CSV or controlled download with atomic replacement.",
                "License or use restriction": "Must be recorded per selected feed; not established here.",
                "Failure behavior": "Missing/corrupt/invalid cache becomes unavailable, never a benign result.",
                "Coverage limitation": "Entirely dependent on supplied cache date/source/scope.",
                "Rule name and version": "Optional trusted YARA source; example malware_detection/rules/wannacry.yar.",
                "Purpose": "Match curated byte/string conditions and return structured evidence.",
                "Author or source": "Per rule metadata; included rule license/readme in malware_detection/rules/.",
                "Indicators": "Rule-defined strings/conditions; report includes identifiers, offsets, and bounded data.",
                "Tags": "Rule tags/namespaces preserved in report.",
                "Test samples": "Generated inert/synthetic PEs and controlled rule content; no malware committed.",
                "False positive checks": "Test coverage exists; broader benign corpus evaluation not recorded.",
                "Performance notes": "Positive timeout required; input capture bounded; no benchmark recorded.",
                "Rule file link": "malware_detection/rules/wannacry.yar and rules/README.md.",
                "Feature name": "SHA-256; PE headers; sections/entropy/permissions; imports/delay imports; strings; resources; warnings; reputation/YARA states.",
                "Extraction method": "One bounded consistent byte capture parsed with pefile and component helpers.",
                "Data type": "Versioned JSON report schema 1.2.0.",
                "Missing or malformed behavior": "Controlled stderr/nonzero exit or explicit unavailable/error evidence state.",
                "Normalization": "Stable counts/lists, UTC timestamp, section permissions, bounded samples, deterministic JSON.",
                "Consumer": "Backend static_analysis stage, future static ML, dashboard, threat report.",
                "Unit test or sample evidence": "Six test modules; current run blocked at import without pefile.",
            },
            "interfaces": [["Static analyzer CLI", "malware_detection/analyze.py", "Backend/CLI", "PE path → JSON stdout", "malware_detection/REPORT_CONTRACT.md", "1.2.0", "Controlled stderr/nonzero; no success JSON on error", "Kyle"]],
            "dependencies": [["Python/pefile", "requirements manifest", "PE parsing", "malware_detection/requirements.txt", "Reports may be sensitive", "Use virtual environment", "PSF/dependency licenses"]],
            "test": ["DOC-VER-003", "FR02 / NFR Explainability", "Python suite", "python3 -m unittest discover -s malware_detection/tests -v", "All modules import and assertions run", "Six modules failed import: pefile missing", "Blocked by dependency", "malware_detection/tests/", UPDATED],
            "risk": ["RISK-MD-001", "Interpretation", "No match or unavailable feed/rules may be mistaken for benign", "False reassurance", "Medium", "Expose evidence state and limitations; never emit benign from absence", "Kyle / consumers", "Ongoing", "Open"],
            "artifact": ["Static analyzer report contract", "Versioned producer/consumer evidence schema", "malware_detection/REPORT_CONTRACT.md", "1.2.0", "Malware-detection team", "Requires current team confirmation", "Authoritative narrow contract"],
            "doc": "docs/components/malware-detection.md",
        },
    }


def populate_team_form(document: ET.Element, form_key: str, evidence: dict[str, Any]) -> None:
    spec = form_specs(evidence)[form_key]
    tables = list(document.iter(f"{W}tbl"))

    set_field(tables[0], "Document owner", spec["owner"])
    set_field(tables[0], "Last updated", UPDATED)
    set_field(tables[0], "Repository and branch", spec["repository"])
    set_field(tables[0], "Current milestone", spec["milestone"])
    set_field(tables[0], "Status", spec["status"])
    set_field(tables[1], "Related proposal requirements", spec["requirements"])
    set_field(tables[1], "Scope changes approved after proposal", spec["scope"])

    change_id = CHANGE_IDS[form_key]
    upsert_row(tables[2], 1, change_id, [
        UPDATED,
        change_id,
        "Evidence-first documentation reconciliation for current prototype",
        "Align Word record with source, tests, Markdown, and actual branch contents",
        f"{spec['doc']}; docs/prototype-status.md; this form",
        spec["requirements"],
        "tests/documentation/test_documentation.py",
        "Not committed during update",
        "Documentation update (AI-assisted; team review required)",
        "Requires team confirmation",
    ])

    for values in spec["interfaces"]:
        upsert_row(tables[3], 0, values[0], values)
    for values in spec["dependencies"]:
        upsert_row(tables[4], 0, values[0], values)

    for table in tables[5:8]:
        for label, value in spec["special"].items():
            try:
                set_field(table, label, value)
            except KeyError:
                pass

    # Backend has two different rows labeled Purpose in adjacent record
    # tables. Keep their meanings distinct after the generic label fill.
    if form_key == "backend":
        remove_rows_by_key(tables[3], 0, {"Static analyzer CLI"})
        remove_rows_by_key(tables[11], 0, {"R-02", "R-03", "R-04"})
        set_field(tables[5], "Purpose", "Account/guest access, submission, queued analysis, status/results, and paged history.")
        set_field(tables[6], "Purpose", "Persist accounts, session hashes, submissions, queue state, and stage output.")
    elif form_key == "malware_detection":
        remove_rows_by_key(tables[3], 0, {"Future Node link"})

    decision_id = f"DEC-20261103-{form_key.upper()}"
    upsert_row(tables[8], 1, decision_id, [
        UPDATED,
        decision_id,
        "How should unverified or absent prototype work be reported?",
        "Infer completion; repeat historical claims; label status from current evidence",
        "Use controlled maturity labels and explicit unknown markers",
        "Prevents planned or blocked work from being presented as verified",
        "More visible gaps; simpler future reconciliation",
        "Team confirmation required",
    ])
    upsert_row(tables[9], 0, spec["test"][0], spec["test"])
    fill_quality_review(tables[10], spec["owner"], spec["component"]["status"])
    upsert_row(tables[11], 0, spec["risk"][0], spec["risk"])
    upsert_row(tables[12], 0, spec["artifact"][0], spec["artifact"])

    handoff = base_handoff(spec["component"], spec["doc"])
    for label, value in handoff.items():
        set_field(tables[13], label, value)

    replace_response_placeholders(document, UNKNOWN)
    complete_record_tables(document)


def populate_project_record(document: ET.Element, evidence: dict[str, Any]) -> None:
    tables = list(document.iter(f"{W}tbl"))
    set_field(tables[0], "Documentation coordinator", "Cade (assigned; confirmation required)")
    set_field(tables[0], "Last updated", UPDATED)
    set_field(tables[0], "Documentation freeze date", "Not recorded; requires team confirmation.")
    set_field(tables[0], "Final report location", "Not recorded; current documentation index: docs/documentation-index.md.")

    title_map = {key: value["title"] for key, value in evidence["components"].items()}
    for requirement_id, record in evidence["requirements"].items():
        owners = ", ".join(title_map.get(owner, owner) for owner in record["responsible_components"])
        implementation = "; ".join(record["implementation_evidence"]) or "No implementation evidence"
        tests = "; ".join(record["test_evidence"]) or "No test evidence recorded"
        for row in table_rows(tables[1])[1:]:
            cells = row_cells(row)
            if cells and element_text(cells[0]) == requirement_id:
                values = [requirement_id, record["requirement"], owners, implementation, tests, record["status"]]
                for cell, value in zip(cells, values):
                    set_cell_text(cell, value)
                break

    milestone_states = {
        "Architecture and Setup": ("Shared integration lead", "Core architecture and setup docs present", "docs/architecture.md", "Partial", "External environment decisions remain"),
        "Static Analysis Pipeline": ("Kyle / D.G", "Analyzer and backend boundary present", "malware_detection/REPORT_CONTRACT.md", "Implemented", "Real analyzer is opt-in; current test dependency missing"),
        "Static ML Classifier": ("Axel P / Diego", "Static probability integrated", "docs/components/machine-learning.md", "Planned/not present", "No static model/stage/artifact"),
        "Dynamic Sandbox": ("Vincent / Jarrel", "Isolated resettable detonation", "docs/components/dynamic-analysis.md", "Stubbed/configurable", "Service, VM, and safety evidence absent"),
        "Behavioral Features": ("Axel P / Diego", "Validated telemetry features", "ML/report_parser.py", "Partial", "No real sandbox/model artifact"),
        "LLM Integration": ("J.J", "Evidence-grounded ATT&CK report", "docs/components/llm-threat-intelligence.md", "Stubbed/configurable", "External component/provider/model absent"),
        "Dashboard Development": ("Sebastian", "Submission plus report/history UI", "docs/components/frontend.md", "Partial", "History/detail view incomplete"),
        "Integration and System Testing": ("Shared integration lead", "End-to-end verified pipeline", "docs/prototype-status.md", "Not verified", "Blocked suites and absent services"),
        "Evaluation and Final Capstone Report": ("Cade / all teams", "Reproducible metrics and final package", "docs/documentation-index.md", "Partial", "Metrics/approvals/final location absent"),
    }
    for row in table_rows(tables[2])[1:]:
        cells = row_cells(row)
        if len(cells) < 8:
            continue
        milestone = element_text(cells[1])
        owner, exit_state, artifact, status, notes = milestone_states.get(milestone, (UNKNOWN, UNKNOWN, UNKNOWN, "Not verified", UNKNOWN))
        for index, value in enumerate([owner, exit_state, "Requires team confirmation", artifact, status, notes], start=2):
            set_cell_text(cells[index], value)

    architecture_fields = {
        "Architecture diagram link": "docs/architecture.md",
        "Deployment diagram link": "docs/architecture.md#deployment-shapes",
        "Primary technology stack": "Static HTML/CSS/JS; Node.js/Express; SQLite or PostgreSQL; Python pefile/scikit-learn/joblib.",
        "Repository structure": "README.md and docs/documentation-index.md.",
        "Environment definitions": "backend/.env.example and docs/setup-and-operations.md.",
        "Shared data contracts": "backend/docs/api-contract.md; malware_detection/REPORT_CONTRACT.md; adapter contracts are currently unversioned.",
        "Authentication approach": "Local username/password; scrypt hash; HttpOnly cookie; hashed server-side token; optional guest.",
        "Logging and observability": "Stage/job states and errors in database; console errors; no production observability stack.",
        "Build and deployment process": "npm install + backend start for local demo; no production deployment pipeline documented.",
    }
    for label, value in architecture_fields.items():
        set_field(tables[3], label, value)

    interfaces = [
        ["IF-API", "Backend", "Frontend", "Authentication, submission, status, history", "backend/docs/api-contract.md", "Current prototype", "backend/test/samples.test.js; auth.test.js", "Integrated", "D.G / Sebastian"],
        ["IF-STATIC", "Malware detection", "Backend", "PE evidence report", "malware_detection/REPORT_CONTRACT.md", "1.2.0", "realAnalyzer.test.js; component tests", "Integrated; not verified here", "Kyle / D.G"],
        ["IF-SANDBOX", "External sandbox", "Backend/ML", "Detonation telemetry", "backend adapters; producer absent", "Unversioned", "sandboxStages.test.js mocks", "Stubbed/configurable", "Vincent, Jarrel / D.G / ML"],
        ["IF-LLM", "Backend", "External threat-intelligence component", "Bounded evidence and indicators", "backend adapter/bridge", "Unversioned", "llmStage.test.js mocks", "Stubbed/configurable", "J.J / D.G"],
    ]
    for values in interfaces:
        upsert_row(tables[4], 0, values[0], values)

    upsert_row(tables[5], 1, "PW-DOC-DECISION", [UPDATED, "PW-DOC-DECISION", "How should current maturity be reported?", "Infer; historical claims; evidence labels", "Use controlled evidence labels", "Avoid overstating prototype", "All teams", "Team confirmation required", "docs/prototype-status.md"])
    upsert_row(tables[6], 0, CHANGE_IDS["project"], [CHANGE_IDS["project"], "Documentation update", "Reconcile Markdown and all Word records", "Improves accuracy; exposes gaps", "All teams", "Applied for review", "Requires team confirmation", UPDATED, "Owners review and approve"])

    for risk in evidence["risks"]:
        upsert_row(tables[7], 0, risk["id"], [risk["id"], risk["type"], risk["description"], risk["impact"], risk["likelihood"], risk["mitigation"], "Assigned owner requires confirmation", "Requires scheduling", risk["status"], "Escalate before affected capability is claimed or enabled"])

    for verification in evidence["verification"]:
        upsert_row(tables[8], 0, verification["id"], [verification["id"], verification["scope"], "See linked requirements/components", verification["scope"], "2026-11-03 documentation environment", "Command runs with prerequisites", verification["result"], verification["status"], "; ".join(verification["evidence_paths"]), "Environment/dependency block where noted"])

    safety_values = {
        "Sandbox cannot reach prohibited host or network resources": ("Vincent / Jarrel", "No sandbox implementation or test", "Not verified"),
        "Sandbox resets to a known state after execution": ("Vincent / Jarrel", "No snapshot/reset implementation in branch", "Not verified"),
        "Malware samples are stored and handled according to the team procedure": ("All analysis teams", "No approved handling procedure recorded", "Not verified"),
        "Secrets and credentials are absent from source and reports": ("All teams", "Environment templates and gitignore exist; full secret scan not recorded", "Partial"),
        "Demo inputs and expected outputs are prepared": ("Integration lead", "Inert backend fixture and safe catalog indicators exist", "Partial"),
        "Failure and timeout paths are demonstrated safely": ("Backend / integration", "Mock tests inventory exists; current Node run blocked", "Not verified in current environment"),
    }
    for row in table_rows(tables[9])[1:]:
        cells = row_cells(row)
        check = element_text(cells[0])
        owner, proof, result = safety_values.get(check, (UNKNOWN, UNKNOWN, "Not verified"))
        for cell, value in zip(cells[1:], [owner, proof, result, UPDATED, "Requires team confirmation"]):
            set_cell_text(cell, value)

    upsert_row(tables[10], 0, "No completed evaluation", ["No completed evaluation", "No versioned dataset/family", "Not recorded", "No trained configuration", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "docs/components/machine-learning.md"])
    evaluation_fields = {
        "Main quantitative finding": "No quantitative finding is supported by artifacts in this branch.",
        "Contribution of each layer": "Not evaluated; default path demonstrates signature plus mock static analysis only.",
        "Held-out family result": "Not available; families, samples, split, artifacts, and commands are not recorded.",
        "Limitations": "No dataset/model cards, metrics, thresholds, or reproducible experiment output.",
        "Dataset version": "Not available.",
        "Threshold": "No evaluated threshold; heuristic default is not an experiment result.",
        "Reproduction command": "Not available until inputs and artifacts are versioned.",
    }
    for label, value in evaluation_fields.items():
        try:
            set_field(tables[11], label, value)
        except KeyError:
            pass

    for row in table_rows(tables[12])[1:]:
        cells = row_cells(row)
        section = element_text(cells[0])
        if len(cells) >= 7:
            values = ["Relevant team form and docs/documentation-index.md", "Cade / assigned owner", "Partial", "Requires team confirmation", "Final location not recorded", f"Current draft source for {section} is indexed; metrics/approvals remain where applicable."]
            for cell, value in zip(cells[1:], values):
                set_cell_text(cell, value)

    team_form_map = {
        "Dynamic Analysis": "docs/components/dynamic-analysis.md",
        "Machine Learning": "docs/components/machine-learning.md",
        "LLM Threat Intelligence": "docs/components/llm-threat-intelligence.md",
        "Backend Development": "docs/components/backend.md",
        "Frontend Development": "docs/components/frontend.md",
        "Malware Detection": "docs/components/malware-detection.md",
        "Documentation and All Rounder": "docs/documentation-index.md",
    }
    for row in table_rows(tables[13])[1:]:
        cells = row_cells(row)
        team = element_text(cells[0])
        if len(cells) >= 7:
            path = team_form_map.get(team, "docs/documentation-index.md")
            values = [element_text(cells[1]) or "Assigned owner; confirmation required", UPDATED, "Source-derived draft complete", "Requires owner review", f"Approvals and component-specific missing evidence; see {path}", "Mapped in docs/documentation-index.md"]
            for cell, value in zip(cells[1:], values):
                set_cell_text(cell, value)

    approvals = {
        "Documentation coordinator approval": "Project handoff draft prepared; coordinator approval requires confirmation.",
        "Integration lead approval": "Requires confirmation.",
        "Team approvals": "Requires each component owner to review current status and unknown markers.",
        "Approval date": "Not recorded.",
        "Final unresolved gaps": "Sandbox safety, static ML, datasets/models/metrics, LLM provider/report/mappings, frontend history/detail, full-suite execution.",
        "Freeze decision": "Not recorded; do not freeze until owners review gaps and Word visual layout.",
    }
    for label, value in approvals.items():
        try:
            set_field(tables[14], label, value)
        except KeyError:
            pass

    replace_response_placeholders(document, UNKNOWN)
    complete_record_tables(document)


def document_text(document: ET.Element) -> str:
    return "\n".join(node.text or "" for node in document.iter(f"{W}t"))


def validate_document(document: ET.Element, form_key: str) -> list[str]:
    text = document_text(document)
    errors: list[str] = []
    if FORM_TITLES[form_key] not in text:
        errors.append("expected title is missing")
    if UPDATED not in text:
        errors.append("current update date is missing")
    if text.count(CHANGE_IDS[form_key]) != 1:
        errors.append(f"{CHANGE_IDS[form_key]} must occur exactly once")
    for phrase in (
        "Enter current value",
        "Enter milestone",
        "Enter link or path",
        "Enter owner",
        "Enter date and time",
        "Planned / In progress / Blocked / Ready for review / Complete",
    ):
        if phrase in text:
            errors.append(f"unresolved response prompt: {phrase}")
    if form_key == "project":
        for index in range(1, 9):
            if f"FR0{index}" not in text:
                errors.append(f"FR0{index} is missing")
        if "handoff" not in text.lower():
            errors.append("project handoff summary is missing")
    generic_types = {"Risk / Issue / Debt", "Risk / Issue / Dependency"}
    for table_index, table in enumerate(document.iter(f"{W}tbl")):
        for row_index, row in enumerate(table_rows(table)[1:], start=1):
            values = [element_text(cell) for cell in row_cells(row)]
            location = f"table {table_index}, row {row_index}"
            if not any(values):
                errors.append(f"unused record row at {location}")
            elif any(value in generic_types for value in values):
                errors.append(f"generic risk prompt at {location}")
            elif any(not value for value in values):
                errors.append(f"unmarked unknown response at {location}")
    return errors


def read_document_xml(path: Path) -> ET.Element:
    with ZipFile(path) as package:
        return ET.fromstring(package.read("word/document.xml"))


def write_document(template: Path, target: Path, document: ET.Element) -> None:
    if target.suffix.lower() != ".docx":
        raise ValueError(f"Refusing to write non-docx target: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    preserve_ignorable_namespaces(document)
    xml_bytes = ET.tostring(document, encoding="utf-8", xml_declaration=True)
    with tempfile.NamedTemporaryFile(prefix=f".{target.stem}-", suffix=".docx", dir=target.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(template) as source, ZipFile(temporary, "w", compression=ZIP_DEFLATED) as output:
            for info in source.infolist():
                data = xml_bytes if info.filename == "word/document.xml" else source.read(info.filename)
                output.writestr(info, data)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_evidence(source_root: Path) -> dict[str, Any]:
    path = source_root / "docs" / "documentation-evidence.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    required = {"metadata", "components", "requirements", "verification", "risks", "artifacts"}
    missing = required - set(evidence)
    if missing:
        raise ValueError(f"Evidence record is missing keys: {sorted(missing)}")
    return evidence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="Repository root containing evidence JSON.")
    parser.add_argument("--template-dir", type=Path, help="Directory containing the eight input templates; defaults to source root.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for populated Word files.")
    parser.add_argument("--check", action="store_true", help="Validate existing files in output-dir without changing them.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    template_dir = (args.template_dir or source_root).resolve()
    output_dir = args.output_dir.resolve()
    evidence = load_evidence(source_root)

    failures: list[str] = []
    for form_key, filename in FORM_FILES.items():
        target = output_dir / filename
        if args.check:
            document = read_document_xml(target)
        else:
            template = template_dir / filename
            document = read_document_xml(template)
            if form_key == "project":
                populate_project_record(document, evidence)
            else:
                populate_team_form(document, form_key, evidence)
            errors = validate_document(document, form_key)
            if errors:
                failures.extend(f"{filename}: {error}" for error in errors)
                continue
            write_document(template, target, document)
        errors = validate_document(document, form_key)
        if errors:
            failures.extend(f"{filename}: {error}" for error in errors)
        else:
            print(f"OK: {target}")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
