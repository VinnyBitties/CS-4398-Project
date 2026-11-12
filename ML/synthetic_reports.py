"""Generate synthetic normalized Sysmon reports and a labeled CSV manifest.

Adapted from ML-Diego's synthetic-reports.py. These fixtures exercise the
pipeline; their labels and distributions are invented, not malware evidence.
Run from the repository root: python ML/synthetic_reports.py --count 300
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from config import LABEL_BENIGN, LABEL_MALICIOUS, MANIFEST_PATH, SYNTHETIC_REPORTS_DIR


GENERATOR_VERSION = "sysmon-synthetic-v1"
# Both classes include quiet and active cases. Legitimate installers can also
# register persistence, so neither volume nor persistence determines the label.
PROFILES = {
    False: ("quiet", "active", "autorun", "task_query", "task_create"),
    True: ("quiet", "active", "autorun", "task_create", "task_change"),
}
COUNT_FIELDS = {
    "processes_created": "processes",
    "network_connections": "network",
    "dns_queries": "dns",
    "files_created": "file_drops",
    "registry_modifications": "registry",
    "remote_threads_injected": "remote_threads",
}


def make_report(malicious: bool, rng: random.Random | None = None) -> dict:
    """Create one report in the shape delivered by sandboxToMl.js.

    Commands and paths below are inert JSON strings; nothing is executed.
    A caller-owned RNG makes all content, including IDs, reproducible.
    """
    rng = rng if rng is not None else random.Random()
    profile = rng.choice(PROFILES[malicious])
    quiet = profile == "quiet"
    image = r"C:\Tools\sample.exe"
    processes = [{"image": image, "command_line": image,
                  "parent": r"C:\Windows\explorer.exe", "pid": "1000"}]
    for i in range(rng.randint(0, 1 if quiet else 4)):
        processes.append({"image": image, "command_line": image + " --worker",
                          "parent": image, "pid": str(1001 + i)})

    network = [{"image": image, "protocol": "tcp",
                "dest_ip": f"192.0.2.{rng.randint(1, 254)}",
                "dest_port": str(rng.choice((80, 443, 8080)))}
               for _ in range(rng.randint(0, 1) if quiet else rng.randint(1, 8))]
    dns = [{"query_name": f"service-{rng.randrange(1000)}.example.test",
            "results": "192.0.2.10"}
           for _ in range(rng.randint(0, 1) if quiet else rng.randint(1, 6))]
    file_drops = [{"target_filename": rf"C:\Users\sandbox\AppData\Local\Temp\file_{i}.dat",
                   "image": image}
                  for i in range(rng.randint(0, 1) if quiet else rng.randint(1, 12))]
    registry = [{"target_object": rf"HKCU\Software\ExampleApp\Setting{i}",
                 "event_type": "SetValue", "details": "1"}
                for i in range(rng.randint(0, 1) if quiet else rng.randint(1, 8))]

    if profile == "autorun":
        key = rng.choice(("Run", "RunOnce"))
        registry.append({
            "target_object": rf"HKCU\Software\Microsoft\Windows\CurrentVersion\{key}\ExampleApp",
            "event_type": "SetValue", "details": image,
        })
    if profile.startswith("task_"):
        operation = {"task_query": "/Query /FO LIST",
                     "task_create": '/Create /SC ONLOGON /TN ExampleApp /TR "C:\\Tools\\sample.exe"',
                     "task_change": "/Change /TN ExampleApp /ENABLE"}[profile]
        processes.append({"image": r"C:\Windows\System32\schtasks.exe",
                          "command_line": "schtasks.exe " + operation,
                          "parent": image, "pid": str(1000 + len(processes))})

    report = {
        "job_id": f"{rng.getrandbits(128):032x}",
        "original_filename": "sample.exe",
        "timeout_seconds": 15,
        "processes": processes, "network": network, "dns": dns,
        "file_drops": file_drops, "registry": registry,
        # The current backend adapter supplies this as an uncaptured zero.
        "remote_threads": [],
        "signatures": [],
        "metadata": {"synthetic": True, "generator_version": GENERATOR_VERSION},
    }
    report["summary"] = {count: len(report[events]) for count, events in COUNT_FIELDS.items()}
    return report


def generate_dataset(count: int, out_dir: Path, malicious_ratio: float = 0.5,
                     seed: int | None = 42) -> list[tuple[Path, int]]:
    if type(count) is not int or count <= 0:
        raise ValueError("count must be a positive integer")
    if not 0 <= malicious_ratio <= 1:
        raise ValueError("malicious_ratio must be between 0 and 1")
    rng = random.Random(seed)
    n_malicious = round(count * malicious_ratio)
    labels = [LABEL_MALICIOUS] * n_malicious + [LABEL_BENIGN] * (count - n_malicious)
    rng.shuffle(labels)
    paths = [out_dir / f"report_{i:05d}.json" for i in range(count)]
    if any(path.exists() for path in paths):
        raise ValueError("Output reports already exist; choose a new --out-dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for path, label in zip(paths, labels):
        report = make_report(label == LABEL_MALICIOUS, rng)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        # Absolute paths work with the current build_dataset.py from any cwd.
        manifest.append((path.resolve(), label))
    return manifest


def write_manifest(manifest: list[tuple[Path, int]], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("report_path", "label"))
        writer.writerows(manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--malicious-ratio", type=float, default=0.5)
    parser.add_argument("--out-dir", type=Path, default=SYNTHETIC_REPORTS_DIR)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        if args.manifest.exists():
            raise ValueError("Manifest already exists; choose a new --manifest")
        manifest = generate_dataset(args.count, args.out_dir, args.malicious_ratio, args.seed)
        write_manifest(manifest, args.manifest)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    n_malicious = sum(label == LABEL_MALICIOUS for _, label in manifest)
    print(f"Generated {len(manifest)} SYNTHETIC reports: {n_malicious} malicious, "
          f"{len(manifest) - n_malicious} benign")
    print(f"Manifest: {args.manifest}")
    print("For pipeline development only; synthetic results do not measure real-world accuracy.")


if __name__ == "__main__":
    main()
