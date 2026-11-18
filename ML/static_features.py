"""Feature extraction for backend file_type/content_analysis reports.

This is deliberately separate from the sandbox behavioral feature schema.
It creates model inputs only; it does not infer a verdict or use analyzer
risk_level as a training label.
"""
from __future__ import annotations

import hashlib
from typing import Any

from config import STATIC_FEATURE_COLUMNS, STATIC_FINDING_BUCKETS


def extract_static_features(file_type: dict[str, Any], content_analysis: dict[str, Any]) -> dict[str, int]:
    """Validate and flatten one file_type/content_analysis report pair."""
    if not isinstance(file_type, dict) or not isinstance(content_analysis, dict):
        raise ValueError("Expected file_type and content_analysis objects")

    category = file_type.get("category")
    if not isinstance(category, str) or not category:
        raise ValueError("file_type.category must be a non-empty string")
    format_name = file_type.get("format")
    if not isinstance(format_name, str) or not format_name:
        raise ValueError("file_type.format must be a non-empty string")
    if content_analysis.get("category") != category or content_analysis.get("format") != format_name:
        raise ValueError("file_type and content_analysis category/format must match")

    findings = content_analysis.get("findings")
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise ValueError("content_analysis.findings must be an array of objects")

    values = {name: 0 for name in STATIC_FEATURE_COLUMNS}
    values[f"category_{_category(category)}"] = 1
    values[f"format_{_format(format_name)}"] = 1
    values[f"content_risk_{_risk(content_analysis.get('risk_level'))}"] = 1
    values["extension_mismatch"] = int(_boolean(file_type.get("extension_mismatch"), "extension_mismatch"))
    values["file_truncated"] = int(_boolean(file_type.get("truncated"), "truncated"))
    values["finding_count"] = len(findings)

    for finding in findings:
        finding_id = finding.get("id")
        severity = finding.get("severity")
        if not isinstance(finding_id, str) or not finding_id:
            raise ValueError("Each finding.id must be a non-empty string")
        if not isinstance(severity, str) or severity not in {"low", "medium", "high"}:
            raise ValueError("Each finding.severity must be low, medium, or high")
        values[f"finding_severity_{severity}"] += 1
        bucket = int.from_bytes(hashlib.sha256(finding_id.encode("utf-8")).digest()[:4], "big") % STATIC_FINDING_BUCKETS
        values[f"finding_id_bucket_{bucket:02d}"] += 1

    return values


def _category(value: str) -> str:
    normalized = value.lower()
    if normalized not in {"executable", "installer", "office", "pdf", "script", "source", "archive", "shortcut", "web", "unknown"}:
        raise ValueError(f"Unsupported file category: {value}")
    return normalized


def _format(value: str) -> str:
    normalized = value.lower()
    if normalized not in {
        "pe", "dos", "elf", "macho", "java_class", "jar", "apk", "msi",
        "doc", "xls", "ppt", "ole", "docx", "xlsx", "pptx", "rtf", "onenote",
        "csv", "pdf", "powershell", "batch", "vbscript", "jscript", "wsf", "hta",
        "python", "shell", "c", "cpp", "c_header", "csharp", "go", "rust", "java",
        "zip", "rar", "7z", "gzip", "tar", "cab", "iso", "vhd", "img", "lnk",
        "internet_shortcut", "html", "svg", "chm", "text", "unknown",
    }:
        raise ValueError(f"Unsupported file format: {value}")
    return normalized


def _risk(value: Any) -> str:
    if not isinstance(value, str) or value not in {"none", "low", "medium", "high"}:
        raise ValueError("content_analysis.risk_level must be none, low, medium, or high")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"file_type.{name} must be a boolean")
    return value
