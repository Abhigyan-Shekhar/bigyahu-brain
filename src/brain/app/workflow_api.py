"""Workflow opt-in, live child records and independent connector review controls."""

from typing import Literal

from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..graph import GraphStore
from ..memory import canonical, digest
from . import document_store, documentation, email_connector, orchestrator
from .evidence import ready, resolve
from .streaming import snapshots
from .workflow_policy import CAPABILITIES, MAX_CALLS, MAX_SECONDS, MAX_STEPS


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=8000)
    auto_investigate: Literal[True]
    capabilities: list[str] = Field(min_length=1, max_length=8)
    source_turn_id: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")
    max_steps: int = Field(default=4, ge=1, le=MAX_STEPS)
    max_model_calls: int = Field(default=8, ge=1, le=MAX_CALLS)
    max_wall_seconds: int = Field(default=900, ge=30, le=MAX_SECONDS)
    recipient: str | None = Field(default=None, max_length=254)
    issue_number: int | None = Field(default=None, ge=1)
    head: str = Field(default="", max_length=200)
    base: str = Field(default="", max_length=200)


class Resume(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clarification: str = Field(default="", max_length=4000)
    expected_status: str


class Consent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent_digest: str = Field(pattern="^[a-f0-9]{64}$")


def install(app, state, workers, lock, project_ready, idle):
    prefix = "/api/repositories/{project}/workflows"

    @app.post(prefix, status_code=202)
    def create(project: str, body: Input):
        with lock:
            idle(project)
            if not body.goal.strip():
                raise ValueError("Enter a nonempty workflow goal")
            if not set(body.capabilities) <= CAPABILITIES or "research" not in body.capabilities:
                raise ValueError(
                    "Workflow capabilities require research and must be server-allowed"
                )
            if len(state.list("workflow", project)) >= 30:
                raise ValueError("Workflow history limit reached")
            documentation.source_context(state, project, body.source_turn_id)
            targets = {
                key: getattr(body, key) for key in ("recipient", "issue_number", "head", "base")
            }
            if body.recipient:
                email_connector.address(body.recipient)
            if "draft_email" in body.capabilities and not body.recipient:
                raise ValueError("Enter the email recipient explicitly")
            if "draft_github_comment" in body.capabilities and not body.issue_number:
                raise ValueError("Enter the issue/PR number explicitly")
            if "draft_github_pr" in body.capabilities and not body.head:
                raise ValueError("Select an existing pushed head branch")
            value = state.create(
                "workflow",
                project,
                project=project,
                goal=body.goal,
                source_turn_id=body.source_turn_id,
                capabilities=sorted(set(body.capabilities)),
                connector_targets=targets,
                source_revision=ready(GraphStore(state.config(project))),
                status="queued",
                stage="Workflow queued",
                limits={
                    "max_steps": body.max_steps,
                    "max_model_calls": body.max_model_calls,
                    "max_wall_seconds": body.max_wall_seconds,
                    "max_retrieval_calls": 60,
                },
                model_calls=0,
                elapsed_seconds=0,
                retrieval_calls=0,
                stop_requested=False,
                created_at=document_store.now(),
            )
            workers.submit(orchestrator.run, state, value["id"])
            return value

    @app.get(prefix)
    def workflows(project: str):
        state.get(project, "repository")
        return {"items": state.list("workflow", project)}

    @app.get(prefix + "/{uid}")
    def detail(project: str, uid: str):
        return orchestrator.snapshot(state, project, uid)

    @app.get(prefix + "/{uid}/events")
    def events(project: str, uid: str, request: Request):
        orchestrator.scoped(state, project, uid)
        return StreamingResponse(
            snapshots(request, lambda: orchestrator.snapshot(state, project, uid), terminal=True),
            media_type="text/event-stream",
        )

    @app.post(prefix + "/{uid}/stop")
    def stop(project: str, uid: str):
        with lock:
            value = orchestrator.scoped(state, project, uid)
            if value["status"] == "queued":
                state.transition(
                    uid,
                    {"status": "queued"},
                    status="stopped",
                    stop_requested=True,
                    stopping_reason="Stopped before execution",
                )
            elif value["status"] == "running":
                state.update(uid, stop_requested=True, stage="Stopping current read-only worker")
            return orchestrator.snapshot(state, project, uid)

    @app.post(prefix + "/{uid}/resume", status_code=202)
    def resume(project: str, uid: str, body: Resume):
        with lock:
            idle(project)
            value = orchestrator.scoped(state, project, uid)
            if (
                value["status"] not in {"stopped", "needs_input", "failed"}
                or value["status"] != body.expected_status
            ):
                raise ValueError("Workflow is not available to resume")
            if (
                value["model_calls"] >= value["limits"]["max_model_calls"]
                or value["elapsed_seconds"] >= value["limits"]["max_wall_seconds"]
                or len(state.list("workflow_step", uid)) >= value["limits"]["max_steps"]
            ):
                raise ValueError(
                    "Workflow budget exhausted; start a new explicitly scoped workflow"
                )
            orchestrator.context(state, value)
            if not state.transition(
                uid,
                {"status": body.expected_status},
                status="queued",
                stop_requested=False,
                clarification=body.clarification,
                stage="Workflow resume queued",
                stopping_reason=None,
            ):
                raise ValueError("Resume was already consumed")
            workers.submit(orchestrator.run, state, uid)
            return state.get(uid)

    @app.get(prefix + "/{uid}/evidence/{evidence_id}")
    def evidence(project: str, uid: str, evidence_id: str):
        value = orchestrator.scoped(state, project, uid)
        _, current = orchestrator.context(state, value)
        proof = next((item for item in current if item["id"] == evidence_id), None)
        if proof is None:
            raise KeyError("Unknown workflow citation")
        return {"id": evidence_id, **resolve(GraphStore(state.config(project)), proof)}

    @app.get(prefix + "/{uid}/artifacts/{artifact_id}")
    def artifact(project: str, uid: str, artifact_id: str):
        orchestrator.scoped(state, project, uid)
        if artifact_id not in {
            a["id"] for s in state.list("workflow_step", uid) for a in s.get("artifacts", [])
        }:
            raise KeyError("Unknown workflow artifact")
        value = state.get(artifact_id)
        if value.get("email_job"):
            job = email_connector.public(state.get(value["email_job"], "email"))
            return {**value, "status": job["status"], "email_result": job}
        return value

    @app.post(prefix + "/{uid}/emails/{draft_id}/send", status_code=202)
    def email_send(project: str, uid: str, draft_id: str, body: Consent):
        with lock:
            workflow = orchestrator.scoped(state, project, uid)
            orchestrator.context(state, workflow)
            value = artifact(project, uid, draft_id)
            draft = state.get(draft_id, "workflow_email_draft")
            content = {
                key: value[key] for key in ("project", "recipient", "sender", "subject", "body")
            }
            if (
                draft["project"] != project
                or body.consent_digest != draft["consent_digest"]
                or digest(canonical(content)) != body.consent_digest
            ):
                raise ValueError("Email draft changed; review its exact content")
            if draft.get("email_job"):
                return email_connector.public(state.get(draft["email_job"], "email"))
            if draft["status"] != "draft":
                raise ValueError("Email send was already attempted")
            cfg = email_connector.settings()
            if cfg["sender"] != draft.get("sender"):
                raise ValueError("Refresh the email sender preview and review before sending")
            if not state.transition(
                draft_id,
                {"status": "draft", "consent_digest": body.consent_digest},
                status="sending",
            ):
                raise ValueError("Email send was already consumed")
            job = state.create(
                "email",
                project,
                project=project,
                recipient=draft["recipient"],
                sender=cfg["sender"],
                purpose="Send the exact user-reviewed workflow draft",
                turn=None,
                status="queued",
                stage="Reviewed email queued",
                connection_identity=email_connector.identity(cfg),
                context={},
                reviewed_content={"subject": draft["subject"], "body": draft["body"]},
                delivery_started=False,
                created_at=document_store.now(),
            )
            state.update(draft_id, status="send_queued", email_job=job["id"])
            workers.submit(email_connector.run_email, state, job["id"])
            return email_connector.public(job)

    @app.post(prefix + "/{uid}/emails/{draft_id}/refresh-sender")
    def refresh_email_sender(project: str, uid: str, draft_id: str, body: Consent):
        with lock:
            value = artifact(project, uid, draft_id)
            if value["status"] != "draft" or value["consent_digest"] != body.consent_digest:
                raise ValueError("Only the current unsent draft can refresh its sender")
            sender = email_connector.settings()["sender"]
            content = {key: value[key] for key in ("project", "recipient", "subject", "body")}
            content["sender"] = sender
            return state.update(draft_id, sender=sender, consent_digest=digest(canonical(content)))
