"""
Fixtures: JSON Schemas for testing synth-test generators.
"""

DEMO_USER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "minLength": 2,
            "maxLength": 50,
            "description": "User's full name",
        },
        "email": {
            "type": "string",
            "format": "email",
            "description": "User's email address",
        },
        "age": {
            "type": "integer",
            "minimum": 0,
            "maximum": 120,
            "description": "User's age in years",
        },
        "score": {
            "type": "number",
            "description": "User's score",
        },
        "active": {
            "type": "boolean",
            "description": "Whether the user is active",
        },
        "role": {
            "type": "string",
            "enum": ["admin", "user", "guest"],
            "description": "User's role",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "User's tags",
        },
        "metadata": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "description": "Additional metadata",
        },
    },
    "required": ["name", "email"],
}

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "value": {"type": "string"},
    },
}

NESTED_SCHEMA = {
    "type": "object",
    "properties": {
        "user": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                },
                "settings": {
                    "type": "object",
                    "properties": {
                        "theme": {"type": "string"},
                    },
                },
            },
        }
    },
}

ARRAY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
        },
    },
}

STRING_FORMATS_SCHEMA = {
    "type": "object",
    "properties": {
        "email_field": {"type": "string", "format": "email"},
        "uri_field": {"type": "string", "format": "uri"},
        "date_field": {"type": "string", "format": "date-time"},
        "ipv4_field": {"type": "string", "format": "ipv4"},
        "plain_string": {"type": "string"},
    },
}

NUMERIC_SCHEMA = {
    "type": "object",
    "properties": {
        "int_field": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
        },
        "float_field": {
            "type": "number",
        },
        "const_field": {
            "type": "string",
            "const": "fixed_value",
        },
    },
}