from __future__ import annotations

import sys
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from config import DEFAULT_MALICIOUS_THRESHOLD
from report_parser import analyze_report, load_report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze Cuckoo Sandbox JSON reports for malicious traffic signals."
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a Cuckoo report JSON file. If omitted, reads JSON from stdin.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start a local HTTP server that accepts POSTed JSON reports.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host when using --serve.")
    parser.add_argument("--port", type=int, default=8000, help="Server port when using --serve.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_MALICIOUS_THRESHOLD,
        help="Risk threshold used to label a report as malicious.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.serve:
        run_server(args.host, args.port)
        return

    report = load_input_report(args.file)
    result = analyze_report(report, threshold=args.threshold)
    print(json.dumps(result.to_dict(), indent=2))


def load_input_report(file_path: str | None) -> dict[str, Any]:
    if file_path:
        return load_report(Path(file_path))

    raw_input = sys.stdin.read().strip()
    if not raw_input:
        raise ValueError("No JSON input received.")
    return load_report(raw_input)


class ReportRequestHandler(BaseHTTPRequestHandler):
    server_version = "CuckooReportAnalyzer/1.0"

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/analyze", "/analyze-report", "/"}:
            self.send_error(404, "Endpoint not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8"))
            result = analyze_report(payload, threshold=DEFAULT_MALICIOUS_THRESHOLD).to_dict()
            response = json.dumps(result).encode("utf-8")
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            response = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health"}:
            response = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

        self.send_error(404, "Endpoint not found")


def run_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ReportRequestHandler)
    print(f"Listening on http://{host}:{port}")
    print("POST Cuckoo JSON reports to /analyze or /analyze-report")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()