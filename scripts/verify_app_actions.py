"""Independently verify a completed synthetic application coding acceptance run.

Never approves actions. Replays the downloadable patch in a fresh disposable clone
and executes a held-out oracle through the same fail-closed OS sandbox.
"""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from prepare_app_action_fixture import POLICY

from brain.app.actions import action_folder, approve, checked_action, clone_at
from brain.app.state import State
from brain.app.test_sandbox import bounded_run, sandbox_command, test_environment
from brain.config import load_config
from brain.ingest.git_parser import git

ORACLE = """
from retry import delay_ms
cases=[(0,10,10),(1,10,20),(2,10,40),(6,10,640),(7,10,800),(20,10,800),
       (0,1000,800),(0,0,0),(4,0,0),(3,7,56),(1,1,2),(0,800,800)]
for attempt,base,expected in cases:
 value=delay_ms(attempt,base)
 assert type(value) is int and value==expected,(attempt,base,value,expected)
for attempt,base in [(-1,10),(0,-1),(-1,-1)]:
 try:delay_ms(attempt,base)
 except ValueError:pass
 else:raise AssertionError('negative inputs accepted')
print('15 independent oracle cases passed')
"""


def calls(run):
    events = [json.loads(line) for line in (run / "trace.jsonl").read_text().splitlines()]
    return [
        e["item"]
        for e in events
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"
    ]


def verify(state, uid):
    action = state.get(uid, "action")
    assert action["status"] == "complete" and action["tests_passed"]
    assert action["approval"]["plan_digest"] == action["plan_digest"]
    checked_action(state, action)
    original = state.config(action["project"]).repo_root
    assert state.get(action["project"])["name"] == "Synthetic coding acceptance fixture"
    assert (original / "policy.md").read_text() == POLICY
    assert (
        original / "retry.py"
    ).read_text() == "def delay_ms(attempt, base_ms=10):\n    return base_ms\n"
    assert not git(original, "status", "--porcelain")
    run = action_folder(state, action)
    planning, editing = calls(run / "plan"), calls(run / "editor")
    assert planning and all(c["tool"] != "write_file" for c in planning)
    writes = [c for c in editing if c["tool"] == "write_file"]
    assert writes and all(
        c["server"] == "patch-workspace"
        and c["arguments"]["path"] in action["plan"]["files"]
        and not c.get("error")
        for c in writes
    )
    assert set(action["changed_files"]) <= set(action["plan"]["files"])
    assert action["baseline_includes_proposed_tests"]
    assert any(not t["passed"] for t in action["baseline_tests"])
    assert all(t["passed"] and t["tests_reported"] > 0 for t in action["tests"])
    assert action["lesson_proposal"]["status"] == "draft"
    assert action["lesson_proposal"]["binding"] is False
    try:
        approve(state, uid, action["plan_digest"])
    except ValueError:
        pass
    else:
        raise AssertionError("Consumed approval replay accepted")
    with tempfile.TemporaryDirectory(prefix="oracle-", dir=run) as temp:
        folder = Path(temp)
        clone = folder / "checkout"
        clone_at(original, clone, action["base_revision"])
        patch = folder / "patch.diff"
        patch.write_bytes(action["patch"].encode("utf-8"))
        git(clone, "apply", "--check", str(patch))
        git(clone, "apply", str(patch))
        for name, work, passed in [("original", original, False), ("replayed_patch", clone, True)]:
            scratch = folder / name
            scratch.mkdir()
            command = sandbox_command(work, scratch, ["python", "-c", ORACLE])
            result = bounded_run(
                command, work, test_environment(work, scratch), scratch / "oracle.log"
            )
            assert result["passed"] is passed, name
    manifests = {
        phase: json.loads((run / phase / "invocation.json").read_text())
        for phase in ["plan", "editor"]
    }
    return {
        "status": "passed",
        "scope": "Synthetic application coding acceptance; not a production repository benchmark",
        "base_revision": action["base_revision"],
        "plan_digest": action["plan_digest"],
        "approved_files": action["plan"]["files"],
        "approved_commands": action["plan"]["commands"],
        "changed_files": action["changed_files"],
        "patch_sha256": hashlib.sha256(action["patch"].encode()).hexdigest(),
        "baseline_regression_tests_failed": True,
        "patched_tests_reported": [t["tests_reported"] for t in action["tests"]],
        "held_out_oracle_cases": 15,
        "downloaded_patch_replay_passed": True,
        "original_oracle_failed": True,
        "original_checkout_unchanged": True,
        "consumed_approval_replay_rejected": True,
        "lesson_status": "unaccepted draft",
        "invocations": manifests,
        "limits": [
            "Local trusted operator; browser approval exercised manually on disposable fixture",
            "macOS Codex sandbox tested; Linux depends on compatible installed sandbox; Windows execution unavailable",
            "No automatic dependency installation, network, apply, commit, push or memory acceptance",
            "Citation checks establish provenance and literal quotations, not semantic entailment",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["config", "data", "action", "output"]:
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    state = State(
        args.data, load_config(Path(args.config).resolve()), "verification-only", recover=False
    )
    report = verify(state, args.action)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Verified approval, evidence, baseline, patch replay and 15 independent oracle cases")


if __name__ == "__main__":
    main()
