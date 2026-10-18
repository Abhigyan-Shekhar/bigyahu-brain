"""Server-owned workflow capability, usage and cancellation boundaries."""

import time

from .activity import TOOLS

CAPABILITIES = {
    "research",
    "draft_document",
    "propose_fix",
    "draft_github_issue",
    "draft_github_comment",
    "draft_github_pr",
    "draft_email",
}
MAX_STEPS, MAX_CALLS, MAX_SECONDS, MAX_RETRIEVAL = 4, 8, 900, 60


class WorkflowStopped(ValueError):
    pass


class Budget:
    def __init__(self, state, uid):
        self.state, self.uid = state, uid
        self.started = time.monotonic()
        self.prior_seconds = state.get(uid).get("elapsed_seconds", 0)
        value = state.get(uid)
        self.retrieval_folder = state.folder(value["project"]) / "workflows" / uid

    def check(self):
        value = self.state.get(self.uid)
        elapsed = self.prior_seconds + time.monotonic() - self.started
        if value.get("stop_requested") or value.get("status") != "running":
            raise WorkflowStopped("Workflow stopped by user")
        if elapsed >= value["limits"]["max_wall_seconds"]:
            raise WorkflowStopped("Workflow wall-clock budget reached")
        return value, elapsed

    def consume(self):
        value, elapsed = self.check()
        calls = value.get("model_calls", 0)
        if calls >= value["limits"]["max_model_calls"]:
            raise WorkflowStopped("Workflow model-call budget reached")
        self.state.update(self.uid, model_calls=calls + 1, elapsed_seconds=elapsed)
        return max(0.1, min(180, value["limits"]["max_wall_seconds"] - elapsed))


def authorize(proposal, capabilities):
    if proposal["kind"] not in {*capabilities, "ask_user", "complete"}:
        raise ValueError("Next step requests a capability the user did not authorize")
    if set(proposal["required_tools"]) - set(TOOLS):
        raise ValueError("Next step requests tools outside the read-only allowlist")
    if proposal["kind"] in {"ask_user", "complete"} and proposal["required_tools"]:
        raise ValueError("A stopping step cannot request tools")
