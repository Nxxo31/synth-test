"""
synth_test.core - Main API for synth-test V1.

Usage:
    from synth_test import generate, execute, report

    cases = generate(schema)
    suite = execute(cases, "https://api.example.com/endpoint", method="POST")
    print_report(suite)
"""

from .generator import generate_cases_for_schema
from .executor import execute_case, execute_suite
from .reporter import report, print_report, Reporter
from .types import TestCase, TestResult, TestSuite


def generate(schema: dict, path: str = "") -> list[TestCase]:
    """
    Generate all edge case test cases from a JSON Schema.

    Args:
        schema: A JSON Schema (dict or JSON string).
        path: Optional root path for the top-level object.

    Returns:
        List of TestCase objects.
    """
    if isinstance(schema, str):
        import json
        schema = json.loads(schema)
    return generate_cases_for_schema(schema, path=path)


def execute(
    cases: list[TestCase],
    url: str,
    method: str = "POST",
    headers: dict | None = None,
    timeout: int = 10,
) -> TestSuite:
    """
    Execute test cases against an endpoint.

    Args:
        cases: List of TestCase objects to execute.
        url: Target endpoint URL.
        method: HTTP method.
        headers: Optional headers dict.
        timeout: Request timeout in seconds.

    Returns:
        A TestSuite with all results.
    """
    return execute_suite(
        cases=cases,
        base_url=url,
        method=method,
        headers=headers,
        timeout=timeout,
    )


__all__ = [
    "generate",
    "execute",
    "report",
    "print_report",
    "Reporter",
    "TestCase",
    "TestResult",
    "TestSuite",
    "generate_cases_for_schema",
    "execute_case",
    "execute_suite",
]