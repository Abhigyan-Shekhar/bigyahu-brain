"""Global budget accounting, retrieval limits and child-process cancellation."""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from brain.app.process import model_process
from brain.app.retrieval import reserve_workflow_call
from brain.app.workflow_policy import Budget, WorkflowStopped


def test_budget_persists_model_count_and_does_not_reset_on_resume(authored):
    state = authored.state
    workflow = state.create(
        "workflow",
        authored.project,
        project=authored.project,
        status="running",
        model_calls=0,
        elapsed_seconds=0,
        limits={"max_wall_seconds": 900, "max_model_calls": 2},
    )
    budget = Budget(state, workflow["id"])
    assert 0 < budget.consume() <= 180
    assert Budget(state, workflow["id"]).consume() > 0
    with pytest.raises(WorkflowStopped, match="model-call"):
        budget.consume()
    state.update(workflow["id"], stop_requested=True)
    with pytest.raises(WorkflowStopped, match="user"):
        budget.check()


def test_wall_clock_budget_is_enforced_before_another_call(authored):
    workflow = authored.state.create(
        "workflow",
        authored.project,
        project=authored.project,
        status="running",
        elapsed_seconds=901,
        limits={"max_wall_seconds": 900, "max_model_calls": 8},
    )
    with pytest.raises(WorkflowStopped, match="wall-clock"):
        Budget(authored.state, workflow["id"]).consume()


def test_shared_retrieval_limit_survives_concurrency_and_reconnect(tmp_path):
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: reserve_workflow_call(tmp_path), range(80)))
    assert sum(outcomes) == 60
    assert not reserve_workflow_call(tmp_path)


@pytest.mark.skipif(os.name == "nt", reason="POSIX child process probe")
def test_user_stop_kills_current_model_process(tmp_path):
    started = time.monotonic()

    def stop():
        if time.monotonic() - started > 0.1:
            raise WorkflowStopped("User stopped")

    with (
        (tmp_path / "trace").open("w") as trace,
        (tmp_path / "err").open("w") as err,
        pytest.raises(WorkflowStopped),
    ):
        model_process(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            "",
            trace,
            err,
            dict(os.environ),
            30,
            cancel_check=stop,
        )
    assert time.monotonic() - started < 5
