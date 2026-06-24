# Type definitions for synth-test
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestCase:
    """A single test case generated from a JSON Schema."""
    name: str
    path: str  # JSON path to the field being tested
    schema_path: list[str]  # Path in schema to the property definition
    generated_value: Any
    category: str  # e.g., "boundary", "type_confusion", "null", "empty", "unicode"
    original_schema: dict  # The original JSON Schema fragment for this field


@dataclass
class TestResult:
    """Result of executing a test case against an endpoint."""
    case: TestCase
    request_kwargs: dict  # The actual HTTP request made
    response_status: int
    response_body: Any
    response_headers: dict
    error: str | None = None
    duration_ms: float = 0.0

    @property
    def is_error(self) -> bool:
        """Return True if the response indicates an error condition."""
        return self.error is not None or self.response_status >= 500


@dataclass
class TestSuite:
    """Collection of test results with summary statistics."""
    endpoint: str
    method: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def failed_cases(self) -> list[TestResult]:
        return [r for r in self.results if r.is_error]

    @property
    def passed_cases(self) -> list[TestResult]:
        return [r for r in self.results if not r.is_error]

    @property
    def error_rate(self) -> float:
        if not self.results:
            return 0.0
        return len(self.failed_cases) / len(self.results)