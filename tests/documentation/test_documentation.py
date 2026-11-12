"""Integrity checks for Sentinel's generated documentation package."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = REPOSITORY_ROOT / "docs" / "documentation-evidence.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "metadata",
    "status_vocabulary",
    "components",
    "requirements",
    "verification",
    "risks",
    "artifacts",
}
REQUIRED_COMPONENTS = {
    "frontend",
    "backend",
    "malware_detection",
    "machine_learning",
    "dynamic_analysis",
    "llm_threat_intelligence",
}
REQUIRED_REQUIREMENTS = {
    "FR01",
    "FR02",
    "FR03",
    "FR04",
    "FR05",
    "FR06",
    "FR07",
    "FR08",
    "NFR Safety",
    "NFR Explainability",
    "NFR Usability",
    "NFR Performance",
    "NFR Maintainability",
}
ALLOWED_STATUSES = {
    "Implemented",
    "Integrated",
    "Partial",
    "Stubbed/configurable",
    "Planned/not present",
    "Not verified",
}
CORE_MARKDOWN_FILES = {
    "README.md",
    "docs/project-overview.md",
    "docs/architecture.md",
    "docs/setup-and-operations.md",
    "docs/prototype-status.md",
    "docs/documentation-index.md",
    "docs/components/frontend.md",
    "docs/components/backend.md",
    "docs/components/malware-detection.md",
    "docs/components/machine-learning.md",
    "docs/components/dynamic-analysis.md",
    "docs/components/llm-threat-intelligence.md",
}
WORD_FORMS = {
    "Sentinel_Backend_Development_Documentation_Form.docx": (
        "Backend Development Documentation Form",
        "BE-DOC-20261103",
    ),
    "Sentinel_Documentation_All_Rounder_Documentation_Form.docx": (
        "Documentation and All Rounder Documentation Form",
        "DOC-DOC-20261103",
    ),
    "Sentinel_Dynamic_Analysis_Documentation_Form.docx": (
        "Dynamic Analysis Documentation Form",
        "DA-DOC-20261103",
    ),
    "Sentinel_Frontend_Development_Documentation_Form.docx": (
        "Frontend Development Documentation Form",
        "FE-DOC-20261103",
    ),
    "Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx": (
        "LLM and Threat Intelligence Documentation Form",
        "LLM-DOC-20261103",
    ),
    "Sentinel_Machine_Learning_Documentation_Form.docx": (
        "Machine Learning Documentation Form",
        "ML-DOC-20261103",
    ),
    "Sentinel_Malware_Detection_Documentation_Form.docx": (
        "Malware Detection Documentation Form",
        "MD-DOC-20261103",
    ),
    "Sentinel_Project_Wide_Documentation_Record.docx": (
        "Project Wide Documentation Record",
        "PW-DOC-20261103",
    ),
}


def load_evidence() -> dict:
    with EVIDENCE_PATH.open(encoding="utf-8") as evidence_file:
        return json.load(evidence_file)


def collect_evidence_paths(value: object) -> list[str]:
    """Return repository paths stored in evidence-oriented fields."""

    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"path", "implementation_evidence", "test_evidence", "evidence_paths"}:
                if isinstance(item, str):
                    paths.append(item)
                elif isinstance(item, list):
                    paths.extend(entry for entry in item if isinstance(entry, str))
            else:
                paths.extend(collect_evidence_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(collect_evidence_paths(item))
    return paths


def extract_docx_text(path: Path) -> str:
    """Extract paragraph and table text from a WordprocessingML package."""

    with ZipFile(path) as package:
        document_xml = package.read("word/document.xml")
    root = ET.fromstring(document_xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    return "\n".join(node.text or "" for node in root.iter(f"{namespace}t"))


def extract_docx_rows(path: Path) -> list[list[str]]:
    """Return Word table rows as plain cell text for structural comparisons."""

    with ZipFile(path) as package:
        root = ET.fromstring(package.read("word/document.xml"))
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    rows: list[list[str]] = []
    for row in root.iter(f"{namespace}tr"):
        cells = []
        for cell in row.findall(f"{namespace}tc"):
            cells.append("".join(node.text or "" for node in cell.iter(f"{namespace}t")))
        rows.append(cells)
    return rows


class DocumentationEvidenceTests(unittest.TestCase):
    """Catch missing components, requirements, status drift, and dead evidence paths."""

    def test_evidence_record_has_required_schema(self) -> None:
        evidence = load_evidence()
        self.assertEqual(REQUIRED_TOP_LEVEL_KEYS, set(evidence))
        self.assertEqual(ALLOWED_STATUSES, set(evidence["status_vocabulary"]))

    def test_evidence_record_covers_every_component_and_requirement(self) -> None:
        evidence = load_evidence()
        self.assertEqual(REQUIRED_COMPONENTS, set(evidence["components"]))
        self.assertEqual(REQUIRED_REQUIREMENTS, set(evidence["requirements"]))

    def test_component_and_requirement_statuses_use_controlled_vocabulary(self) -> None:
        evidence = load_evidence()
        records = list(evidence["components"].values()) + list(evidence["requirements"].values())
        for record in records:
            self.assertIn(record["status"], ALLOWED_STATUSES)

    def test_repository_evidence_paths_exist(self) -> None:
        evidence = load_evidence()
        paths = collect_evidence_paths(evidence)
        self.assertGreater(len(paths), 20, "The evidence record should cite detailed repository evidence.")
        missing = sorted({path for path in paths if not (REPOSITORY_ROOT / path).exists()})
        self.assertEqual([], missing, f"Missing evidence paths: {missing}")

    def test_static_ml_requirement_is_not_overstated(self) -> None:
        evidence = load_evidence()
        fr03 = evidence["requirements"]["FR03"]
        self.assertEqual("Planned/not present", fr03["status"])
        self.assertIn("No static-feature model", fr03["gap"])

    def test_llm_privacy_record_describes_unredacted_paths(self) -> None:
        evidence = load_evidence()
        record = evidence["components"]["llm_threat_intelligence"]
        combined = " ".join(record["present_implementation"] + record["limitations"])
        self.assertIn("standalone IP indicators", combined)
        self.assertIn("submitted URLs", combined)
        self.assertIn("raw telemetry", combined)


class MarkdownDocumentationTests(unittest.TestCase):
    """Catch missing entry points, broken local links, and incomplete traceability."""

    def test_required_markdown_documents_exist(self) -> None:
        missing = sorted(path for path in CORE_MARKDOWN_FILES if not (REPOSITORY_ROOT / path).is_file())
        self.assertEqual([], missing, f"Missing Markdown documents: {missing}")

    def test_readme_links_to_every_core_document(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        required_links = {path for path in CORE_MARKDOWN_FILES if path != "README.md"}
        missing = sorted(path for path in required_links if f"({path})" not in readme)
        self.assertEqual([], missing, f"README navigation is missing: {missing}")

    def test_prototype_status_covers_requirements_components_and_statuses(self) -> None:
        text = (REPOSITORY_ROOT / "docs" / "prototype-status.md").read_text(encoding="utf-8")
        required_terms = REQUIRED_REQUIREMENTS | {
            "Frontend dashboard",
            "Backend API and orchestration",
            "Static malware detection and PE evidence",
            "Behavioral feature extraction and machine learning",
            "Dynamic sandbox integration",
            "LLM and threat-intelligence integration",
        }
        missing = sorted(term for term in required_terms if term not in text)
        self.assertEqual([], missing, f"Prototype status is missing: {missing}")
        for status in ALLOWED_STATUSES:
            self.assertIn(status, text)

    def test_markdown_has_no_workspace_paths_or_template_prompts(self) -> None:
        forbidden = (
            "/mnt/c/Users/",
            "Enter current value",
            "Enter milestone",
            "Enter link or path",
            "Planned / In progress / Blocked / Ready for review / Complete",
        )
        findings: list[str] = []
        for relative_path in CORE_MARKDOWN_FILES:
            path = REPOSITORY_ROOT / relative_path
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                if phrase in text:
                    findings.append(f"{relative_path}: {phrase}")
        self.assertEqual([], findings)

    def test_repository_relative_markdown_links_resolve(self) -> None:
        broken: list[str] = []
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for relative_path in CORE_MARKDOWN_FILES:
            document = REPOSITORY_ROOT / relative_path
            if not document.exists():
                continue
            text = document.read_text(encoding="utf-8")
            for target in link_pattern.findall(text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                resolved = (document.parent / target_path).resolve()
                if not resolved.exists():
                    broken.append(f"{relative_path} -> {target}")
        self.assertEqual([], sorted(broken), f"Broken local Markdown links: {broken}")


class WordDocumentationTests(unittest.TestCase):
    """Catch invalid Office packages, unfilled responses, and duplicate reconciliation rows."""

    def test_all_word_forms_are_valid_office_packages(self) -> None:
        errors: list[str] = []
        for filename in WORD_FORMS:
            path = REPOSITORY_ROOT / filename
            try:
                with ZipFile(path) as package:
                    if "word/document.xml" not in package.namelist():
                        errors.append(f"{filename}: missing word/document.xml")
            except (BadZipFile, FileNotFoundError) as error:
                errors.append(f"{filename}: {error}")
        self.assertEqual([], errors)

    def test_ignorable_namespace_prefixes_are_declared(self) -> None:
        findings: list[str] = []
        ignorable_pattern = re.compile(rb'\bmc:Ignorable="([^"]*)"')
        for filename in WORD_FORMS:
            with ZipFile(REPOSITORY_ROOT / filename) as package:
                document_xml = package.read("word/document.xml")
            match = ignorable_pattern.search(document_xml)
            if match is None:
                continue
            for prefix in match.group(1).decode("ascii").split():
                if f"xmlns:{prefix}=".encode("ascii") not in document_xml:
                    findings.append(f"{filename}: undeclared mc:Ignorable prefix {prefix}")
        self.assertEqual([], findings)

    def test_forms_have_current_title_date_and_single_reconciliation_entry(self) -> None:
        errors: list[str] = []
        for filename, (title, change_id) in WORD_FORMS.items():
            text = extract_docx_text(REPOSITORY_ROOT / filename)
            if title not in text:
                errors.append(f"{filename}: missing title {title}")
            if "2026-11-03" not in text:
                errors.append(f"{filename}: missing current update date")
            count = text.count(change_id)
            if count != 1:
                errors.append(f"{filename}: {change_id} occurs {count} times")
        self.assertEqual([], errors)

    def test_forms_have_no_unresolved_response_prompts(self) -> None:
        forbidden = (
            "Enter current value",
            "Enter milestone",
            "Enter link or path",
            "Enter owner",
            "Enter date and time",
            "Planned / In progress / Blocked / Ready for review / Complete",
        )
        findings: list[str] = []
        for filename in WORD_FORMS:
            text = extract_docx_text(REPOSITORY_ROOT / filename)
            for phrase in forbidden:
                if phrase in text:
                    findings.append(f"{filename}: {phrase}")
        self.assertEqual([], findings)

    def test_forms_have_no_unused_or_incomplete_record_rows(self) -> None:
        findings: list[str] = []
        generic_types = {"Risk / Issue / Debt", "Risk / Issue / Dependency"}
        for filename in WORD_FORMS:
            for index, row in enumerate(extract_docx_rows(REPOSITORY_ROOT / filename), start=1):
                if not row:
                    continue
                if not any(cell.strip() for cell in row):
                    findings.append(f"{filename}: unused row {index}")
                elif any(cell in generic_types for cell in row):
                    findings.append(f"{filename}: generic risk row {index}")
                elif any(not cell.strip() for cell in row):
                    findings.append(f"{filename}: incomplete retained row {index}")
        self.assertEqual([], findings)

    def test_forms_do_not_retain_superseded_current_state_claims(self) -> None:
        forbidden = (
            "schema_version 1.0.0",
            "Not wired in",
            "No authentication and no CORS configuration",
            "Future Node link",
        )
        findings: list[str] = []
        for filename in WORD_FORMS:
            text = extract_docx_text(REPOSITORY_ROOT / filename)
            for phrase in forbidden:
                if phrase in text:
                    findings.append(f"{filename}: {phrase}")
        self.assertEqual([], findings)

    def test_forms_include_status_evidence_limitations_and_handoff(self) -> None:
        findings: list[str] = []
        for filename in WORD_FORMS:
            text = extract_docx_text(REPOSITORY_ROOT / filename).lower()
            for term in ("status", "evidence", "limitation", "handoff"):
                if term not in text:
                    findings.append(f"{filename}: missing {term}")
        self.assertEqual([], findings)

    def test_project_record_covers_every_functional_requirement(self) -> None:
        text = extract_docx_text(REPOSITORY_ROOT / "Sentinel_Project_Wide_Documentation_Record.docx")
        missing = sorted(requirement for requirement in [f"FR0{index}" for index in range(1, 9)] if requirement not in text)
        self.assertEqual([], missing, f"Project-wide Word record is missing: {missing}")


class CrossFormatConsistencyTests(unittest.TestCase):
    """Catch status, evidence-page, form-index, and verification drift."""

    def test_requirement_statuses_match_evidence_markdown_and_project_word_table(self) -> None:
        evidence = load_evidence()
        markdown = (REPOSITORY_ROOT / "docs" / "prototype-status.md").read_text(encoding="utf-8")
        rows = extract_docx_rows(REPOSITORY_ROOT / "Sentinel_Project_Wide_Documentation_Record.docx")
        word_statuses = {row[0]: row[5] for row in rows if len(row) >= 6 and row[0] in REQUIRED_REQUIREMENTS}
        errors: list[str] = []
        for requirement, record in evidence["requirements"].items():
            status = record["status"]
            markdown_pattern = re.compile(rf"^\| {re.escape(requirement)} \|.*\| {re.escape(status)} \|", re.MULTILINE)
            if not markdown_pattern.search(markdown):
                errors.append(f"Markdown: {requirement} is not {status}")
            if word_statuses.get(requirement) != status:
                errors.append(f"Word: {requirement} is {word_statuses.get(requirement)!r}, expected {status!r}")
        self.assertEqual([], errors)

    def test_each_component_page_is_indexed_and_cited_by_its_role_form(self) -> None:
        index = (REPOSITORY_ROOT / "docs" / "documentation-index.md").read_text(encoding="utf-8")
        component_forms = {
            "docs/components/frontend.md": "Sentinel_Frontend_Development_Documentation_Form.docx",
            "docs/components/backend.md": "Sentinel_Backend_Development_Documentation_Form.docx",
            "docs/components/malware-detection.md": "Sentinel_Malware_Detection_Documentation_Form.docx",
            "docs/components/machine-learning.md": "Sentinel_Machine_Learning_Documentation_Form.docx",
            "docs/components/dynamic-analysis.md": "Sentinel_Dynamic_Analysis_Documentation_Form.docx",
            "docs/components/llm-threat-intelligence.md": "Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx",
        }
        errors: list[str] = []
        for component_path, form in component_forms.items():
            index_target = component_path.removeprefix("docs/")
            if index_target not in index:
                errors.append(f"Index missing {index_target}")
            if component_path not in extract_docx_text(REPOSITORY_ROOT / form):
                errors.append(f"{form} missing {component_path}")
        self.assertEqual([], errors)

    def test_documentation_index_lists_all_word_forms(self) -> None:
        index = (REPOSITORY_ROOT / "docs" / "documentation-index.md").read_text(encoding="utf-8")
        missing = sorted(filename for filename in WORD_FORMS if filename not in index)
        self.assertEqual([], missing, f"Documentation index is missing Word forms: {missing}")

    def test_observed_verification_results_match_status_markdown_and_project_word(self) -> None:
        evidence = load_evidence()
        markdown = (REPOSITORY_ROOT / "docs" / "prototype-status.md").read_text(encoding="utf-8")
        project_word = extract_docx_text(REPOSITORY_ROOT / "Sentinel_Project_Wide_Documentation_Record.docx")
        errors: list[str] = []
        for verification in evidence["verification"]:
            result = verification["result"]
            if result not in markdown:
                errors.append(f"Markdown missing exact {verification['id']} result")
            if result not in project_word:
                errors.append(f"Project Word record missing exact {verification['id']} result")
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
