#!/usr/bin/env python3
"""Install backend npm dependencies if needed, then start Sentinel locally."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
URL = "http://localhost:3000/"
HEALTH_URL = "http://localhost:3000/api/health"


def command_for(name: str) -> list[str] | None:
    executable = shutil.which(name)
    if executable:
        return [executable]
    if os.name == "nt" and name == "npm":
        executable = shutil.which("npm.cmd")
        if executable:
            return [executable]
    return None


def main() -> int:
    node = command_for("node")
    npm = command_for("npm")
    if not node or not npm:
        print("Node.js and npm are required. Install Node.js 22 LTS, then run this file again.", file=sys.stderr)
        return 1

    if not (BACKEND / "node_modules").is_dir():
        print("Installing backend dependencies...")
        result = subprocess.run(npm + ["install"], cwd=BACKEND)
        if result.returncode:
            return result.returncode

    print("Starting Sentinel at http://localhost:3000/ (Ctrl+C to stop)...")
    process = subprocess.Popen(npm + ["run", "dev"], cwd=BACKEND)
    try:
        for _ in range(60):
            if process.poll() is not None:
                return int(process.returncode or 0)
            try:
                with urllib.request.urlopen(HEALTH_URL, timeout=1) as response:
                    if response.status == 200:
                        webbrowser.open(URL)
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.5)
        return int(process.wait())
    except KeyboardInterrupt:
        print("\nStopping Sentinel...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
