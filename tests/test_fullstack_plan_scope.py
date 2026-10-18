"""Authentication plans can include required browser callers without losing scope checks."""

import json

import pytest

from brain.app import actions, evidence, relevance
from brain.app.action_mcp import read_file, write_file
from brain.app.action_policy import execution_capabilities


def candidate():
    return {
        "summary": "Require verified ownership and propagate the current browser session token",
        "steps": ["Verify backend identity", "Attach session token through the shared API client"],
        "files": ["backend/app/main.py", "frontend/src/services/api.js", "backend/test_auth.py"],
        "tests": [{"runner": "unittest", "path": "backend/test_auth.py"}],
    }


@pytest.mark.parametrize(
    "extension", ["js", "jsx", "ts", "tsx", "css", "html", "json", "yaml", "yml"]
)
def test_frontend_companion_files_can_be_planned_and_edited_within_scope(tmp_path, extension):
    plan = candidate()
    path = f"frontend/src/component.{extension}"
    plan["files"].append(path)
    validated = actions.validate_plan(plan, tmp_path)
    previous = read_file(tmp_path, path)
    write_file(tmp_path, validated["files"], path, "// fixture\n", previous["digest"])
    assert read_file(tmp_path, path)["text"] == "// fixture\n"
    with pytest.raises(ValueError, match="outside the approved"):
        write_file(tmp_path, validated["files"], "unapproved.js", "", previous["digest"])
    assert validated["commands"] == [["python", "-m", "unittest", "backend/test_auth.py", "-v"]]


def test_reviewer_receives_application_capabilities_without_weakening_caller_preservation(
    tmp_path, monkeypatch
):
    proof = evidence.register(
        tmp_path,
        {
            "kind": "code",
            "ref": {},
            "text": "api.get('/documents')",
            "digest": "fixture",
            "revision": "fixture",
            "graph": {},
        },
    )
    claims = [
        {
            "text": "The browser calls the document endpoint",
            "influence": "Preserve access",
            "support": [{"evidence_id": proof["id"], "quote": proof["text"]}],
        }
    ]

    def extract(prompt, *_args, **_kwargs):
        payload = json.loads(prompt.rsplit("\n", 1)[-1])
        assert payload["execution_capabilities"] == execution_capabilities()
        assert ".js" in payload["execution_capabilities"]["editable_extensions"]
        assert payload["execution_capabilities"]["frontend_test_execution"] is False
        assert "not a user-imposed requirement" in prompt
        assert "Require necessary companion caller/client changes" in prompt
        return {
            "assessments": [{"claim": 0, "verdict": "supported", "reason": "Client source"}],
            "action": {
                "verdict": "uncertain",
                "reason": "Missing companion authentication integration",
            },
        }

    monkeypatch.setattr(relevance, "structured_extract", extract)
    assert (
        relevance.assess(
            "Preserve legitimate access", claims, tmp_path, "fixture", plan=candidate()
        )["action"]["verdict"]
        == "uncertain"
    )
