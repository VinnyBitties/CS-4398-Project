"""
Sentinel - LLM + Threat Intelligence
Threat Intelligence Module

This module receives indicators from malware analysis results
and prepares threat-intelligence information for Sentinel.
"""

from typing import Dict


def analyze_indicator(indicator: str, indicator_type: str) -> Dict[str, str]:
    """
    Analyze a threat indicator and return basic threat-intelligence data.

    Supported indicator types:
    - hash
    - ip
    - domain
    - url
    """

    supported_types = ["hash", "ip", "domain", "url"]

    if indicator_type.lower() not in supported_types:
        return {
            "indicator": indicator,
            "type": indicator_type,
            "status": "unsupported",
            "message": "Unsupported indicator type."
        }

    return {
        "indicator": indicator,
        "type": indicator_type.lower(),
        "status": "received",
        "message": "Indicator received for threat-intelligence analysis."
    }


if __name__ == "__main__":
    test_result = analyze_indicator(
        "example.com",
        "domain"
    )

    print("Sentinel Threat Intelligence Test")
    print(test_result)