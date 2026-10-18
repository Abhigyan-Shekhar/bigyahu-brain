"""Project-scoped documentation and workflow HTTP boundaries."""

import difflib
import json
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..graph import GraphStore
from . import actions, document_patch, document_store, documentation
from .enrichment import active_ingestions
from .evidence import resolve
from .sources import upload_document
from .streaming import snapshots


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal[
        "architecture", "runbook", "incident", "adr", "api_guide", "change_summary", "custom"
    ] = "custom"
    instruction: str = Field(min_length=1, max_length=8000)
    destination: Literal["app_docs", "repo_patch"] = "app_docs"
    proposed_repo_path: str | None = Field(default=None, max_length=180)
    source_turn_id: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")
    source_action_id: str | None = Field(default=None, pattern="^[a-f0-9]{32}$")


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_digest: str = Field(pattern="^[a-f0-9]{64}$")
    source_revision: str = Field(pattern="^[a-f0-9]{40,64}$")


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1, max_length=8000)
    expected_digest: str = Field(pattern="^[a-f0-9]{64}$")


def install(app, state, workers, lock, project_ready):
    prefix = "/api/repositories/{project}/documentation/drafts"

    def idle(project):
        project_ready(project)
        if (
            actions.active_actions(state, project)
            or active_ingestions(state, project)
            or any(
                t["status"] in {"queued", "running"}
                for s in state.list("session", project)
                for t in state.list("turn", s["id"])
            )
        ):
            raise HTTPException(409, "Finish the active research, ingestion or plan first")

    def detail(project, uid):
        value = document_store.scoped(state, project, uid)
        if value.get("content_digest"):
            value["markdown"] = document_store.content(state, value)
            from .action_mcp import read_file

            original = read_file(state.config(project).repo_root, value["proposed_repo_path"])
            value["diff"] = "".join(
                difflib.unified_diff(
                    original["text"].splitlines(keepends=True),
                    value["markdown"].splitlines(keepends=True),
                    fromfile="a/" + value["proposed_repo_path"],
                    tofile="b/" + value["proposed_repo_path"],
                )
            )
            try:
                documentation.validate(state, value)
                value["stale"] = False
            except (ValueError, OSError, PermissionError, KeyError):
                value["stale"] = True
        return value

    @app.post(prefix, status_code=202)
    def create_document(project: str, body: DraftInput):
        with lock:
            idle(project)
            if len(state.list("documentation_draft", project)) >= 100:
                raise ValueError("Documentation history limit reached")
            value = documentation.create(state, project, body.model_dump())
            workers.submit(documentation.generate, state, value["id"])
        return value

    @app.get(prefix)
    def documents(project: str):
        state.get(project, "repository")
        return {"items": state.list("documentation_draft", project)[-100:]}

    @app.get(prefix + "/{uid}")
    def get_document(project: str, uid: str):
        return detail(project, uid)

    @app.get(prefix + "/{uid}/events")
    def events(project: str, uid: str, request: Request):
        document_store.scoped(state, project, uid)
        return StreamingResponse(
            snapshots(request, lambda: detail(project, uid), terminal=True),
            media_type="text/event-stream",
        )

    @app.get(prefix + "/{uid}/evidence/{evidence_id}")
    def evidence(project: str, uid: str, evidence_id: str):
        value = document_store.scoped(state, project, uid)
        documentation.validate(state, value)
        if evidence_id not in {s["evidence_id"] for c in value["claims"] for s in c["support"]}:
            raise KeyError("Unknown citation")
        saved = json.loads(
            (documentation.folder(state, value) / "evidence" / (evidence_id + ".json")).read_text()
        )
        return {"id": evidence_id, **resolve(GraphStore(state.config(project)), saved)}

    @app.post(prefix + "/{uid}/revise", status_code=202)
    def revise(project: str, uid: str, body: RevisionInput):
        with lock:
            idle(project)
            old = document_store.scoped(state, project, uid)
            if old.get("review_digest") != body.expected_digest:
                raise ValueError("Document changed; reload before revising")
            values = {key: old.get(key) for key in DraftInput.model_fields}
            values["instruction"] = (
                old["instruction"][:3500]
                + "\nRevision requested by user: "
                + body.instruction[:4000]
            )
            value = documentation.create(state, project, values)
            state.update(value["id"], supersedes=uid)
            workers.submit(documentation.generate, state, value["id"])
            return value

    @app.post(prefix + "/{uid}/approve")
    def approve(project: str, uid: str, body: ReviewInput):
        with lock:
            idle(project)
            return document_store.approve(
                state,
                project,
                uid,
                body.expected_digest,
                body.source_revision,
                documentation.validate,
            )

    @app.get(prefix + "/{uid}/download")
    def download(project: str, uid: str):
        value = document_store.scoped(state, project, uid)
        return PlainTextResponse(
            document_store.content(state, value),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{Path(value["proposed_repo_path"]).name}"',
            },
        )

    def reviewed(project, uid, body):
        value = document_store.scoped(state, project, uid)
        if (
            value.get("review_digest") != body.expected_digest
            or value.get("source_revision") != body.source_revision
        ):
            raise ValueError("Document changed; review again")
        documentation.validate(state, value)
        return value

    @app.post(prefix + "/{uid}/prepare-patch", status_code=201)
    def prepare_patch(project: str, uid: str, body: ReviewInput):
        with lock:
            idle(project)
            return document_patch.prepare(
                state, reviewed(project, uid, body), documentation.validate
            )

    @app.post(prefix + "/{uid}/patches/{patch_id}/approve")
    def approve_patch(project: str, uid: str, patch_id: str, body: ReviewInput):
        with lock:
            idle(project)
            patch = state.get(patch_id, "documentation_patch")
            if patch["document"] != uid or patch["source_revision"] != body.source_revision:
                raise ValueError("Patch does not match the document/revision")
            return document_patch.approve(
                state, project, patch_id, body.expected_digest, documentation.validate
            )

    @app.post(prefix + "/{uid}/index-approved")
    def index(project: str, uid: str, body: ReviewInput):
        with lock:
            idle(project)
            value = reviewed(project, uid, body)
            if value["status"] != "approved":
                raise ValueError("Approve App Docs before indexing")
            if value.get("indexing_result"):
                return value["indexing_result"]
            result = upload_document(
                state,
                project,
                "generated-" + uid + ".md",
                document_store.content(state, value),
                generated_provenance=json.dumps(
                    {
                        "document": uid,
                        "review_digest": value["review_digest"],
                        "source_evidence_ids": sorted(
                            {s["evidence_id"] for c in value["claims"] for s in c["support"]}
                        ),
                    }
                ),
            )
            state.update(uid, indexing_result=result, indexed_at=document_store.now())
            return result

    from .workflow_api import install as install_workflows

    install_workflows(app, state, workers, lock, project_ready, idle)
