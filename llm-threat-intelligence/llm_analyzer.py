import json
from groq import Groq
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


def generate_llm_explanation(report):
    """Generate an AI explanation of Sentinel scan results using Groq."""
    client = Groq()
    prompt = build_security_prompt(report)

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cybersecurity analysis assistant. "
                    "Explain only what the supplied scan evidence supports. "
                    "Do not invent malware detections or suspicious behaviors. "
                    "If evidence is insufficient, clearly say so."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_tokens=500,
    )

    return response.choices[0].message.content
    
    

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
