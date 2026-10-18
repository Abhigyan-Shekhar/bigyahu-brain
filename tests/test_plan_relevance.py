"""Plan approval must depend on relevance AND fresh authorized source evidence."""

import copy
import subprocess
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from brain.app import actions, evidence, relevance
from brain.app.state import State
from brain.config import Config


@pytest.fixture
def planning(tmp_path, monkeypatch):
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture")
    project = state.create("repository", url="https://github.com/example/fixture")
    state.folder(project["id"]).mkdir()
    turn = state.create("turn", question="Why does conversion fail?")
    action = state.create(
        "action",
        project["id"],
        project=project["id"],
        turn=turn["id"],
        objective="Normalize malformed timestamps and preserve signature validation",
        status="queued",
        phase="planning",
    )
    monkeypatch.setattr(state, "config", lambda *_: state.base)
    monkeypatch.setattr(actions, "GraphStore", lambda cfg: SimpleNamespace(cfg=cfg))
    monkeypatch.setattr(actions, "ready", lambda *_: "base-sha")
    proof = {
        "kind": "memory",
        "ref": {"uid": "reviewed-fixture"},
        "text": "Preserve signature validation.",
        "title": "Reviewed team lesson",
        "digest": "content-digest",
        "revision": "base-sha",
        "graph": {"nodes": [], "edges": []},
    }
    changes = {"after_review": False, "mutation": None}

    def resolve(*_):
        if changes["after_review"] and changes["mutation"] == "revoked":
            raise PermissionError("Reviewed memory revoked")
        current = copy.deepcopy(proof)
        if changes["after_review"] and changes["mutation"] == "source":
            current["digest"] = "changed-digest"
        return current

    monkeypatch.setattr(evidence, "resolve", resolve)

    def codex(_state, _project, folder, *_args):
        item = evidence.register(folder / "evidence", proof)
        return {
            "claims": [
                {
                    "text": "Signature validation must be preserved",
                    "influence": "Keep signature verification while normalizing conversion errors",
                    "support": [{"evidence_id": item["id"], "quote": proof["text"]}],
                }
            ],
            "limitations": [],
            "plan": {
                "summary": "Guard timestamp conversion without changing signature checks",
                "files": ["timed.py", "test_timed.py"],
                "steps": ["Guard conversion", "Test malformed and tampered inputs"],
                "tests": [{"runner": "unittest", "path": "test_timed.py"}],
            },
        }

    monkeypatch.setattr(actions, "_codex", codex)
    return state, action, changes


def assessment(claim="supported", action="supported", reason="Direct preservation requirement"):
    return {
        "assessments": [{"claim": 0, "verdict": claim, "reason": reason}],
        "action": {"verdict": action, "reason": reason},
    }


@pytest.mark.parametrize(
    ("claim", "action_verdict", "reason"),
    [
        ("supported", "supported", "Evidence supports a narrow conversion fix"),
        ("unsupported", "supported", "Authentic quote is irrelevant to the diagnosis"),
        (
            "supported",
            "unsupported",
            "Removing signature verification does not follow from the evidence",
        ),
        ("supported", "uncertain", "Document and reviewed lesson conflict without resolution"),
    ],
)
def test_plan_requires_both_claim_and_action_support(
    planning, monkeypatch, claim, action_verdict, reason
):
    state, action, _ = planning

    def review(question, claims, folder, model, *, plan):
        assert question == action["objective"] and claims[0]["influence"]
        assert plan["files"] == ["timed.py", "test_timed.py"]
        assert folder.is_dir()
        return assessment(claim, action_verdict, reason)

    monkeypatch.setattr(actions, "assess", review)
    actions.prepare_plan(state, action["id"])
    result = state.get(action["id"])
    if claim == action_verdict == "supported":
        assert result["status"] == "awaiting_approval"
        actions.require_plan_review(result)
        actions.checked_action(state, result)
        changed = {**result, "plan": {**result["plan"], "summary": "Remove signature checks"}}
        with pytest.raises(ValueError, match="relevance review"):
            actions.require_plan_review(changed)
        assert result["notice"].startswith("Source provenance checked deterministically")
    else:
        assert result["status"] == "failed" and reason in result["error"]
        assert not result.get("plan") and not result.get("plan_digest")


@pytest.mark.parametrize("mutation", ["revoked", "source", "revision"])
def test_plan_rechecks_authorization_and_freshness_after_review(planning, monkeypatch, mutation):
    state, action, changes = planning
    changes["mutation"] = mutation

    def review(*_args, **_kwargs):
        changes["after_review"] = True
        if mutation == "revision":
            monkeypatch.setattr(actions, "ready", lambda *_: "new-sha")
        return assessment()

    monkeypatch.setattr(actions, "assess", review)
    actions.prepare_plan(state, action["id"])
    result = state.get(action["id"])
    assert result["status"] == "failed" and not result.get("plan_digest")


def test_revocation_after_presentation_blocks_approval(planning, monkeypatch):
    state, action, changes = planning
    monkeypatch.setattr(actions, "assess", lambda *_a, **_k: assessment())
    actions.prepare_plan(state, action["id"])
    pending = state.get(action["id"])
    changes.update(after_review=True, mutation="revoked")
    with pytest.raises(PermissionError, match="revoked"):
        actions.approve(state, pending["id"], pending["plan_digest"])
    assert state.get(action["id"])["status"] == "awaiting_approval"


def test_unavailable_plan_reviewer_fails_closed(planning, monkeypatch):
    state, action, _ = planning

    def unavailable(*_a, **_k):
        raise ValueError("Plan relevance reviewer unavailable")

    monkeypatch.setattr(actions, "assess", unavailable)
    actions.prepare_plan(state, action["id"])
    assert state.get(action["id"])["status"] == "failed"


def test_plan_reviewer_checks_whole_action_and_input_bound(tmp_path, monkeypatch):
    item = evidence.register(
        tmp_path,
        {
            "kind": "code",
            "ref": {},
            "text": "verify_signature()",
            "digest": "d",
            "revision": "s",
            "graph": {},
        },
    )
    claims = [
        {
            "text": "Signature is checked",
            "influence": "Keep the check",
            "support": [{"evidence_id": item["id"], "quote": "verify_signature()"}],
        }
    ]
    plan = {"summary": "Delete verification", "steps": ["Remove signature check"]}

    def extract(prompt, schema, model):
        assert "ENTIRE proposed action" in prompt and "NOT binding company policy" in prompt
        assert "Delete verification" in prompt and "Keep the check" in prompt
        assert "action" in schema["required"]
        return assessment(action="unsupported")

    monkeypatch.setattr(relevance, "structured_extract", extract)
    assert (
        relevance.assess("Fix conversion", claims, tmp_path, "fixture", plan=plan)["action"][
            "verdict"
        ]
        == "unsupported"
    )
    with pytest.raises(ValueError, match="bound"):
        relevance.assess("x" * 150001, claims, tmp_path, "fixture", plan=plan)
    monkeypatch.setattr(
        relevance, "structured_extract", lambda *_: {"assessments": assessment()["assessments"]}
    )
    with pytest.raises(ValueError, match="Invalid plan"):
        relevance.assess("Fix conversion", claims, tmp_path, "fixture", plan=plan)

    def timeout(*_):
        raise subprocess.TimeoutExpired("fixture-reviewer", 180)

    monkeypatch.setattr(relevance, "structured_extract", timeout)
    with pytest.raises(ValueError, match="timed out"):
        relevance.assess("Fix conversion", claims, tmp_path, "fixture", plan=plan)


def test_legacy_plan_requires_new_review_before_approval(planning):
    state, action, _ = planning
    # Existing historical records remain readable, but cannot authorize a new run.
    old = state.update(action["id"], status="awaiting_approval", plan_digest="old")
    with pytest.raises(ValueError):
        actions.approve(state, old["id"], "old")
