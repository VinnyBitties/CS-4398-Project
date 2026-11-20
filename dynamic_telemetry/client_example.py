"""
Example client script for detonating samples via the dynamic telemetry REST API.
"""
import requests
import json
import sys

SANDBOX_URL = "http://9.160.32.135:8000"

def check_health():
    resp = requests.get(f"{SANDBOX_URL}/health")
    resp.raise_for_status()
    print("[+] Sandbox Health:", resp.json())

def detonate(file_path: str, timeout: int = 15):
    print(f"[*] Submitting {file_path} (timeout={timeout}s)...")
    with open(file_path, "rb") as f:
        files = {"file": f}
        data = {"timeout": timeout}
        resp = requests.post(f"{SANDBOX_URL}/detonate", files=files, data=data)
    
    if resp.status_code != 200:
        print(f"[-] Detonation error ({resp.status_code}):", resp.text)
        return None
    
    report = resp.json()
    print("[+] Detonation complete!")
    print(f"    Job ID: {report.get('job_id')}")
    print(f"    Summary: {json.dumps(report.get('summary'), indent=2)}")
    return report

if __name__ == "__main__":
    check_health()
    if len(sys.argv) > 1:
        detonate(sys.argv[1])
    else:
        print("\nUsage: python client_example.py <path_to_sample>")
