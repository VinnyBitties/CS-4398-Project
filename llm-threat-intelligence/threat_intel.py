

import ipaddress
import re
from urllib.parse import urlparse
from typing import Dict


# Sample threat intelligence for prototype testing.
# These are demonstration indicators, not live threat feeds.
DEMO_INDICATORS = {
    "domain": {
        "malware.example": "Demo domain associated with malware activity."
    },
    "ip": {
        "192.0.2.10": "Demo IP associated with suspicious network traffic."
    },
    "url": {
        "https://malware.example/payload": "Demo malicious download URL."
    }
}


def analyze_indicator(indicator: str, indicator_type: str) -> Dict[str, str]:
    """Validate an indicator and return prototype threat intelligence."""

    indicator_type = indicator_type.lower().strip()
    indicator = indicator.strip()

    result = {
        "indicator": indicator,
        "type": indicator_type,
        "status": "unknown",
        "message": ""
    }

    if indicator_type not in ["hash", "ip", "domain", "url"]:
        result["status"] = "unsupported"
        result["message"] = "Unsupported indicator type."
        return result

    valid = False

    if indicator_type == "hash":
        valid = bool(
            re.fullmatch(r"[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", indicator)
        )

    elif indicator_type == "ip":
        try:
            ipaddress.ip_address(indicator)
            valid = True
        except ValueError:
            pass

    elif indicator_type == "domain":
        valid = bool(
            re.fullmatch(
                r"(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}",
                indicator
            )
        )

    elif indicator_type == "url":
        parsed = urlparse(indicator)
        valid = (
            parsed.scheme in ["http", "https"]
            and bool(parsed.hostname)
        )

    if not valid:
        result["status"] = "invalid"
        result["message"] = "Invalid indicator format."
        return result

    lookup_value = indicator.lower()
    known = DEMO_INDICATORS.get(indicator_type, {})

    if lookup_value in known:
        result["status"] = "suspicious"
        result["message"] = known[lookup_value]
    else:
        result["status"] = "not_found"
        result["message"] = (
            "Indicator is valid but was not found in the demo database. "
            "This does not mean it is safe."
        )

    return result


if __name__ == "__main__":
    test = analyze_indicator("malware.example", "domain")
    print("Sentinel Threat Intelligence Test")
    print(test)
