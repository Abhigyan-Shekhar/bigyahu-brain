"""Durable four-step coordinator: autonomous research, separately reviewed effects."""

import json
import time

from ..graph import GraphStore
from ..memory import canonical, digest
from . import actions, document_store, documentation, email_connector, github_actions, next_step
from .activity import TOOLS
from .evidence import ready
from .workflow_policy import Budget, WorkflowStopped


def scoped(state, project, uid):
    value = state.get(uid, "workflow")
    if value["project"] != project:
        raise KeyError("Unknown workflow")
    return value


def step_folder(state, workflow, step):
    return state.folder(workflow["project"]) / "workflows" / workflow["id"] / step["id"]


def context(state, workflow):
    if ready(GraphStore(state.config(workflow["project"]))) != workflow["source_revision"]:
        raise ValueError("Workflow source revision changed")
    sources = []
    if workflow.get("source_turn_id"):
        sources, _ = documentation.source_context(
            state, workflow["project"], workflow["source_turn_id"]
        )
    for step in state.list("workflow_step", workflow["id"]):
        if step.get("status") == "complete" and step.get("claims"):
            documentation.checked(
                state,
                workflow["project"],
                step_folder(state, workflow, step) / "evidence",
                {"claims": step["claims"]},
            )
            sources.append((step_folder(state, workflow, step) / "evidence", step["claims"]))
    destination = state.folder(workflow["project"]) / "workflows" / workflow["id"] / "context"
    for evidence_folder, claims in sources:
        documentation.checked(state, workflow["project"], evidence_folder, {"claims": claims})
    return sources, documentation.seed_evidence(state, workflow["project"], destination, sources)


def record_retrieval(state, workflow):
    root = state.folder(workflow["project"]) / "workflows" / workflow["id"]
    count = 0
    global_db = root / "retrieval-budget.sqlite"
    if global_db.exists():
        import sqlite3

        with sqlite3.connect(global_db) as db:
            count = db.execute("SELECT used FROM budget WHERE id=1").fetchone()[0]
        state.update(workflow["id"], retrieval_calls=count)
        if count >= workflow["limits"]["max_retrieval_calls"]:
            raise WorkflowStopped("Aggregate retrieval budget reached")
        return
    for path in root.rglob("retrieval.json") if root.exists() else []:
        count += json.loads(path.read_text()).get("used", 0)
    state.update(workflow["id"], retrieval_calls=count)
    if count >= workflow["limits"]["max_retrieval_calls"]:
        raise WorkflowStopped("Aggregate retrieval budget reached")


def complete_step(state, step, **fields):
    state.update(step["id"], status="complete", finished_at=document_store.now(), **fields)


def current_steps(state, uid):
    steps = state.list("workflow_step", uid)
    for step in steps:
        artifacts = []
        for artifact in step.get("artifacts", []):
            value = state.get(artifact["id"])
            info = {**artifact, "status": value["status"]}
            if artifact["kind"] == "fix" and value["status"] == "complete":
                info["verification"] = actions.verification_result(value)
            if value.get("email_job"):
                info["status"] = state.get(value["email_job"])["status"]
            artifacts.append(info)
        step["artifacts"] = artifacts
    return steps


def run(state, uid):
    if not state.transition(
        uid, {"status": "queued"}, status="running", stage="Choosing the next evidence-based step"
    ):
        return
    workflow = state.get(uid, "workflow")
    budget, active = Budget(state, uid), None
    try:
        while True:
            workflow, _ = budget.check()
            previous = current_steps(state, uid)
            if len(previous) >= workflow["limits"]["max_steps"]:
                raise WorkflowStopped("Workflow step budget reached")
            sources, evidence = context(state, workflow)
            record_retrieval(state, workflow)
            proposal, prompt_digest = next_step.suggest(state, workflow, evidence, previous, budget)
            budget.check()
            context(state, workflow)
            if proposal["kind"] in {"ask_user", "complete"}:
                state.update(
                    uid,
                    status="needs_input" if proposal["kind"] == "ask_user" else "complete",
                    stage="User input needed"
                    if proposal["kind"] == "ask_user"
                    else "Workflow complete; review prepared artifacts",
                    stopping_reason=proposal["objective"],
                    completed_at=document_store.now(),
                )
                break
            active = state.create(
                "workflow_step",
                uid,
                workflow=uid,
                project=workflow["project"],
                status="running",
                **proposal,
                prompt_digest=prompt_digest,
                model=state.model,
                allowed_tools=list(TOOLS),
                started_at=document_store.now(),
                artifacts=[],
            )
            state.update(uid, stage=proposal["objective"], active_step=active["id"])
            if proposal["kind"] == "research":
                output, claims, reviews, sha = documentation.research(
                    state,
                    workflow["project"],
                    step_folder(state, workflow, active),
                    proposal["objective"],
                    sources=sources,
                    budget=budget,
                    context={
                        "original_goal": workflow["goal"],
                        "criteria": proposal["completion_criteria"],
                    },
                )
                budget.check()
                complete_step(
                    state,
                    active,
                    claims=claims,
                    limitations=output["limitations"],
                    relevance_review=reviews,
                    source_revision=sha,
                )
            elif proposal["kind"] == "draft_document":
                completed_fix = next(
                    (
                        a["id"]
                        for s in reversed(previous)
                        for a in s.get("artifacts", [])
                        if a["kind"] == "fix" and a["status"] == "complete"
                    ),
                    None,
                )
                document = documentation.create(
                    state,
                    workflow["project"],
                    {
                        "kind": "custom",
                        "instruction": workflow["goal"]
                        + "\nDocumentation task: "
                        + proposal["objective"],
                        "destination": "app_docs",
                        "proposed_repo_path": None,
                        "source_turn_id": workflow.get("source_turn_id"),
                        "source_action_id": completed_fix,
                    },
                )
                state.update(active["id"], artifacts=[{"kind": "document", "id": document["id"]}])
                documentation.generate(state, document["id"], budget=budget, sources=sources)
                document = state.get(document["id"])
                if document["status"] != "draft":
                    raise ValueError(document.get("error", "Documentation not ready"))
                budget.check()
                complete_step(
                    state,
                    active,
                    artifacts=[{"kind": "document", "id": document["id"], "status": "draft"}],
                )
            elif proposal["kind"] == "propose_fix":
                parent = next(
                    (
                        s
                        for s in reversed(previous)
                        if s.get("claims") and s["status"] == "complete"
                    ),
                    None,
                )
                if parent is None and not workflow.get("source_turn_id"):
                    raise ValueError("A fix proposal needs a completed workflow research step")
                action = state.create(
                    "action",
                    workflow["project"],
                    project=workflow["project"],
                    **({"source_workflow": uid} if parent else {"workflow_owner": uid}),
                    turn=parent["id"] if parent else workflow["source_turn_id"],
                    objective=workflow["goal"][:4000] + "\n" + proposal["objective"],
                    status="queued",
                    phase="planning",
                    stage="Workflow fix plan queued",
                )
                state.update(active["id"], artifacts=[{"kind": "fix", "id": action["id"]}])
                actions.prepare_plan(state, action["id"], budget=budget)
                action = state.get(action["id"])
                if action["status"] != "awaiting_approval":
                    raise ValueError(action.get("error", "Fix plan was not supported"))
                budget.check()
                complete_step(
                    state,
                    active,
                    artifacts=[{"kind": "fix", "id": action["id"], "status": "awaiting_approval"}],
                )
            else:
                if not evidence:
                    raise ValueError("Connector drafts require current checked evidence")
                # Payload is derived from checked observations. The model cannot choose a recipient, branch, or issue target.
                text = "\n\n".join(c["text"] for _, claims in sources for c in claims)[:12000]
                title = proposal["objective"][:200]
                if proposal["kind"].startswith("draft_github"):
                    kind = {
                        "draft_github_issue": "issue",
                        "draft_github_comment": "comment",
                        "draft_github_pr": "pull_request",
                    }[proposal["kind"]]
                    targets = workflow["connector_targets"]
                    draft = github_actions.preview(
                        state,
                        workflow["project"],
                        {
                            "kind": kind,
                            "title": title,
                            "body": text
                            + "\n\nPrepared from reviewed source observations; independent verification may remain pending.",
                            "number": targets.get("issue_number"),
                            "head": targets.get("head", ""),
                            "base": targets.get("base", ""),
                        },
                    )
                    state.update(draft["id"], source_workflow=uid)
                    artifact = {"kind": "github", "id": draft["id"], "status": "draft"}
                else:
                    recipient = workflow["connector_targets"].get("recipient")
                    if not recipient:
                        raise ValueError(
                            "Enter an email recipient in the workflow settings; recipients cannot come from sources"
                        )
                    content = {
                        "project": workflow["project"],
                        "recipient": recipient,
                        "sender": email_connector.connection().get("sender"),
                        "subject": title,
                        "body": text,
                    }
                    draft = state.create(
                        "workflow_email_draft",
                        workflow["project"],
                        **content,
                        status="draft",
                        consent_digest=digest(canonical(content)),
                        binding=False,
                    )
                    artifact = {"kind": "email", "id": draft["id"], "status": "draft"}
                budget.check()
                complete_step(state, active, artifacts=[artifact])
            active = None
            record_retrieval(state, workflow)
    except Exception as exc:  # noqa: BLE001
        current = state.get(uid)
        cancelled = current.get("stop_requested")
        reason = (
            str(exc)[:1000]
            if isinstance(exc, ValueError)
            else "Workflow worker failed; no external publication authorized"
        )
        if active:
            state.update(
                active["id"],
                status="stopped" if isinstance(exc, WorkflowStopped) else "failed",
                error=reason,
                finished_at=document_store.now(),
            )
        exhausted = isinstance(exc, WorkflowStopped) or (
            "budget" in reason.lower()
            and current.get("model_calls", 0) >= current["limits"]["max_model_calls"]
        )
        state.update(
            uid,
            status="stopped" if cancelled else "budget_exhausted" if exhausted else "failed",
            stage="Workflow stopped",
            stopping_reason=reason,
            completed_at=document_store.now(),
        )
    finally:
        state.update(
            uid,
            elapsed_seconds=budget.prior_seconds + time.monotonic() - budget.started,
            active_step=None,
        )


def snapshot(state, project, uid):
    value = scoped(state, project, uid)
    return {**value, "steps": current_steps(state, uid)}
