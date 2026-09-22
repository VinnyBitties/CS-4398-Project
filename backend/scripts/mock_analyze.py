#!/usr/bin/env python3
"""Stand-in for malware_detection/analyze.py, matching its documented I/O
contract (REPORT_CONTRACT.md, schema_version 1.0.0) closely enough for
backend development and tests before that branch is merged in.

Real behavior it mimics: one JSON object to stdout + exit 0 on success;
a JSON error object to stderr + exit 1 on a missing/invalid file. It does
NOT parse real PE files -- swap ANALYZER_SCRIPT_PATH to the real
malware_detection/analyze.py once that branch lands.
"""
import hashlib
import json
import sys


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage", "message": "usage: mock_analyze.py <file>"}), file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:
        print(json.dumps({"error": "read_failed", "message": str(exc)}), file=sys.stderr)
        sys.exit(1)

    sha256 = hashlib.sha256(data).hexdigest()
    report = {
        "schema_version": "1.0.0",
        "filename": path.split("/")[-1],
        "file_size": len(data),
        "sha256": sha256,
        "pe": {
            "format": "PE32+",
            "architecture": "x64",
            "machine": "0x8664",
            "compile_timestamp": None,
            "entry_point": "0x1000",
            "image_base": "0x140000000",
            "is_dll": False,
        },
        "sections": [],
        "imports": {"dlls": [], "apis": []},
        "strings": {"count": 0, "sample": [], "sample_limit": 200, "truncated": False},
        "summary": {
            "section_count": 0,
            "imported_dll_count": 0,
            "imported_api_count": 0,
            "string_count": 0,
        },
    }
    print(json.dumps(report))
    sys.exit(0)


if __name__ == "__main__":
    main()
