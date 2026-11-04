import json
from threat_intel import analyze_indicator


def load_analysis_report(path):
    """Load structured malware analysis results from Sentinel."""
    with open(path, "r") as file:
        return json.load(file)


def build_security_prompt(report):
    """Convert Sentinel analysis results into a prompt for an LLM."""

    filename = report.get("filename", "Unknown")
    static_analysis = report.get("static_analysis", {})
    ml_analysis = report.get("ml_analysis", {})
    dynamic_analysis = report.get("dynamic_analysis", {})

    prompt = f"""
You are assisting with malware-analysis reporting for Sentinel.

Analyze the following security analysis results.

Filename:
{filename}

Static Analysis:
{static_analysis}

Machine Learning Analysis:
{ml_analysis}

Dynamic Analysis:
{dynamic_analysis}

Explain the following:

1. Important findings
2. Suspicious behaviors
3. Why the behaviors may represent security concerns
4. Overall risk explanation
5. Recommended next steps

Base the explanation only on the supplied analysis evidence.
"""

    return prompt


if __name__ == "__main__":
    report = load_analysis_report("sample_report.json")

    threat_intel_result = analyze_indicator(
        report.get("sha256", "unknown"),
        "hash"
    )

    prompt = build_security_prompt(report)

    print("=== SENTINEL THREAT INTELLIGENCE ===")
    print(threat_intel_result)

    print("\n=== SENTINEL LLM PROMPT ===")
    print(prompt)
