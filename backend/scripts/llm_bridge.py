#!/usr/bin/env python3
"""Bridge between the backend's `llm` stage and llm-threat-intelligence/.

Usage: python3 llm_bridge.py <path to llm-threat-intelligence>

Reads one JSON object on stdin:
    {"report": {...}, "indicators": [{"indicator": "...", "type": "hash|ip|domain|url"}]}
where `report` is the shape llm_analyzer.build_security_prompt() reads
(filename, sha256, static_analysis, ml_analysis, dynamic_analysis).

Writes one JSON object on stdout:
    {"threat_intel": [...], "prompt": "...", "explanation": null,
     "explanation_status": "not_generated"}

The LLM/Threat Intelligence component does not call an LLM yet, so there is
no explanation to return. When it does, this script is the one place on the
backend side that changes: call it after building the prompt and fill in
`explanation`.

On failure: exit 1 with {"error": ..., "message": ...} on stderr, the same
contract malware_detection/analyze.py uses.
"""

import json
import os
import sys


def fail(error, message):
    sys.stderr.write(json.dumps({"error": error, "message": message}))
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        fail("UsageError", "usage: llm_bridge.py <llm-threat-intelligence directory>")

    llm_dir = os.path.abspath(sys.argv[1])
    if not os.path.isfile(os.path.join(llm_dir, "llm_analyzer.py")):
        fail("LlmComponentNotFound", f"llm_analyzer.py not found in {llm_dir}")

    # llm_analyzer.py imports threat_intel as a sibling module.
    sys.path.insert(0, llm_dir)
    try:
        from llm_analyzer import build_security_prompt
        from threat_intel import analyze_indicator
    except Exception as exc:  # noqa: BLE001 -- report any import problem as JSON
        fail("LlmImportError", f"{type(exc).__name__}: {exc}")

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        fail("BadInput", f"stdin was not valid JSON: {exc}")

    report = payload.get("report") or {}
    indicators = payload.get("indicators") or []

    try:
        threat_intel = [analyze_indicator(i["indicator"], i["type"]) for i in indicators]
        prompt = build_security_prompt(report)
    except Exception as exc:  # noqa: BLE001
        fail(type(exc).__name__, str(exc))

    json.dump(
        {
            "threat_intel": threat_intel,
            "prompt": prompt.strip(),
            "explanation": None,
            "explanation_status": "not_generated",
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
