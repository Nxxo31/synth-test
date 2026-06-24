"""
Boundary case generators for JSON Schema types.
Each type has strategies for generating edge case values across 5 categories:
1. Boundary values (min/max extremes)
2. Type confusion (wrong types sent as value)
3. Null/empty values
4. Unicode and encoding issues
5. Unusually large values
"""

from __future__ import annotations

import math
import json
from typing import Any

from .types import TestCase, TestResult


# ---------------------------------------------------------------------------
# String edge values
# ---------------------------------------------------------------------------
STRING_EDGE_VALUES = [
    ("empty", ""),
    ("single_char", "X"),
    ("space", " "),
    ("tab", "\t"),
    ("newline", "\n"),
    ("crlf", "\r\n"),
    ("max_length_255", "X" * 255),
    ("max_length_1k", "X" * 1024),
    ("max_length_10k", "X" * 10240),
    ("unicode_emoji", "🎉🔥💀😂"),
    ("unicode_ascii_homoglyphs", "а" * 5),  # Cyrillic 'а' vs Latin 'a'
    ("unicode_zalgo", "ẗ̈́̋h̔̓̈e̛̅ͧ ̕t̨̛ͬe̴ͨͪx̴ͩ̚t̸̋ͬ"[:50]),
    ("unicode_bidi", "\u202e\u0041\u0042\u0043"),  # RLE override
    ("sql_injection_attempt", "'; DROP TABLE users; --"),
    ("xss_attempt", "<script>alert('xss')</script>"),
    ("path_traversal", "../../../etc/passwd"),
    ("null_byte", "\x00"),
    ("null_bytes_many", "\x00\x00\x00"),
    ("only_null_byte", "\x00"),
    ("all_whitespace_variations", " \t\n\r\f\v"),
    ("repetition_10k", "ABCDEFGHIJ" * 1000),
]


def generate_string_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for a string field."""
    cases = []
    min_len = schema.get("minLength", 0)
    max_len = schema.get("maxLength", float("inf"))
    pattern = schema.get("pattern", None)
    enum = schema.get("enum", None)

    # Use format if present
    fmt = schema.get("format", None)

    for name, value in STRING_EDGE_VALUES:
        if enum and value in enum:
            continue

        # Skip very large strings if there's no maxLength (avoid generating GB of data)
        if max_len == float("inf") and len(value) > 10240:
            continue

        # Skip if it exceeds an explicit maxLength constraint
        if len(value) > max_len:
            value = value[: int(max_len)] if max_len > 0 else ""

        # Skip values shorter than minLength (these should fail validation ideally)
        # Actually for boundary testing we WANT to test below minLength

        cases.append(
            TestCase(
                name=f"string_{name}",
                path=path,
                schema_path=schema_path,
                generated_value=value,
                category="boundary" if name in [
                    "empty", "single_char", "max_length_255", "max_length_1k"
                ] else "unicode" if "unicode" in name or "emoji" in name
                else "special_chars",
                original_schema=schema,
            )
        )

    # Format-specific cases
    if fmt == "email":
        cases.append(TestCase(
            name="email_no_at", path=path, schema_path=schema_path,
            generated_value="notanemail", category="type_confusion", original_schema=schema,
        ))
        cases.append(TestCase(
            name="email_double_at", path=path, schema_path=schema_path,
            generated_value="user@@example.com", category="type_confusion", original_schema=schema,
        ))
        cases.append(TestCase(
            name="email_unicode", path=path, schema_path=schema_path,
            generated_value="用户@例子.广告", category="unicode", original_schema=schema,
        ))
        cases.append(TestCase(
            name="email_quoted", path=path, schema_path=schema_path,
            generated_value='"test email"@example.com', category="boundary", original_schema=schema,
        ))

    if fmt == "uri":
        cases.append(TestCase(
            name="uri_invalid", path=path, schema_path=schema_path,
            generated_value="not a uri at all", category="type_confusion", original_schema=schema,
        ))
        cases.append(TestCase(
            name="uri_relative", path=path, schema_path=schema_path,
            generated_value="/relative/path", category="boundary", original_schema=schema,
        ))
        cases.append(TestCase(
            name="uri_null_scheme", path=path, schema_path=schema_path,
            generated_value="file:///etc/passwd", category="special_chars", original_schema=schema,
        ))

    if fmt == "date-time":
        cases.append(TestCase(
            name="datetime_invalid", path=path, schema_path=schema_path,
            generated_value="not-a-date", category="type_confusion", original_schema=schema,
        ))
        cases.append(TestCase(
            name="datetime_future_extreme", path=path, schema_path=schema_path,
            generated_value="9999-12-31T23:59:59Z", category="boundary", original_schema=schema,
        ))
        cases.append(TestCase(
            name="datetime_epoch", path=path, schema_path=schema_path,
            generated_value="1970-01-01T00:00:00Z", category="boundary", original_schema=schema,
        ))

    if fmt == "ipv4":
        cases.append(TestCase(
            name="ipv4_invalid", path=path, schema_path=schema_path,
            generated_value="999.999.999.999", category="type_confusion", original_schema=schema,
        ))
        cases.append(TestCase(
            name="ipv4_loopback", path=path, schema_path=schema_path,
            generated_value="127.0.0.1", category="boundary", original_schema=schema,
        ))
        cases.append(TestCase(
            name="ipv4_broadcast", path=path, schema_path=schema_path,
            generated_value="255.255.255.255", category="boundary", original_schema=schema,
        ))

    return cases


# ---------------------------------------------------------------------------
# Number / integer edge values
# ---------------------------------------------------------------------------

def _int_edge_values(min_val: int | None, max_val: int | None, fmt: str | None) -> list[tuple[str, Any]]:
    """Return boundary integer values based on min/max constraints."""
    vals = []

    # Establish safe bounds
    min_bound = min_val if min_val is not None else - (2 ** 53)  # Safe JS integer range
    max_bound = max_val if max_val is not None else (2 ** 53)

    vals.extend([
        ("zero", 0),
        ("negative_one", -1),
        ("one", 1),
    ])

    if min_val is not None:
        vals.extend([
            ("at_min", min_val),
            ("one_below_min", min_val - 1),
        ])
    else:
        vals.extend([
            ("min_safe_int", -(2 ** 31)),
            ("min_safe_int_plus_one", -(2 ** 31) + 1),
        ])

    if max_val is not None:
        vals.extend([
            ("at_max", max_val),
            ("one_above_max", max_val + 1),
        ])
    else:
        vals.extend([
            ("max_safe_int", 2 ** 31 - 1),
            ("max_safe_int_minus_one", 2 ** 31 - 2),
        ])

    # Classic overflow/underflow boundaries
    vals.extend([
        ("int8_min", -(2 ** 7)),
        ("int8_max", 2 ** 7 - 1),
        ("int8_max_plus_one", 2 ** 7),
        ("int16_min", -(2 ** 15)),
        ("int16_max", 2 ** 15 - 1),
        ("int32_min", -(2 ** 31)),
        ("int32_max", 2 ** 31 - 1),
        ("int64_min", -(2 ** 63)),
        ("int64_max", 2 ** 63 - 1),
        ("float32_min_subnormal", 1e-38),
        ("float32_max", 3.4e38),
        ("float64_min_subnormal", 1e-308),
        ("float64_max", 1.8e308),
        ("negative_float_huge", -1e308),
        ("positive_float_huge", 1e308),
    ])

    # Remove duplicates while preserving order
    seen, unique = set(), []
    for name, value in vals:
        if value not in seen:
            seen.add(value)
            unique.append((name, value))

    return unique


def generate_integer_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for an integer field."""
    cases = []
    min_val = schema.get("minimum", None)
    max_val = schema.get("maximum", None)
    exclusive_min = schema.get("exclusiveMinimum", None)
    exclusive_max = schema.get("exclusiveMaximum", None)

    if exclusive_min is not None:
        min_val = exclusive_min
    if exclusive_max is not None:
        max_val = exclusive_max

    for name, value in _int_edge_values(min_val, max_val, "integer"):
        cases.append(
            TestCase(
                name=f"integer_{name}",
                path=path,
                schema_path=schema_path,
                generated_value=value,
                category="boundary" if name in [
                    "zero", "negative_one", "one", "at_min", "at_max",
                    "one_below_min", "one_above_max"
                ] else "overflow",
                original_schema=schema,
            )
        )

    # Type confusion: float as integer
    cases.append(TestCase(
        name="integer_as_float", path=path, schema_path=schema_path,
        generated_value=1.5, category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="integer_as_string", path=path, schema_path=schema_path,
        generated_value="42", category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="integer_as_null_string", path=path, schema_path=schema_path,
        generated_value="null", category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="integer_as_bool_true", path=path, schema_path=schema_path,
        generated_value=True, category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="integer_max_float_precision_loss", path=path, schema_path=schema_path,
        generated_value=9007199254740993, category="boundary", original_schema=schema,
    ))

    return cases


def generate_number_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for a number (float) field."""
    cases = []
    min_val = schema.get("minimum", None)
    max_val = schema.get("maximum", None)

    for name, value in _int_edge_values(
        int(min_val) if min_val is not None else None,
        int(max_val) if max_val is not None else None,
        "number"
    ):
        cases.append(
            TestCase(
                name=f"number_{name}",
                path=path,
                schema_path=schema_path,
                generated_value=float(value),
                category="boundary" if name in [
                    "zero", "negative_one", "one", "at_min", "at_max"
                ] else "overflow",
                original_schema=schema,
            )
        )

    # Float-specific edge cases
    cases.append(TestCase(
        name="number_zero_dotzero", path=path, schema_path=schema_path,
        generated_value=0.0, category="boundary", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_negative_zero", path=path, schema_path=schema_path,
        generated_value=-0.0, category="boundary", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_nan", path=path, schema_path=schema_path,
        generated_value=float("nan"), category="special_chars", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_inf", path=path, schema_path=schema_path,
        generated_value=float("inf"), category="special_chars", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_neg_inf", path=path, schema_path=schema_path,
        generated_value=float("-inf"), category="special_chars", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_as_string", path=path, schema_path=schema_path,
        generated_value="3.14159", category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_as_int_string", path=path, schema_path=schema_path,
        generated_value="42", category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_as_scientific", path=path, schema_path=schema_path,
        generated_value="1e308", category="type_confusion", original_schema=schema,
    ))
    cases.append(TestCase(
        name="number_precision_loss", path=path, schema_path=schema_path,
        generated_value=1.234567890123456789, category="boundary", original_schema=schema,
    ))

    return cases


# ---------------------------------------------------------------------------
# Boolean edge cases
# ---------------------------------------------------------------------------

def generate_boolean_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for a boolean field."""
    cases = [
        TestCase(
            name="bool_true", path=path, schema_path=schema_path,
            generated_value=True, category="boundary", original_schema=schema,
        ),
        TestCase(
            name="bool_false", path=path, schema_path=schema_path,
            generated_value=False, category="boundary", original_schema=schema,
        ),
        TestCase(
            name="bool_as_int_1", path=path, schema_path=schema_path,
            generated_value=1, category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="bool_as_int_0", path=path, schema_path=schema_path,
            generated_value=0, category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="bool_as_string_true", path=path, schema_path=schema_path,
            generated_value="true", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="bool_as_string_false", path=path, schema_path=schema_path,
            generated_value="false", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="bool_as_string_yes", path=path, schema_path=schema_path,
            generated_value="yes", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="bool_as_string_no", path=path, schema_path=schema_path,
            generated_value="no", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="bool_as_null", path=path, schema_path=schema_path,
            generated_value=None, category="null", original_schema=schema,
        ),
        TestCase(
            name="bool_as_empty_string", path=path, schema_path=schema_path,
            generated_value="", category="type_confusion", original_schema=schema,
        ),
    ]
    return cases


# ---------------------------------------------------------------------------
# Null edge cases
# ---------------------------------------------------------------------------

def generate_null_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for a null-type field."""
    cases = [
        TestCase(
            name="null_null", path=path, schema_path=schema_path,
            generated_value=None, category="null", original_schema=schema,
        ),
        TestCase(
            name="null_as_none_string", path=path, schema_path=schema_path,
            generated_value="None", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="null_as_empty_string", path=path, schema_path=schema_path,
            generated_value="", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="null_as_json_null_string", path=path, schema_path=schema_path,
            generated_value="null", category="type_confusion", original_schema=schema,
        ),
    ]
    return cases


# ---------------------------------------------------------------------------
# Array edge cases
# ---------------------------------------------------------------------------

def generate_array_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for an array field."""
    cases = []
    min_items = schema.get("minItems", 0)
    max_items = schema.get("maxItems", float("inf"))
    unique_items = schema.get("uniqueItems", False)
    items_schema = schema.get("items", {})

    cases.extend([
        TestCase(
            name="array_empty", path=path, schema_path=schema_path,
            generated_value=[], category="empty", original_schema=schema,
        ),
        TestCase(
            name="array_single_item", path=path, schema_path=schema_path,
            generated_value=[1], category="boundary", original_schema=schema,
        ),
        TestCase(
            name="array_two_items", path=path, schema_path=schema_path,
            generated_value=[1, 2], category="boundary", original_schema=schema,
        ),
    ])

    if min_items == 0:
        cases.append(TestCase(
            name="array_zero_items_explicit", path=path, schema_path=schema_path,
            generated_value=[], category="empty", original_schema=schema,
        ))

    if max_items == float("inf") or max_items > 2:
        cases.extend([
            TestCase(
                name="array_100_items", path=path, schema_path=schema_path,
                generated_value=list(range(100)), category="boundary", original_schema=schema,
            ),
            TestCase(
                name="array_1000_items", path=path, schema_path=schema_path,
                generated_value=list(range(1000)), category="large", original_schema=schema,
            ),
        ])

    if min_items > 0:
        cases.append(TestCase(
            name="array_below_min_items", path=path, schema_path=schema_path,
            generated_value=[], category="boundary", original_schema=schema,
        ))

    cases.extend([
        TestCase(
            name="array_null_item", path=path, schema_path=schema_path,
            generated_value=[None], category="null", original_schema=schema,
        ),
        TestCase(
            name="array_duplicate_items", path=path, schema_path=schema_path,
            generated_value=[1, 1, 1], category="boundary", original_schema=schema,
        ),
        TestCase(
            name="array_mixed_types", path=path, schema_path=schema_path,
            generated_value=[1, "string", True, None], category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="array_as_object", path=path, schema_path=schema_path,
            generated_value={"0": 1, "1": 2}, category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="array_as_string", path=path, schema_path=schema_path,
            generated_value="[1, 2, 3]", category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="array_as_int", path=path, schema_path=schema_path,
            generated_value=42, category="type_confusion", original_schema=schema,
        ),
    ])

    return cases


# ---------------------------------------------------------------------------
# Object edge cases
# ---------------------------------------------------------------------------

def generate_object_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for an object field."""
    cases = []

    cases.extend([
        TestCase(
            name="object_empty", path=path, schema_path=schema_path,
            generated_value={}, category="empty", original_schema=schema,
        ),
        TestCase(
            name="object_single_property", path=path, schema_path=schema_path,
            generated_value={"key": "value"}, category="boundary", original_schema=schema,
        ),
        TestCase(
            name="object_extra_property", path=path, schema_path=schema_path,
            generated_value={"key": "value", "extra": "property"},
            category="boundary", original_schema=schema,
        ),
        TestCase(
            name="object_null_value", path=path, schema_path=schema_path,
            generated_value={"key": None}, category="null", original_schema=schema,
        ),
        TestCase(
            name="object_numeric_keys", path=path, schema_path=schema_path,
            generated_value={0: "zero", 1: "one"}, category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="object_boolean_keys", path=path, schema_path=schema_path,
            generated_value={True: "true_key", False: "false_key"}, category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="object_null_key", path=path, schema_path=schema_path,
            generated_value={"__proto__": "value"}, category="special_chars", original_schema=schema,
        ),
        TestCase(
            name="object_constructor_key", path=path, schema_path=schema_path,
            generated_value={"constructor": {}}, category="special_chars", original_schema=schema,
        ),
        TestCase(
            name="object_hasownproperty_key", path=path, schema_path=schema_path,
            generated_value={"hasOwnProperty": "evil"}, category="special_chars", original_schema=schema,
        ),
        TestCase(
            name="object_deeply_nested", path=path, schema_path=schema_path,
            generated_value={"a": {"b": {"c": {"d": {"e": "deep"}}}}},
            category="boundary", original_schema=schema,
        ),
        TestCase(
            name="object_as_array", path=path, schema_path=schema_path,
            generated_value=[1, 2, 3], category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="object_as_string", path=path, schema_path=schema_path,
            generated_value='{"key": "value"}', category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="object_as_primitives", path=path, schema_path=schema_path,
            generated_value="string_object", category="type_confusion", original_schema=schema,
        ),
    ])

    # Property names with unusual characters
    unusual_names = [
        ("spaces_in_key", "key with spaces"),
        ("unicode_key", "ключ"),
        ("emoji_key", "🔑"),
        ("dot_key", "key.with.dots"),
        ("special_chars_key", "key@#$"),
    ]
    for name, key in unusual_names:
        cases.append(TestCase(
            name=f"object_{name}", path=path, schema_path=schema_path,
            generated_value={key: "value"}, category="special_chars", original_schema=schema,
        ))

    return cases


# ---------------------------------------------------------------------------
# Enum cases
# ---------------------------------------------------------------------------

def generate_enum_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for an enum field."""
    enum_values = schema.get("enum", [])
    cases = []

    # Test each enum value
    for i, value in enumerate(enum_values[:5]):  # limit to 5 enum values
        cases.append(TestCase(
            name=f"enum_value_{i}", path=path, schema_path=schema_path,
            generated_value=value, category="boundary", original_schema=schema,
        ))

    # Test values NOT in enum
    if enum_values:
        sample = enum_values[0]
        if isinstance(sample, str):
            cases.append(TestCase(
                name="enum_invalid_string", path=path, schema_path=schema_path,
                generated_value="__invalid_enum__", category="type_confusion", original_schema=schema,
            ))
        elif isinstance(sample, int):
            cases.append(TestCase(
                name="enum_invalid_int", path=path, schema_path=schema_path,
                generated_value=999999, category="type_confusion", original_schema=schema,
            ))

    # Test enum value as wrong type
    if enum_values:
        sample = enum_values[0]
        if not isinstance(sample, bool):
            cases.append(TestCase(
                name="enum_as_bool", path=path, schema_path=schema_path,
                generated_value=True, category="type_confusion", original_schema=schema,
            ))
        if not isinstance(sample, str):
            cases.append(TestCase(
                name="enum_as_string", path=path, schema_path=schema_path,
                generated_value="enum_string", category="type_confusion", original_schema=schema,
            ))

    cases.append(TestCase(
        name="enum_null", path=path, schema_path=schema_path,
        generated_value=None, category="null", original_schema=schema,
    ))

    return cases


# ---------------------------------------------------------------------------
# const cases
# ---------------------------------------------------------------------------

def generate_const_cases(
    schema: dict, path: str, schema_path: list[str]
) -> list[TestCase]:
    """Generate edge case TestCases for a const field."""
    const_value = schema.get("const")
    cases = [
        TestCase(
            name="const_correct_value", path=path, schema_path=schema_path,
            generated_value=const_value, category="boundary", original_schema=schema,
        ),
        TestCase(
            name="const_wrong_value", path=path, schema_path=schema_path,
            generated_value="wrong" if const_value != "wrong" else "also_wrong",
            category="type_confusion", original_schema=schema,
        ),
        TestCase(
            name="const_null", path=path, schema_path=schema_path,
            generated_value=None, category="null", original_schema=schema,
        ),
    ]
    return cases


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_TYPE_TO_GENERATOR = {
    "string": generate_string_cases,
    "integer": generate_integer_cases,
    "number": generate_number_cases,
    "boolean": generate_boolean_cases,
    "null": generate_null_cases,
    "array": generate_array_cases,
    "object": generate_object_cases,
}


def generate_cases_for_schema(
    schema: dict,
    path: str = "",
    schema_path: list[str] | None = None,
    seen_paths: dict | None = None,
) -> list[TestCase]:
    """
    Recursively generate all edge case test cases for a JSON Schema.

    Args:
        schema: The JSON Schema fragment to generate cases for.
        path: JSON path to the current field (for building test case names).
        schema_path: Path in the schema to this fragment.
        seen_paths: Tracks visited schema nodes to avoid infinite loops.

    Returns:
        List of TestCase objects for every field and type in the schema.
    """
    if schema_path is None:
        schema_path = []
    if seen_paths is None:
        seen_paths = {}

    # Resolve $ref if present
    resolved = schema
    if "$ref" in schema:
        # In a full implementation we'd resolve the reference.
        # For V1 we handle local refs only.
        pass

    all_cases: list[TestCase] = []

    # Detect type(s)
    json_types = schema.get("type")
    if json_types is None:
        # Infer from other keywords
        if "properties" in schema or "additionalProperties" in schema:
            json_types = "object"
        elif "items" in schema:
            json_types = "array"
        elif "enum" in schema:
            json_types = "enum"
        elif "const" in schema:
            json_types = "const"
        else:
            # No type detected, skip
            return all_cases

    # Normalize to list
    if isinstance(json_types, str):
        json_types = [json_types]

    # Handle enum and const specially
    if "enum" in schema:
        all_cases.extend(generate_enum_cases(schema, path, schema_path))
        # Don't recurse into enum's const if there's a type too
        if "type" not in schema:
            return all_cases

    if "const" in schema:
        all_cases.extend(generate_const_cases(schema, path, schema_path))
        if "type" not in schema:
            return all_cases

    # Schema ID for cycle detection
    try:
        schema_id = id(schema)
        if schema_id in seen_paths:
            return all_cases
        seen_paths[schema_id] = True
    except Exception:
        pass

    for json_type in json_types:
        # Dispatch to type-specific generator
        if json_type in _TYPE_TO_GENERATOR:
            cases = _TYPE_TO_GENERATOR[json_type](schema, path, schema_path)
            all_cases.extend(cases)

        # Recurse into object properties
        if json_type == "object":
            props = schema.get("properties", {})
            addl = schema.get("additionalProperties", True)
            if addl is True:
                # Free-form object, add some extra property tests
                all_cases.append(TestCase(
                    name="object_additional_property_stress",
                    path=path, schema_path=schema_path,
                    generated_value={f"prop_{i}": f"value_{i}" for i in range(20)},
                    category="large", original_schema=schema,
                ))

            for prop_name, prop_schema in props.items():
                child_path = f"{path}.{prop_name}" if path else prop_name
                child_schema_path = schema_path + ["properties", prop_name]
                all_cases.extend(
                    generate_cases_for_schema(
                        prop_schema, child_path, child_schema_path, seen_paths
                    )
                )

        # Recurse into array items
        elif json_type == "array":
            items = schema.get("items", {})
            if items:
                child_path = f"{path}[0]" if path else "[0]"
                child_schema_path = schema_path + ["items"]
                all_cases.extend(
                    generate_cases_for_schema(
                        items, child_path, child_schema_path, seen_paths
                    )
                )

    return all_cases