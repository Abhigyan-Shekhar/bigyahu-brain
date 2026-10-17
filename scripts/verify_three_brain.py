"""Independent oracle and trace assertions for the synthetic agent demonstration."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from demo_three_brain import POLICY


def verify(run):
    events = [json.loads(line) for line in (run / "agent/trace.jsonl").read_text().splitlines()]
    calls = [
        (i, e["item"])
        for i, e in enumerate(events)
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"
    ]

    def payload(item):
        if item.get("status") != "completed" or item.get("error"):
            return {}
        result = item.get("result") or {}
        for content in result.get("content", []):
            if content.get("type") == "text":
                return json.loads(content["text"])
        return {}

    search = [(i, payload(item)) for i, item in calls if item["tool"] == "memory_search"]
    graphs = [(i, payload(item)) for i, item in calls if item["tool"] == "memory_graph"]
    private = [
        (i, r)
        for i, r in search
        if r.get("status") == "ok"
        and r.get("backend") == "falkor"
        and any(n.get("brain") == "private:alice" for n in r.get("items", []))
    ]
    joined = [
        (i, r)
        for i, r in graphs
        if r.get("status") == "ok"
        and {"private:alice", "team:runtime", "company"}
        <= {n.get("brain") for n in r.get("nodes", [])}
        and {"SAME_CITATION", "VERIFIED_SOURCE"} <= {e["relation"] for e in r.get("edges", [])}
        and any(
            n["kind"] == "CompanySource"
            and n.get("digest") == hashlib.sha256(POLICY.encode()).hexdigest()
            and n.get("text") == POLICY
            for n in r.get("nodes", [])
        )
    ]
    assert private and joined, "Missing successful private search or verified three-brain graph"
    edits = [
        i
        for i, e in enumerate(events)
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "file_change"
    ]
    assert edits and max(private[0][0], joined[0][0]) < min(edits), "Evidence must precede edits"
    assert "HIDDEN_THREE_BRAIN_CANARY" not in json.dumps([payload(item) for _, item in calls])
    assert (run / "checkout/policy.md").read_text() == POLICY
    oracle = """
from retry import delay_ms
cases = [(0,10,10),(1,10,20),(2,10,40),(6,10,640),(7,10,800),(20,10,800),
         (0,1000,800),(0,0,0),(4,0,0),(3,7,56),(1,1,2),(0,800,800)]
for attempt,base,expected in cases:
 value=delay_ms(attempt,base)
 assert type(value) is int and value==expected,(attempt,base,value,expected)
for attempt,base in [(-1,10),(0,-1),(-1,-1)]:
 try: delay_ms(attempt,base)
 except ValueError: pass
 else: raise AssertionError('negative inputs accepted')
print('15 independent oracle cases passed')
"""
    fixture = json.loads((run / "fixture.json").read_text())
    original = subprocess.check_output(
        ["git", "-C", str(run / "checkout"), "show", fixture["revision"] + ":retry.py"], text=True
    )
    with tempfile.TemporaryDirectory(prefix="three-brain-oracle-") as temp:
        (Path(temp) / "retry.py").write_text(original)
        baseline = subprocess.run(
            [sys.executable, "-c", oracle], cwd=temp, capture_output=True, text=True, check=False
        )
        assert baseline.returncode != 0, "Original fixture should fail the same independent oracle"
    oracle_run = subprocess.run(
        [sys.executable, "-c", oracle],
        cwd=run / "checkout",
        capture_output=True,
        text=True,
        check=False,
    )
    assert oracle_run.returncode == 0, oracle_run.stderr
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-v"],
        cwd=run / "checkout",
        check=False,
        capture_output=True,
        text=True,
    )
    assert tests.returncode == 0 and "Ran 0 tests" not in tests.stderr
    final = (run / "agent/agent-final.txt").read_text()
    source_uris = [
        n["uri"]
        for n in joined[0][1]["nodes"]
        if n["kind"] == "CompanySource" and n.get("text") == POLICY
    ]
    assert any(uri in final for uri in source_uris), "Final response must cite verified source"
    manifest = json.loads((run / "agent/invocation.json").read_text())
    return {
        "scope": "guided_synthetic_three_brain_agent_demonstration",
        "model_requested": manifest["model"],
        "reasoning_requested": manifest["reasoning"],
        "codex_version": manifest["codex_version"],
        "fixture_revision": fixture["revision"],
        "graphify": fixture["graphify"],
        "original_fixture_fails_oracle": True,
        "agent_test_count": int(re.search(r"Ran (\d+) tests?", tests.stderr)[1]),
        "backend_source_sha256": manifest.get("backend_source_sha256", {}),
        "backend_dirty_at_launch": manifest.get("backend_dirty"),
        "private_native_search": True,
        "three_brain_graph": True,
        "verified_source_consumed_before_edits": True,
        "unauthorized_canary_excluded": True,
        "policy_unchanged": True,
        "independent_oracle_cases": 15,
        "agent_tests_passed": True,
        "verified_source_cited": True,
        "patch_sha256": hashlib.sha256((run / "agent/agent.patch").read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256((run / "agent/runner-invoked.py").read_bytes()).hexdigest(),
        "limits": [
            "Synthetic fixture; guided tool-use instructions",
            "One run; no baseline or coding advantage claim",
            "Model identity is requested, not independently attested",
            "Local operator remains trusted",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
