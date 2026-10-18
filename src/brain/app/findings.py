"""Bounded review metadata for source-backed vulnerability and defect alerts."""

FINDING_SCHEMA = {
    "anyOf": [
        {"type": "null"},
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "severity", "category", "location", "recommendation"],
            "properties": {
                "title": {"type": "string"},
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low", "info"],
                },
                "category": {
                    "type": "string",
                    "enum": ["security", "correctness", "performance", "reliability"],
                },
                "location": {
                    "anyOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["path", "line"],
                            "properties": {"path": {"type": "string"}, "line": {"type": "integer"}},
                        },
                    ]
                },
                "recommendation": {"type": "string"},
            },
        },
    ]
}


def validate_finding(value, sources):
    if not isinstance(value, dict) or set(value) != {
        "title",
        "severity",
        "category",
        "location",
        "recommendation",
    }:
        raise ValueError("Invalid finding metadata")
    if (
        value["severity"] not in {"critical", "high", "medium", "low", "info"}
        or value["category"] not in {"security", "correctness", "performance", "reliability"}
        or any(
            not isinstance(value[k], str) or not 1 <= len(value[k].strip()) <= bound
            for k, bound in (("title", 200), ("recommendation", 2000))
        )
    ):
        raise ValueError("Invalid finding classification or description")
    location = value["location"]
    if location is not None and (
        not isinstance(location, dict)
        or set(location) != {"path", "line"}
        or not isinstance(location["path"], str)
        or type(location["line"]) is not int
        or not any(
            s["kind"] == "code"
            and s["ref"]["path"] == location["path"]
            and s["ref"]["start"] <= location["line"] <= s["ref"]["end"]
            for s in sources
        )
    ):
        raise ValueError("Finding location must fall within cited current code lines")
    return value
