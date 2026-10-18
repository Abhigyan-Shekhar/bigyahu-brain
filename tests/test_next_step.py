"""Next-task prose cannot change tools, scope or evidence authorization."""

import pytest

from brain.app import next_step


def proposal(kind="research", refs=()):
    return {
        "kind": kind,
        "objective": "Inspect queue restart handling",
        "rationale": "Current evidence leaves restart behavior uncertain",
        "based_on_evidence_ids": list(refs),
        "required_tools": ["read_code"],
        "completion_criteria": ["Cite the storage lifetime"],
        "expected_output": "checked_claims",
        "stop_if": ["Sources change"],
    }


@pytest.mark.parametrize(
    "tool", ["shell", "write_file", "publish", "send_email", "approve", "memory_propose"]
)
def test_untrusted_prompt_cannot_grant_write_or_external_tools(tool):
    item = proposal()
    item["required_tools"] = [tool]
    with pytest.raises(ValueError, match="allowlist"):
        next_step.validate(item, ["research"], [], [])


def test_capability_and_evidence_checks():
    with pytest.raises(ValueError, match="did not authorize"):
        next_step.validate(proposal("draft_email", ["x"]), ["research"], ["x"], [])
    with pytest.raises(ValueError, match="unknown parent"):
        next_step.validate(proposal(refs=["invented"]), ["research"], ["current"], [])
    with pytest.raises(ValueError, match="parent evidence"):
        next_step.validate(proposal(), ["research"], ["current"], [])
    with pytest.raises(ValueError, match="establish evidence"):
        next_step.validate(proposal("draft_document"), ["research", "draft_document"], [], [])


def test_near_duplicate_requires_new_checked_evidence():
    old = proposal(refs=["a"])
    with pytest.raises(ValueError, match="Repeated"):
        next_step.validate(proposal(refs=["a"]), ["research"], ["a"], [old])
    assert next_step.validate(proposal(refs=["a", "b"]), ["research"], ["a", "b"], [old])


def test_followup_must_state_a_relationship_to_the_original_goal():
    with pytest.raises(ValueError, match="original user goal"):
        next_step.validate(proposal(), ["research"], [], [], goal="Inspect invoice encryption")
