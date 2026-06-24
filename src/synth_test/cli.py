#!/usr/bin/env python3
"""
synth-test CLI - Edge case test generator from JSON Schema

Usage:
    synth-test run --schema schema.json --url https://api.example.com/endpoint
    synth-test generate --schema schema.json
    synth-test --help
"""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

import requests


def cmd_generate(args) -> int:
    """Generate test cases from schema and print them."""
    from synth_test import generate

    schema = _load_schema(args.schema)
    cases = generate(schema, path=args.path or "")

    if args.json:
        output = {
            "total": len(cases),
            "cases": [
                {
                    "name": c.name,
                    "path": c.path,
                    "generated_value": c.generated_value,
                    "category": c.category,
                }
                for c in cases
            ],
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print(f"Generated {len(cases)} test cases from {args.schema}")
        for c in cases:
            print(f"  [{c.category:15s}] {c.name:40s} path={c.path}")

    return 0


def cmd_run(args) -> int:
    """Generate cases and execute against target endpoint."""
    from synth_test import generate, execute_suite
    from synth_test.reporter import Reporter

    schema = _load_schema(args.schema)
    cases = generate(schema, path=args.path or "")

    print(f"Generated {len(cases)} test cases. Executing...")

    # Build headers
    headers = None
    if args.header:
        headers = {}
        for h in args.header:
            if ":" in h:
                k, v = h.split(":", 1)
                headers[k.strip()] = v.strip()

    suite = execute_suite(
        cases=cases,
        base_url=args.url,
        method=args.method.upper(),
        headers=headers,
        timeout=args.timeout,
    )

    reporter = Reporter()
    reporter.print(suite)

    # Exit code: 0 if no errors, 1 if any errors
    return 1 if suite.failed_cases else 0


def cmd_serve(args) -> int:
    """Start a local test API server for demonstration."""
    import threading
    import http.server
    import socketserver
    from urllib.parse import parse_qs, urlparse

    PORT = args.port

    class TestAPIHandler(http.server.BaseHTTPRequestHandler):
        errors_5xx = set()

        def log_message(self, fmt, *args):
            # Suppress default logging
            pass

        def do_GET(self):
            self._handle_request("GET")

        def do_POST(self):
            self._handle_request("POST")

        def do_PUT(self):
            self._handle_request("PUT")

        def do_PATCH(self):
            self._handle_request("PATCH")

        def do_DELETE(self):
            self._handle_request("DELETE")

        def _handle_request(self, expected_method: str):
            """Process requests with intentionally buggy behavior for testing."""
            if self.command != expected_method:
                self.send_error(405)
                return

            # Parse path
            parsed = urlparse(self.path)
            path = parsed.path

            # Read body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            # Try to parse JSON
            data = None
            if content_length > 0:
                try:
                    data = json.loads(body)
                except Exception:
                    pass

            # Simulate various error conditions based on path
            if path.endswith("/intentional-500"):
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Internal server error triggered"}')
                return

            if path.endswith("/intentional-timeout"):
                import time
                time.sleep(5)  # Intentional slow response
                self.send_response(200)
                self.end_headers()
                return

            if path.endswith("/null-pointer"):
                try:
                    null_val = None
                    _ = null_val["key"]
                except Exception as e:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())
                    return

            # Validation errors for type confusion tests
            if path.endswith("/validate"):
                validation_errors = []
                if data:
                    for key, value in data.items():
                        # Detect type confusion
                        if isinstance(value, str) and key in ("age", "count", "id", "score"):
                            validation_errors.append(f"{key}: string provided for numeric field")
                        if isinstance(value, bool) and key in ("age", "count"):
                            validation_errors.append(f"{key}: boolean provided for numeric field")

                if validation_errors:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"validation_errors": validation_errors}).encode())
                    return

            # Default: 200 OK
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            response = {
                "status": "ok",
                "path": path,
                "method": self.command,
                "received": data,
            }
            self.wfile.write(json.dumps(response, indent=2).encode())

    class ReuseAddrTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReuseAddrTCPServer(("", PORT), TestAPIHandler) as httpd:
        print(f"Test API server running at http://localhost:{PORT}")
        print(f"  POST /validate     - validates incoming JSON with type checks")
        print(f"  GET  /intentional-500  - triggers a 500 error")
        print(f"  GET  /intentional-timeout - slow response (timeout)")
        print(f"  POST /null-pointer  - triggers a null pointer-like error")
        print(f"\nPress Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
    return 0


def cmd_demo(args) -> int:
    """Run a demonstration with the built-in test API server."""
    import subprocess
    import time

    # Start test server in background
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "synth_test.cli", "serve", "--port", str(args.port)],
        cwd=str(Path(__file__).parent),
    )
    time.sleep(1)

    try:
        from synth_test import generate, execute_suite
        from synth_test.reporter import Reporter

        # Load demo schema
        demo_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 2, "maxLength": 50},
                "age": {"type": "integer", "minimum": 0, "maximum": 120},
                "email": {"type": "string", "format": "email"},
                "score": {"type": "number"},
                "active": {"type": "boolean"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object", "properties": {"key": {"type": "string"}}},
            },
        }

        print("Generating test cases from demo schema...")
        cases = generate(demo_schema)
        print(f"  -> {len(cases)} test cases generated\n")

        # Run against validation endpoint
        url = f"http://localhost:{args.port}/validate"
        print(f"Executing against {url} ...")
        suite = execute_suite(
            cases=cases,
            base_url=url,
            method="POST",
            timeout=5,
        )

        reporter = Reporter()
        reporter.print(suite)

        # Also test 500 error endpoint
        print("\n\n")
        url_500 = f"http://localhost:{args.port}/intentional-500"
        from synth_test.types import TestCase, TestSuite
        from synth_test.executor import execute_case

        error_case = TestCase(
            name="intentional_500_trigger",
            path="trigger",
            schema_path=[],
            generated_value=True,
            category="error_trigger",
            original_schema={},
        )
        result = execute_case(error_case, url_500, method="GET", timeout=5)
        print(f"  [{result.response_status}] {error_case.name} -> {result.error or 'OK'}")

        return 1 if suite.failed_cases else 0

    finally:
        server_proc.terminate()
        server_proc.wait()


def _load_schema(path_or_data: str | Path) -> dict:
    """Load a JSON Schema from a file path or raw JSON string."""
    import json

    p = Path(path_or_data)
    if p.exists():
        return json.loads(p.read_text())
    else:
        # Try as raw JSON
        try:
            return json.loads(path_or_data)
        except json.JSONDecodeError:
            raise ValueError(f"Schema not found and not valid JSON: {path_or_data}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="synth-test",
        description="Edge case test generator from JSON Schema",
    )
    sub = parser.add_subparsers(required=True)

    # generate
    gen = sub.add_parser("generate", help="Generate test cases from schema")
    gen.add_argument("--schema", required=True, help="Path to JSON Schema file or '-' for stdin")
    gen.add_argument("--path", help="Root JSON path for top-level object")
    gen.add_argument("--json", action="store_true", help="Output as JSON")
    gen.set_defaults(fn=cmd_generate)

    # run
    run = sub.add_parser("run", help="Generate and execute test cases")
    run.add_argument("--schema", required=True)
    run.add_argument("--url", required=True, help="Target endpoint URL")
    run.add_argument("--method", default="POST", help="HTTP method (default: POST)")
    run.add_argument("--path", help="Root JSON path")
    run.add_argument("--header", action="append", help="Extra headers as 'Name: Value'")
    run.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    run.set_defaults(fn=cmd_run)

    # serve
    serve = sub.add_parser("serve", help="Start test API server")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(fn=cmd_serve)

    # demo
    demo = sub.add_parser("demo", help="Run demonstration with test API")
    demo.add_argument("--port", type=int, default=8765)
    demo.set_defaults(fn=cmd_demo)

    args = parser.parse_args(argv)

    try:
        return args.fn(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())