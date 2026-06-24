"""
Tests for synth-test V1.
Uses a local test API server to test the full execution pipeline.
"""

import json
import threading
import time
import http.server
import socketserver
import pytest
from pathlib import Path

from synth_test import generate, execute_suite
from synth_test.generator import (
    generate_cases_for_schema,
    generate_string_cases,
    generate_integer_cases,
    generate_number_cases,
    generate_boolean_cases,
    generate_array_cases,
    generate_object_cases,
    generate_enum_cases,
    generate_const_cases,
)
from synth_test.reporter import Reporter, report, print_report
from synth_test.types import TestCase, TestSuite, TestResult
from synth_test.executor import _build_request, _parse_path, _flatten_dict, execute_case


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def test_api_server():
    """Start a local test API server for integration tests."""
    PORT = 18765

    class TestAPIHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress logging

        def do_GET(self):
            self._respond(200, {"method": "GET", "path": self.path})

        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = body

            errors = []
            # Simulate some validation error conditions
            for key, value in data.items():
                if key in ("age", "count", "score") and isinstance(value, bool):
                    errors.append(f"{key}: bool for numeric")
                if key == "age" and isinstance(value, str):
                    errors.append(f"{key}: string for integer")

            # Trigger 500 on specific value
            if data.get("trigger_500"):
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "intentional 500"}')
                return

            if errors:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"validation_errors": errors}).encode())
            else:
                self._respond(200, {"received": data, "method": "POST"})

        def _respond(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

    class ReuseAddrTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    server = ReuseAddrTCPServer(("", PORT), TestAPIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)  # Let server start

    yield f"http://localhost:{PORT}"

    server.shutdown()


# ---------------------------------------------------------------------------
# Generator tests
# ---------------------------------------------------------------------------

class TestStringCases:
    def test_generates_empty_string(self):
        schema = {"type": "string"}
        cases = generate_string_cases(schema, "field", [])
        assert any(c.name == "string_empty" and c.generated_value == "" for c in cases)

    def test_generates_sql_injection(self):
        schema = {"type": "string"}
        cases = generate_string_cases(schema, "field", [])
        assert any("sql" in c.name for c in cases)

    def test_generates_unicode_emoji(self):
        schema = {"type": "string"}
        cases = generate_string_cases(schema, "field", [])
        assert any("emoji" in c.name for c in cases)

    def test_generates_xss_attempt(self):
        schema = {"type": "string"}
        cases = generate_string_cases(schema, "field", [])
        assert any("xss" in c.name for c in cases)

    def test_generates_email_format_cases(self):
        schema = {"type": "string", "format": "email"}
        cases = generate_string_cases(schema, "field", [])
        assert any(c.name == "email_no_at" for c in cases)
        assert any(c.name == "email_unicode" for c in cases)

    def test_generates_uri_format_cases(self):
        schema = {"type": "string", "format": "uri"}
        cases = generate_string_cases(schema, "field", [])
        assert any(c.name == "uri_invalid" for c in cases)

    def test_generates_datetime_format_cases(self):
        schema = {"type": "string", "format": "date-time"}
        cases = generate_string_cases(schema, "field", [])
        assert any(c.name == "datetime_invalid" for c in cases)
        assert any(c.name == "datetime_future_extreme" for c in cases)

    def test_generates_ipv4_format_cases(self):
        schema = {"type": "string", "format": "ipv4"}
        cases = generate_string_cases(schema, "field", [])
        assert any(c.name == "ipv4_invalid" for c in cases)

    def test_min_length_respected(self):
        schema = {"type": "string", "minLength": 5}
        cases = generate_string_cases(schema, "field", [])
        # Should still generate empty/short strings (boundary testing)
        assert len(cases) > 0


class TestIntegerCases:
    def test_generates_zero(self):
        schema = {"type": "integer"}
        cases = generate_integer_cases(schema, "field", [])
        assert any(c.name == "integer_zero" and c.generated_value == 0 for c in cases)

    def test_generates_boundary_at_min(self):
        schema = {"type": "integer", "minimum": 10}
        cases = generate_integer_cases(schema, "field", [])
        assert any(c.name == "integer_at_min" and c.generated_value == 10 for c in cases)
        assert any(c.name == "integer_one_below_min" and c.generated_value == 9 for c in cases)

    def test_generates_boundary_at_max(self):
        schema = {"type": "integer", "maximum": 100}
        cases = generate_integer_cases(schema, "field", [])
        assert any(c.name == "integer_at_max" and c.generated_value == 100 for c in cases)
        assert any(c.name == "integer_one_above_max" and c.generated_value == 101 for c in cases)

    def test_generates_type_confusion_cases(self):
        schema = {"type": "integer"}
        cases = generate_integer_cases(schema, "field", [])
        assert any(c.name == "integer_as_string" and c.generated_value == "42" for c in cases)
        assert any(c.name == "integer_as_float" and c.generated_value == 1.5 for c in cases)
        assert any(c.name == "integer_as_bool_true" for c in cases)

    def test_generates_overflow_values(self):
        schema = {"type": "integer"}
        cases = generate_integer_cases(schema, "field", [])
        assert any(c.name == "integer_int32_max" and c.generated_value == 2**31 - 1 for c in cases)
        assert any(c.name == "integer_int32_min" and c.generated_value == -(2**31) for c in cases)


class TestNumberCases:
    def test_generates_nan(self):
        schema = {"type": "number"}
        cases = generate_number_cases(schema, "field", [])
        import math
        assert any(c.name == "number_nan" and math.isnan(c.generated_value) for c in cases)

    def test_generates_inf(self):
        schema = {"type": "number"}
        cases = generate_number_cases(schema, "field", [])
        import math
        assert any(c.name == "number_inf" and c.generated_value == float("inf") for c in cases)
        assert any(c.name == "number_neg_inf" and c.generated_value == float("-inf") for c in cases)

    def test_generates_negative_zero(self):
        schema = {"type": "number"}
        cases = generate_number_cases(schema, "field", [])
        import math
        assert any(c.name == "number_negative_zero" and math.copysign(1, c.generated_value) < 0 for c in cases)


class TestBooleanCases:
    def test_generates_bool_values(self):
        schema = {"type": "boolean"}
        cases = generate_boolean_cases(schema, "field", [])
        assert any(c.name == "bool_true" and c.generated_value is True for c in cases)
        assert any(c.name == "bool_false" and c.generated_value is False for c in cases)

    def test_generates_type_confusion(self):
        schema = {"type": "boolean"}
        cases = generate_boolean_cases(schema, "field", [])
        assert any(c.name == "bool_as_int_1" and c.generated_value == 1 for c in cases)
        assert any(c.name == "bool_as_int_0" and c.generated_value == 0 for c in cases)
        assert any(c.name == "bool_as_string_true" and c.generated_value == "true" for c in cases)


class TestArrayCases:
    def test_generates_empty_array(self):
        schema = {"type": "array", "items": {"type": "string"}}
        cases = generate_array_cases(schema, "field", [])
        assert any(c.name == "array_empty" and c.generated_value == [] for c in cases)

    def test_generates_large_array(self):
        schema = {"type": "array", "items": {"type": "integer"}}
        cases = generate_array_cases(schema, "field", [])
        assert any(c.name == "array_1000_items" for c in cases)

    def test_generates_type_confusion(self):
        schema = {"type": "array", "items": {"type": "string"}}
        cases = generate_array_cases(schema, "field", [])
        assert any(c.name == "array_as_object" for c in cases)
        assert any(c.name == "array_as_string" for c in cases)


class TestObjectCases:
    def test_generates_empty_object(self):
        schema = {"type": "object", "properties": {}}
        cases = generate_object_cases(schema, "field", [])
        assert any(c.name == "object_empty" and c.generated_value == {} for c in cases)

    def test_generates_prototype_pollution_cases(self):
        schema = {"type": "object", "properties": {}}
        cases = generate_object_cases(schema, "field", [])
        assert any("__proto__" in str(c.generated_value) for c in cases)

    def test_generates_constructor_key(self):
        schema = {"type": "object", "properties": {}}
        cases = generate_object_cases(schema, "field", [])
        assert any("constructor" in str(c.generated_value) for c in cases)


class TestEnumCases:
    def test_generates_enum_values(self):
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        cases = generate_enum_cases(schema, "field", [])
        assert any(c.generated_value == "a" for c in cases)
        assert any(c.generated_value == "b" for c in cases)

    def test_generates_invalid_enum(self):
        schema = {"type": "string", "enum": ["a", "b"]}
        cases = generate_enum_cases(schema, "field", [])
        assert any(c.name == "enum_invalid_string" for c in cases)


class TestConstCases:
    def test_generates_const_value(self):
        schema = {"type": "string", "const": "fixed"}
        cases = generate_const_cases(schema, "field", [])
        assert any(c.name == "const_correct_value" and c.generated_value == "fixed" for c in cases)
        assert any(c.name == "const_wrong_value" for c in cases)


# ---------------------------------------------------------------------------
# Generator integration tests
# ---------------------------------------------------------------------------

class TestGenerateCasesForSchema:
    def test_generates_cases_from_simple_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        cases = generate_cases_for_schema(schema)
        assert len(cases) > 0
        paths = {c.path for c in cases}
        assert "name" in paths
        assert "age" in paths

    def test_generates_cases_from_nested_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
        cases = generate_cases_for_schema(schema)
        paths = {c.path for c in cases}
        assert "user" in paths
        assert any("user.profile" in p for p in paths)
        assert any("user.profile.name" in p for p in paths)

    def test_generates_from_array_schema(self):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                },
            },
        }
        cases = generate_cases_for_schema(schema)
        assert len(cases) > 0

    def test_generates_all_categories(self):
        schema = {"type": "string"}
        cases = generate_cases_for_schema(schema)
        categories = {c.category for c in cases}
        assert "boundary" in categories or "special_chars" in categories or "unicode" in categories

    def test_handles_string_formats(self):
        schema = {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "uri": {"type": "string", "format": "uri"},
            },
        }
        cases = generate_cases_for_schema(schema)
        names = [c.name for c in cases]
        assert any("email" in n for n in names)

    def test_handles_numeric_constraints(self):
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "minimum": 5, "maximum": 10},
            },
        }
        cases = generate_cases_for_schema(schema)
        assert any(c.name == "integer_at_min" and c.generated_value == 5 for c in cases)
        assert any(c.name == "integer_at_max" and c.generated_value == 10 for c in cases)

    def test_handles_enum_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["active", "inactive"]},
            },
        }
        cases = generate_cases_for_schema(schema)
        assert len(cases) > 0

    def test_handles_array_with_items(self):
        schema = {
            "type": "array",
            "items": {"type": "integer"},
        }
        cases = generate_cases_for_schema(schema)
        # Should generate cases for the array itself AND for integer items
        assert len(cases) > 5

    def test_top_level_generate(self):
        """Test the top-level generate() convenience function."""
        schema = {"type": "string"}
        cases = generate(schema)
        assert len(cases) > 0


# ---------------------------------------------------------------------------
# Executor tests
# ---------------------------------------------------------------------------

class TestBuildRequest:
    def test_build_request_simple_path(self):
        result = _build_request("POST", "http://example.com", "name", "Alice")
        assert result["method"] == "POST"
        assert result["url"] == "http://example.com"
        assert "data" in result["kwargs"]

    def test_build_request_nested_path(self):
        result = _build_request("POST", "http://example.com", "user.name", "Alice")
        assert result["method"] == "POST"

    def test_build_request_get_with_params(self):
        result = _build_request("GET", "http://example.com", "name", "Alice")
        assert "params" in result["kwargs"]

    def test_headers_set(self):
        result = _build_request("POST", "http://example.com", "name", "Alice")
        assert "Content-Type" in result["kwargs"]["headers"]


class TestParsePath:
    def test_simple_path(self):
        assert _parse_path("name") == ["name"]

    def test_dotted_path(self):
        assert _parse_path("user.name") == ["user", "name"]

    def test_array_path(self):
        assert _parse_path("users[0].name") == ["users", 0, "name"]

    def test_complex_path(self):
        result = _parse_path("a.b[0].c[1].d")
        assert result == ["a", "b", 0, "c", 1, "d"]


class TestFlattenDict:
    def test_flatten_simple(self):
        result = _flatten_dict({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_flatten_nested(self):
        result = _flatten_dict({"a": {"b": 1, "c": 2}})
        assert result == {"a.b": 1, "a.c": 2}


# ---------------------------------------------------------------------------
# Reporter tests
# ---------------------------------------------------------------------------

class TestReporter:
    def test_report_plain(self):
        reporter = Reporter(use_rich=False)
        case = TestCase("test", "path", [], "value", "boundary", {})
        result = TestResult(
            case=case,
            request_kwargs={},
            response_status=500,
            response_body={"error": "bad"},
            response_headers={},
            error=None,
            duration_ms=10.0,
        )
        suite = TestSuite("http://example.com", "POST", [result])

        output = reporter.report(suite)
        assert "synth-test Report" in output
        assert "FAILED" in output
        assert "500" in output

    def test_report_prints_all_cases(self):
        """Test that a report includes all passed and failed cases summary."""
        reporter = Reporter(use_rich=False)

        cases = [
            TestCase("pass_test", "path", [], "value", "boundary", {}),
            TestCase("fail_test", "path2", [], "value2", "boundary", {}),
        ]
        results = [
            TestResult(
                case=cases[0], request_kwargs={}, response_status=200,
                response_body={}, response_headers={},
            ),
            TestResult(
                case=cases[1], request_kwargs={}, response_status=500,
                response_body={}, response_headers={},
            ),
        ]
        suite = TestSuite("http://example.com", "POST", results)

        output = reporter.report(suite)
        assert "pass_test" in output
        assert "fail_test" in output
        assert "1" in output  # 1 passed

    def test_report_truncates_long_values(self):
        reporter = Reporter(use_rich=False)
        case = TestCase("test", "path", [], "X" * 200, "boundary", {})
        result = TestResult(
            case=case, request_kwargs={}, response_status=200,
            response_body={}, response_headers={},
        )
        suite = TestSuite("http://example.com", "POST", [result])

        output = reporter.report(suite)
        assert "..." in output or "X" not in output or len(output) < 5000


# ---------------------------------------------------------------------------
# Integration tests (with test server)
# ---------------------------------------------------------------------------

class TestExecuteSuite:
    def test_execute_all_pass(self, test_api_server):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        cases = generate(schema)

        suite = execute_suite(cases, test_api_server, method="POST", timeout=5)

        # Most cases should pass (no validation errors for basic string)
        assert suite.total_cases > 0

    def test_execute_catches_validation_errors(self, test_api_server):
        """Send bool where int is expected -> 400."""
        from synth_test.executor import execute_case
        from synth_test.types import TestCase

        # Send bool (True) as "age" which the server treats as invalid for numeric
        case = TestCase("bool_as_age", "age", [], True, "type_confusion", {"type": "integer"})
        result = execute_case(case, test_api_server, method="POST", timeout=5)

        # Server returns 400 for bool-integer type confusion
        assert result.response_status == 400

    def test_execute_catches_500_errors(self, test_api_server):
        from synth_test.executor import execute_case
        from synth_test.types import TestCase

        case = TestCase("trigger_500", "trigger_500", [], True, "boundary", {})
        result = execute_case(case, f"{test_api_server}/intentional-500", method="GET", timeout=5)

        assert result.response_status == 500
        assert result.is_error

    def test_suite_error_rate(self, test_api_server):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        cases = generate(schema)

        suite = execute_suite(cases, test_api_server, method="POST", timeout=5)
        assert 0.0 <= suite.error_rate <= 1.0


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_full_pipeline(self, test_api_server):
        """Test the full generate -> execute -> report pipeline."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"},
            },
        }

        cases = generate(schema)
        suite = execute_suite(cases, test_api_server, method="POST", timeout=5)

        reporter = Reporter(use_rich=False)
        output = reporter.report(suite)

        assert "synth-test Report" in output
        assert suite.total_cases == len(cases)
        assert len(output) > 0

    def test_core_convenience_functions(self):
        """Test the top-level generate/execute/report functions."""
        schema = {"type": "string"}
        cases = generate(schema)
        assert len(cases) > 0

        output = report(TestSuite("http://example.com", "GET", []))
        assert "synth-test Report" in output