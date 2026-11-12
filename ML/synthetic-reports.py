"""
Generates synthetic Cuckoo/CAPE-shaped JSON reports so feature extraction,
dataset assembly, and model training can be developed and tested before a
real sandbox is producing reports.

The report *shape* (top-level keys: signatures, network, behavior.summary)
matches what report_parser.py already expects. Once a real sandbox exists,
only the sandbox's own report-to-this-shape adapter needs to be written --
report_parser.py, build_dataset.py, and the training scripts should not need
to change.

Usage:
    python synthetic_reports.py --count 300 --out-dir data/synthetic_reports
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from pathlib import Path

from config import LABEL_BENIGN, LABEL_MALICIOUS, MANIFEST_PATH, SYNTHETIC_REPORTS_DIR

PERSISTENCE_SIGNATURE_NAMES = [
    "creates_run_key",
    "installs_scheduled_task",
    "service_install_detected",
    "startup_folder_write",
]
NETWORK_SIGNATURE_NAMES = [
    "possible_c2_beacon",
    "suspicious_dns_request",
    "http_exfiltration_pattern",
    "command_and_control_traffic",
]
BENIGN_SIGNATURE_NAMES = [
    "reads_system_info",
    "loads_common_dll",
    "creates_temp_file",
    "checks_internet_connection",
]

API_POOL_BENIGN = [
    "CreateFileW", "ReadFile", "CloseHandle", "GetSystemTime",
    "LoadLibraryW", "RegOpenKeyExW", "RegQueryValueExW", "GetModuleHandleW",
]
API_POOL_MALICIOUS = [
    "CreateRemoteThread", "WriteProcessMemory", "VirtualAllocEx",
    "RegSetValueExW", "InternetOpenW", "InternetConnectW", "CreateServiceW",
    "NtUnmapViewOfSection", "CryptEncrypt", "FindFirstFileW", "DeleteFileW",
]


def _rand_domain(malicious: bool) -> str:
    if malicious:
        return f"{uuid.uuid4().hex[:8]}.{random.choice(['top', 'xyz', 'ru', 'info'])}"
    return random.choice(["microsoft.com", "google.com", "cloudflare.com", "github.com"])


def _make_signatures(malicious: bool) -> list[dict]:
    sigs = []
    pool = BENIGN_SIGNATURE_NAMES.copy()
    if malicious:
        # malicious samples usually, but not always, trip persistence/network
        # heuristics -- some don't, which is exactly the "anomaly, not known
        # signature" case the anomaly detector is meant to catch later.
        if random.random() < 0.7:
            pool += random.sample(PERSISTENCE_SIGNATURE_NAMES, k=random.randint(1, 2))
        if random.random() < 0.75:
            pool += random.sample(NETWORK_SIGNATURE_NAMES, k=random.randint(1, 2))

    n = random.randint(0, 3) if not malicious else random.randint(1, 5)
    for name in random.sample(pool, k=min(n, len(pool))) if pool else []:
        severity = random.randint(3, 5) if "c2" in name or "exfil" in name or "command" in name else random.randint(1, 4)
        if not malicious:
            severity = min(severity, 2)
        sigs.append({"name": name, "severity": severity, "description": name.replace("_", " ")})
    return sigs


def _make_network(malicious: bool) -> dict:
    n_dns = random.randint(0, 2) if not malicious else random.randint(0, 10)
    n_conn = random.randint(0, 1) if not malicious else random.randint(0, 8)
    return {
        "dns": [{"request": _rand_domain(malicious)} for _ in range(n_dns)],
        "domains": [_rand_domain(malicious) for _ in range(n_dns)],
        "tcp": [{"dst": f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}",
                 "dport": random.choice([80, 443, 8080, 4444, 53])} for _ in range(n_conn)],
        "http": [],
        "hosts": [],
    }


def _make_behavior(malicious: bool) -> dict:
    api_pool = API_POOL_MALICIOUS if malicious and random.random() < 0.8 else API_POOL_BENIGN
    n_calls = random.randint(5, 40) if malicious else random.randint(2, 15)
    calls = [{"api": random.choice(api_pool)} for _ in range(n_calls)]

    n_proc = random.randint(1, 5) if malicious else random.randint(1, 2)
    processes = [{"pid": 1000 + i, "calls": calls if i == 0 else []} for i in range(n_proc)]

    return {
        "processes": processes,
        "summary": {
            "num_files_written": random.randint(0, 3) if not malicious else random.randint(0, 25),
            "num_registry_keys_set": random.randint(0, 2) if not malicious else random.randint(0, 20),
            "processes": n_proc,
        },
    }


def make_report(malicious: bool) -> dict:
    return {
        "target": {"file": {"name": f"sample_{uuid.uuid4().hex[:10]}.exe"}},
        "signatures": _make_signatures(malicious),
        "network": _make_network(malicious),
        "behavior": _make_behavior(malicious),
    }


def generate_dataset(count: int, out_dir: Path, malicious_ratio: float, seed: int | None) -> list[tuple[Path, int]]:
    if seed is not None:
        random.seed(seed)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[tuple[Path, int]] = []

    for i in range(count):
        malicious = random.random() < malicious_ratio
        label = LABEL_MALICIOUS if malicious else LABEL_BENIGN
        report = make_report(malicious)

        report_path = out_dir / f"report_{i:05d}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        manifest.append((report_path, label))

    return manifest


def write_manifest(manifest: list[tuple[Path, int]], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as f:
        f.write("report_path,label\n")
        for path, label in manifest:
            f.write(f"{path},{label}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic sandbox reports for ML development.")
    parser.add_argument("--count", type=int, default=300, help="Number of reports to generate.")
    parser.add_argument("--malicious-ratio", type=float, default=0.5, help="Fraction labeled malicious.")
    parser.add_argument("--out-dir", type=Path, default=SYNTHETIC_REPORTS_DIR)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    manifest = generate_dataset(args.count, args.out_dir, args.malicious_ratio, args.seed)
    write_manifest(manifest, args.manifest)

    n_malicious = sum(1 for _, label in manifest if label == LABEL_MALICIOUS)
    print(f"Generated {len(manifest)} reports -> {args.out_dir}")
    print(f"  malicious: {n_malicious}  benign: {len(manifest) - n_malicious}")
    print(f"Manifest written -> {args.manifest}")


if __name__ == "__main__":
    main()