"""
HTTP execution engine for synth-test.
Sends test cases as HTTP requests and collects responses.
"""

from __future__ import annotations

import time
import json
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from requests.structures import CaseInsensitiveDict

from .types import TestCase, TestResult, TestSuite


# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 10


def _build_request(
    method: str,
    url: str,
    path: str,
    generated_value: Any,
    headers: dict | None = None,
    content_type: str = "application/json",
) -> dict:
    """
    Build the keyword arguments for a requests call.
    Uses the path as a hint for how to send the value:
      - For leaf fields (no dots, no brackets), sends as JSON body
      - For deeply nested paths, builds a nested JSON body

    Returns:
        A dict with 'method', 'url', 'kwargs' keys.
    """
    kwargs: dict[str, Any] = {
        "headers": CaseInsensitiveDict(headers or {}),
        "timeout": DEFAULT_TIMEOUT,
    }

    # Set content type if not already set
    if "Content-Type" not in kwargs["headers"] and "content-type" not in kwargs["headers"]:
        kwargs["headers"]["Content-Type"] = content_type

    # Determine how to package the value
    parsed_path = path
    is_simple_path = "." not in parsed_path and "[" not in parsed_path

    if is_simple_path:
        # Leaf field — build a flat body
        body = {path: generated_value}
    else:
        # Nested path — build nested structure
        body = _build_nested_body(path, generated_value)

    if method.upper() in ("POST", "PUT", "PATCH"):
        if content_type == "application/json":
            kwargs["data"] = json.dumps(body, default=str)
            kwargs["headers"]["Content-Type"] = "application/json"
        else:
            kwargs["data"] = body
    elif method.upper() == "GET":
        # For GET, add as query params (flatten the body)
        params = _flatten_dict(body)
        kwargs["params"] = params

    return {
        "method": method.upper(),
        "url": url,
        "kwargs": kwargs,
    }


def _build_nested_body(path: str, value: Any) -> dict:
    """Build a nested dict from a dotted/bracketed path."""
    result: dict = {}
    current = result

    # Parse path components
    parts = _parse_path(path)

    for i, part in enumerate(parts[:-1]):
        if isinstance(part, int):
            current[part] = []
            current = current[part]
        else:
            current[part] = {}
            current = current[part]

    # Set the final value
    if parts:
        last = parts[-1]
        current[last] = value

    return result


def _parse_path(path: str) -> list[str | int]:
    """Parse a JSON path like 'user.addresses[0].city' into components."""
    import re
    # Split on dots first
    parts = path.split(".")
    result: list[str | int] = []
    for part in parts:
        # Handle bracket notation
        tokens = re.split(r"(\[\d+\])", part)
        for token in tokens:
            m = re.match(r"\[(\d+)\]", token)
            if m:
                result.append(int(m.group(1)))
            elif token:
                result.append(token)
    return result


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Flatten a nested dict into a single-level dict with dot-notation keys."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def execute_case(
    case: TestCase,
    base_url: str,
    method: str = "POST",
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> TestResult:
    """
    Execute a single test case against the target endpoint.

    Args:
        case: The TestCase to execute.
        base_url: Base URL of the API.
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        headers: Additional headers to send.
        timeout: Request timeout in seconds.

    Returns:
        A TestResult with the response details.
    """
    import json

    request_spec = _build_request(
        method=method,
        url=base_url,
        path=case.path,
        generated_value=case.generated_value,
        headers=headers,
    )

    request_kwargs = request_spec.copy()

    start = time.monotonic()
    error: str | None = None
    response_status = 0
    response_body: Any = None
    response_headers: dict = {}

    try:
        # Unpack kwargs dict separately (method and url are top-level)
        method = request_spec.pop("method")
        url = request_spec.pop("url")
        extra_kwargs = request_spec.pop("kwargs", {})
        extra_kwargs.pop("timeout", None)  # timeout passed explicitly below
        resp = requests.request(method, url, timeout=timeout, **extra_kwargs)
        response_status = resp.status_code
        response_headers = dict(resp.headers)

        # Try to parse as JSON
        try:
            response_body = resp.json()
        except Exception:
            response_body = resp.text

    except requests.Timeout:
        error = f"Request timed out after {timeout}s"
        response_body = None
    except requests.ConnectionError as e:
        error = f"Connection error: {e}"
        response_body = None
    except requests.RequestException as e:
        error = f"Request error: {e}"
        response_body = None
    except Exception as e:
        error = f"Unexpected error: {e}"
        response_body = None

    duration_ms = (time.monotonic() - start) * 1000

    return TestResult(
        case=case,
        request_kwargs=request_kwargs,
        response_status=response_status,
        response_body=response_body,
        response_headers=response_headers,
        error=error,
        duration_ms=duration_ms,
    )


def execute_suite(
    cases: list[TestCase],
    base_url: str,
    method: str = "POST",
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    progress_callback=None,
) -> TestSuite:
    """
    Execute a full suite of test cases against the target endpoint.

    Args:
        cases: List of TestCases to execute.
        base_url: Base URL of the API.
        method: HTTP method.
        headers: Additional headers.
        timeout: Request timeout.
        progress_callback: Optional callable(cases_run, cases_total) for progress.

    Returns:
        A TestSuite containing all results.
    """
    results: list[TestResult] = []

    for i, case in enumerate(cases):
        result = execute_case(
            case=case,
            base_url=base_url,
            method=method,
            headers=headers,
            timeout=timeout,
        )
        results.append(result)

        if progress_callback:
            progress_callback(i + 1, len(cases))

    return TestSuite(
        endpoint=base_url,
        method=method,
        results=results,
    )