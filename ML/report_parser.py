from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from config import (
    DEFAULT_MALICIOUS_THRESHOLD,
    FEATURE_COLUMNS,
    NETWORK_KEYWORDS,
    PERSISTENCE_KEYWORDS,
)


@dataclass(frozen=True)
class ReportAnalysis:
    malicious: bool
    risk_score: float
    risk_level: str
    features: dict[str, int]
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_report(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source

    path = Path(source)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    return json.loads(str(source))


def analyze_report(report: dict[str, Any], threshold: float = DEFAULT_MALICIOUS_THRESHOLD) -> ReportAnalysis:
    features = extract_features(report)
    evidence = gather_evidence(report, features)
    risk_score = calculate_risk_score(features)
    malicious = risk_score >= threshold
    risk_level = classify_risk(risk_score)
    return ReportAnalysis(
        malicious=malicious,
        risk_score=round(risk_score, 3),
        risk_level=risk_level,
        features=features,
        evidence=evidence,
    )


def extract_features(report: dict[str, Any]) -> dict[str, int]:
    signatures = _as_list(report.get("signatures"))
    network = _as_dict(report.get("network"))
    behavior = _as_dict(report.get("behavior"))
    summary = _as_dict(behavior.get("summary"))

    network_connections = _count_network_connections(network)
    dns_requests = len(_as_list(network.get("dns")))

    files_written = _first_int(
        summary,
        report,
        ["num_files_written", "files_written", "file_written", "files", "created_files"],
    )
    registry_keys_set = _first_int(
        summary,
        report,
        ["num_registry_keys_set", "registry_keys_set", "registry_written", "registry"],
    )
    processes_created = _first_int(
        summary,
        behavior,
        ["processes", "processes_created", "num_processes_created"],
    )

    max_signature_severity = max(
        (_safe_int(signature.get("severity"), 0) for signature in signatures),
        default=0,
    )

    has_persistence_signature = int(
        _has_keyword_match(report, signatures, PERSISTENCE_KEYWORDS)
    )
    has_network_signature = int(
        _has_keyword_match(report, signatures, NETWORK_KEYWORDS) or network_connections > 0 or dns_requests > 0
    )

    feature_map = {
        "num_processes_created": processes_created,
        "num_files_written": files_written,
        "num_registry_keys_set": registry_keys_set,
        "num_network_connections": network_connections,
        "num_dns_requests": dns_requests,
        "num_signatures_matched": len(signatures),
        "max_signature_severity": max_signature_severity,
        "has_persistence_signature": has_persistence_signature,
        "has_network_signature": has_network_signature,
    }

    return {name: int(feature_map.get(name, 0)) for name in FEATURE_COLUMNS}


def calculate_risk_score(features: dict[str, int]) -> float:
    raw_score = 0.0
    raw_score += min(features["num_network_connections"], 25) * 0.05
    raw_score += min(features["num_dns_requests"], 25) * 0.04
    raw_score += min(features["num_signatures_matched"], 12) * 0.08
    raw_score += min(features["max_signature_severity"], 5) * 0.12
    raw_score += features["has_persistence_signature"] * 0.18
    raw_score += features["has_network_signature"] * 0.18
    raw_score += min(features["num_files_written"], 20) * 0.02
    raw_score += min(features["num_registry_keys_set"], 20) * 0.02

    probability = 1.0 / (1.0 + math.exp(-(raw_score - 1.25)))
    return round(probability, 3)


def classify_risk(risk_score: float) -> str:
    if risk_score >= 0.8:
        return "critical"
    if risk_score >= 0.6:
        return "high"
    if risk_score >= 0.4:
        return "medium"
    return "low"


def gather_evidence(report: dict[str, Any], features: dict[str, int]) -> list[str]:
    evidence: list[str] = []

    if features["num_network_connections"]:
        evidence.append(f"{features['num_network_connections']} network connection(s) observed")
    if features["num_dns_requests"]:
        evidence.append(f"{features['num_dns_requests']} DNS request(s) observed")
    if features["num_signatures_matched"]:
        evidence.append(f"{features['num_signatures_matched']} signature(s) matched")
    if features["has_persistence_signature"]:
        evidence.append("persistence-related behavior detected")
    if features["has_network_signature"]:
        evidence.append("network-related behavior detected")

    signatures = _as_list(report.get("signatures"))
    for signature in signatures[:5]:
        name = str(signature.get("name") or signature.get("description") or "signature")
        severity = signature.get("severity", 0)
        evidence.append(f"signature: {name} (severity {severity})")

    return evidence


def _has_keyword_match(report: dict[str, Any], signatures: list[dict[str, Any]], keywords: list[str]) -> bool:
    haystack_parts: list[str] = []

    for signature in signatures:
        for key in ("name", "description", "short_description", "category"):
            value = signature.get(key)
            if value:
                haystack_parts.append(str(value))

        marks = signature.get("marks")
        if isinstance(marks, list):
            haystack_parts.extend(str(mark) for mark in marks)

    network = _as_dict(report.get("network"))
    for key in ("domains", "http", "hosts"):
        value = network.get(key)
        if isinstance(value, list):
            haystack_parts.extend(str(item) for item in value)

    haystack = " ".join(haystack_parts).lower()
    return any(keyword in haystack for keyword in keywords)


def _count_network_connections(network: dict[str, Any]) -> int:
    if not network:
        return 0

    hosts = _as_list(network.get("hosts"))
    if hosts:
        return len(hosts)

    total = 0
    for key in ("tcp", "udp", "icmp", "http", "dns"):
        total += len(_as_list(network.get(key)))
    return total


def _first_int(primary: dict[str, Any], secondary: dict[str, Any], keys: list[str]) -> int:
    for source in (primary, secondary):
        for key in keys:
            if key not in source:
                continue

            value = source.get(key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, dict):
                return len(value)
            if value is not None:
                return _safe_int(value, 0)

    return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default