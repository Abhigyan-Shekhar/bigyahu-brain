"""Loopback-only FastAPI application for one trusted local operator."""

import argparse
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..config import load_config
from ..graph import GraphStore, GraphUnavailable
from . import personal, team
from .actions import active_actions, approve, checked_action, execute, prepare_plan
from .agent import run_turn
from .enrichment import active_ingestions, run_enrichment
from .evidence import native_graph, ready, resolve
from .sources import onboard, repository_url, upload_binary, upload_document
from .state import State


class RepositoryInput(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    history: bool = True


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


class ApprovalInput(BaseModel):
    plan_digest: str = Field(min_length=64, max_length=64)


class DocumentInput(BaseModel):
    filename: str = Field(min_length=1, max_length=110)
    text: str | None = Field(default=None, min_length=1, max_length=500000)
    data_base64: str | None = Field(default=None, min_length=1, max_length=1866670)


class EnrichmentInput(BaseModel):
    engine: str
    sources: list[str] = Field(min_length=1, max_length=8)


class PersonalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoteInput(PersonalInput):
    text: str = Field(min_length=1, max_length=4000)


class MemoryReviewInput(PersonalInput):
    expected_hash: str = Field(pattern="^[a-f0-9]{64}$")
    expected_state: str
    action: str
    reason: str = Field(min_length=1, max_length=1000)


class TeamInput(PersonalInput):
    name: str = Field(pattern="^[A-Za-z0-9_-]{1,64}$")


class MembershipInput(PersonalInput):
    principal: str = Field(pattern="^[A-Za-z0-9_-]{1,64}$")
    role: str
    expected_role: str
    reason: str = Field(min_length=1, max_length=1000)


class ShareInput(PersonalInput):
    uid: str = Field(min_length=1, max_length=200)
    expected_hash: str = Field(pattern="^[a-f0-9]{64}$")
    expected_target: str = Field(default="", pattern="^(?:[a-f0-9]{64})?$")


class ConversationSelection(PersonalInput):
    session: str
    turns: list[str] = Field(min_length=1, max_length=20)


class ConversationImport(ConversationSelection):
    consent_digest: str = Field(pattern="^[a-f0-9]{64}$")
    semantic: bool = False


def create_app(state, token, origin, assets=None):
    app = FastAPI(title="Company Brain", docs_url=None, redoc_url=None, openapi_url=None)
    workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="brain-app")
    lock = threading.Lock()
    app.state.workers = workers

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if (
            request.headers.get("host") != origin.removeprefix("http://")
            or request.headers.get("origin", origin) != origin
        ):
            return JSONResponse({"detail": "Local same-origin access required"}, status_code=403)
        if request.url.path.startswith("/api/"):
            if not secrets.compare_digest(
                request.headers.get("authorization", "").encode(), ("Bearer " + token).encode()
            ):
                return JSONResponse(
                    {"detail": "Open the local session URL printed by the server"}, status_code=401
                )
            if request.method in {"POST", "PUT"}:
                length = request.headers.get("content-length")
                if not length or not length.isdigit() or int(length) > 2_100_000:
                    return JSONResponse({"detail": "Request exceeds upload limit"}, status_code=413)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
            }
        )
        return response

    @app.exception_handler(GraphUnavailable)
    async def unavailable(request, exc):
        return JSONResponse(
            {"detail": "Graph is unavailable; check the local database connection"}, status_code=503
        )

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "Unknown resource"}, status_code=404)

    @app.exception_handler(PermissionError)
    async def forbidden(request, exc):
        return JSONResponse({"detail": "Memory scope or action unavailable"}, status_code=403)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    def project_ready(project):
        value = state.get(project, "repository")
        if value["status"] != "ready":
            raise HTTPException(409, "Repository is not ready")
        return value

    @app.get("/api/status")
    def status():
        return {
            "principal": "Local operator",
            "model": state.model,
            "mode": "read_only_investigation",
            "capabilities": [
                "repository_onboarding",
                "markdown_rst_pdf_docx_upload",
                "graphify_semantic_ingestion",
                "falkordb_graphrag_sdk_ingestion",
                "company_chat",
                "personal_memory_review",
                "authorized_team_sharing_navigation",
                "reviewed_lesson_recall",
                "source_inspection",
                "approved_isolated_patch_tests",
            ],
            "deferred": ["abhi_ui"],
        }

    @app.get("/api/repositories")
    def repositories():
        return state.list("repository")

    @app.post("/api/repositories", status_code=202)
    def connect(body: RepositoryInput):
        url = repository_url(body.url)
        with lock:
            if any(r["status"] in {"queued", "running"} for r in state.list("repository")):
                raise HTTPException(409, "Wait for the current indexing job")
            if len(state.list("repository")) >= 20:
                raise HTTPException(409, "Local application limit is 20 repositories")
            project = state.create(
                "repository",
                url=url,
                name=url.removeprefix("https://github.com/"),
                status="queued",
                stage="Queued",
                warnings=[],
            )
            workers.submit(onboard, state, project["id"], body.history)
        return project

    @app.get("/api/repositories/{project}")
    def repository(project: str):
        return state.get(project, "repository")

    @app.get("/api/repositories/{project}/memory")
    def personal_list(project: str):
        project_ready(project)
        cfg = state.config(project)
        if not Path(personal.config(cfg).memory_db).exists():
            return {"items": [], "truncated": False, "binding": False, "initialized": False}
        with lock, personal.catalog(cfg) as (memory, _projection):
            items, truncated = personal.rows(memory)
            links = memory.db.execute(
                "SELECT uid,source_uid,target_uid,relation,state FROM memory_links WHERE tenant=? AND brain=? ORDER BY rowid DESC LIMIT 100",
                (memory.identity.tenant, personal.brain(memory)),
            ).fetchall()
            return {
                "items": items,
                "truncated": truncated,
                "binding": False,
                "initialized": True,
                "relationships": [dict(r) for r in links],
            }

    @app.post("/api/repositories/{project}/memory", status_code=201)
    def personal_propose(project: str, body: NoteInput):
        project_ready(project)
        with lock:
            return personal.propose_note(state.config(project), body.text)

    @app.get("/api/repositories/{project}/memory/graph")
    def personal_graph(project: str):
        project_ready(project)
        cfg = state.config(project)
        if not Path(personal.config(cfg).memory_db).exists():
            return {
                "status": "unavailable",
                "graph": {"nodes": [], "edges": []},
                "warnings": ["Add a memory to initialize this Personal Brain"],
            }
        with lock, personal.catalog(cfg) as (memory, projection):
            view = projection.read([personal.brain(memory)], include_proposals=True)
            return {
                "status": view["status"],
                "graph": personal.graph_view(view),
                "warnings": view["warnings"],
            }

    @app.post("/api/repositories/{project}/memory/refresh")
    def personal_refresh(project: str):
        project_ready(project)
        with lock, personal.catalog(state.config(project)) as (memory, projection):
            return personal.refresh(memory, projection)

    @app.get("/api/repositories/{project}/memory/records/{uid}")
    def personal_detail(project: str, uid: str):
        project_ready(project)
        cfg = state.config(project)
        with lock, personal.catalog(cfg) as (memory, _projection):
            record = personal.row(memory, uid)
            try:
                sources = personal.source_details(cfg, memory, record)
                error = None
            except (ValueError, OSError):
                sources, error = (
                    [],
                    "Original memory source is unavailable or changed; acceptance is blocked.",
                )
            reviews = memory.db.execute(
                "SELECT actor,action,at,detail FROM events WHERE tenant=? AND brain=? AND uid=? AND action IN ('accept','reject','rollback') ORDER BY rowid DESC LIMIT 30",
                (memory.identity.tenant, personal.brain(memory), uid),
            ).fetchall()
            return {
                "uid": uid,
                "text": record["text"],
                "state": record["state"],
                "hash": record["hash"],
                "sources": sources,
                "source_error": error,
                "reviews": [dict(r) for r in reviews],
                "binding": False,
            }

    @app.post("/api/repositories/{project}/memory/records/{uid}/review")
    def personal_review(project: str, uid: str, body: MemoryReviewInput):
        project_ready(project)
        with lock:
            return personal.review(
                state.config(project),
                uid,
                body.expected_hash,
                body.expected_state,
                body.action,
                body.reason,
            )

    @app.get("/api/repositories/{project}/memory/imports")
    def memory_imports(project: str):
        project_ready(project)
        return [
            {k: v for k, v in job.items() if k != "turns"}
            for job in state.list("memory_import", project)
        ]

    @app.post("/api/repositories/{project}/memory/preview")
    def memory_preview(project: str, body: ConversationSelection):
        project_ready(project)
        return personal.conversation_preview(state, project, body.session, body.turns)

    @app.post("/api/repositories/{project}/memory/imports", status_code=202)
    def memory_import(project: str, body: ConversationImport):
        project_ready(project)
        preview = personal.conversation_preview(state, project, body.session, body.turns)
        if preview["consent_digest"] != body.consent_digest:
            raise ValueError("Consent must match the exact previewed user turns")
        with lock:
            jobs = state.list("memory_import", project)
            if len(jobs) >= 30 or any(j["status"] in {"running", "queued"} for j in jobs):
                raise HTTPException(
                    409, "Finish the current import; local limit is 30 imports per repository"
                )
            job = state.create(
                "memory_import",
                project,
                project=project,
                session=body.session,
                turns=body.turns,
                consent_digest=body.consent_digest,
                semantic=body.semantic,
                status="queued",
                stage="Selected conversation import queued",
            )
            workers.submit(personal.import_selected, state, job["id"])
        return {"id": job["id"], "status": job["status"]}

    @app.post("/api/repositories/{project}/actions/{action_id}/lesson", status_code=201)
    def lesson_proposal(project: str, action_id: str):
        project_ready(project)
        if state.get(action_id, "action")["project"] != project:
            raise HTTPException(404, "Unknown action in this repository")
        with lock:
            return personal.propose_lesson(state, action_id)

    @app.get("/api/repositories/{project}/teams")
    def team_list(project: str):
        project_ready(project)
        cfg = state.config(project)
        if not Path(personal.config(cfg).memory_db).exists():
            return {"items": [], "principal": cfg.principal, "truncated": False}
        with lock, personal.catalog(cfg) as (memory, _):
            names = team.authorized(memory)
            return {
                "items": [team.team_info(memory, b[5:]) for b in names[:100]],
                "principal": memory.identity.principal,
                "truncated": len(names) > 100,
            }

    @app.post("/api/repositories/{project}/teams", status_code=201)
    def team_create(project: str, body: TeamInput):
        project_ready(project)
        with lock:
            return team.create(state.config(project), body.name)

    @app.post("/api/repositories/{project}/teams/{name}/members")
    def team_membership(project: str, name: str, body: MembershipInput):
        project_ready(project)
        with lock:
            return team.membership(
                state.config(project),
                name,
                body.principal,
                body.role,
                body.expected_role,
                body.reason,
            )

    @app.get("/api/repositories/{project}/teams/{name}/memories")
    def team_memories(project: str, name: str, member: str = ""):
        project_ready(project)
        with lock, personal.catalog(state.config(project)) as (memory, _):
            info = team.team_info(memory, name)
            if member and member not in {m["principal"] for m in info["members"]}:
                raise KeyError("Unknown member")
            reviewer = info["role"] == "reviewer"
            records = memory.db.execute(
                "SELECT uid,text,state,hash,author,sources,expires FROM records WHERE tenant=? AND brain=? "
                "AND state!='deleted' AND (expires='' OR expires>?) "
                "AND (state='accepted' OR author=? OR ?) AND (?='' OR author=?) ORDER BY rowid DESC LIMIT 101",
                (
                    memory.identity.tenant,
                    team.scope(name),
                    personal.now(),
                    memory.identity.principal,
                    reviewer,
                    member,
                    member,
                ),
            ).fetchall()
            return {
                "items": [{**dict(r), "sources": json.loads(r["sources"])} for r in records[:100]],
                "truncated": len(records) > 100,
                "team": info,
                "binding": False,
            }

    @app.get("/api/repositories/{project}/teams/{name}/graph")
    def team_graph(project: str, name: str, member: str = ""):
        project_ready(project)
        cfg = state.config(project)
        with lock, personal.catalog(cfg) as (memory, projection):
            info = team.team_info(memory, name)
            if member and member not in {m["principal"] for m in info["members"]}:
                raise KeyError("Unknown member")
            return team.graph(
                cfg, memory, projection, [team.scope(name)], include_proposals=True, member=member
            )

    @app.post("/api/repositories/{project}/teams/{name}/refresh")
    def team_refresh(project: str, name: str):
        project_ready(project)
        with lock, personal.catalog(state.config(project)) as (memory, projection):
            memory.authorize(team.scope(name), review=True)
            return team.refresh(memory, projection, name)

    @app.post("/api/repositories/{project}/teams/{name}/share", status_code=201)
    def team_share(project: str, name: str, body: ShareInput):
        project_ready(project)
        with lock:
            return team.share(
                state.config(project), name, body.uid, body.expected_hash, body.expected_target
            )

    @app.get("/api/repositories/{project}/teams/{name}/memories/{uid}")
    def team_detail(project: str, name: str, uid: str):
        project_ready(project)
        cfg = state.config(project)
        with lock, personal.catalog(cfg) as (memory, _):
            r = team.record(memory, name, uid)
            try:
                source, error = team.source_details(cfg, memory, r), None
            except (OSError, ValueError):
                source, error = (
                    None,
                    "Selected shared source unavailable or changed; acceptance is blocked.",
                )
            events = memory.db.execute(
                "SELECT actor,action,at,detail FROM events WHERE tenant=? AND brain=? AND uid=? "
                "AND action IN ('accept','reject','rollback') ORDER BY rowid DESC LIMIT 30",
                (memory.identity.tenant, team.scope(name), uid),
            ).fetchall()
            return {
                "uid": uid,
                "text": r["text"],
                "hash": r["hash"],
                "state": r["state"],
                "author": r["author"],
                "source": source,
                "source_error": error,
                "reviews": [dict(e) for e in events],
                "binding": False,
            }

    @app.post("/api/repositories/{project}/teams/{name}/memories/{uid}/review")
    def team_review(project: str, name: str, uid: str, body: MemoryReviewInput):
        project_ready(project)
        with lock:
            return team.review(
                state.config(project),
                name,
                uid,
                body.expected_hash,
                body.expected_state,
                body.action,
                body.reason,
            )

    @app.get("/api/repositories/{project}/graph")
    def graph(project: str, query: str = ""):
        project_ready(project)
        if len(query) > 100:
            raise ValueError("Use a shorter graph filter")
        store = GraphStore(state.config(project))
        sha = ready(store)
        nodes = store.query(
            "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) AND NOT n:Source "
            "AND ($q='' OR toLower(coalesce(n.path,n.qualname,n.title,n.uid)) CONTAINS toLower($q)) "
            "RETURN n.uid AS uid ORDER BY uid LIMIT 151",
            {"repo": store.cfg.repo_id, "q": query},
        )
        result = native_graph(store, [n["uid"] for n in nodes[:150]])
        truncated = len(nodes) > 150 or len(result["edges"]) > 300
        result["edges"] = result["edges"][:300]
        return {
            **result,
            "revision": sha,
            "truncated": truncated,
            "limits": {"nodes": 150, "edges": 300},
        }

    @app.post("/api/repositories/{project}/documents")
    def upload(project: str, body: DocumentInput):
        project_ready(project)
        with lock:
            if (
                active_ingestions(state, project)
                or active_actions(state, project)
                or any(
                    t["status"] in {"queued", "running"}
                    for s in state.list("session", project)
                    for t in state.list("turn", s["id"])
                )
            ):
                raise HTTPException(
                    409, "Wait for the current investigation before changing sources"
                )
            if (body.text is None) == (body.data_base64 is None):
                raise ValueError("Supply either text or base64 file bytes")
            if body.data_base64 is not None:
                import base64
                import binascii

                try:
                    raw = base64.b64decode(body.data_base64, validate=True)
                except (ValueError, binascii.Error):
                    raise ValueError("Invalid base64 file data") from None
                return upload_binary(state, project, body.filename, raw)
            return upload_document(state, project, body.filename, body.text)

    @app.get("/api/repositories/{project}/documents")
    def documents(project: str):
        project_ready(project)
        store = GraphStore(state.config(project))
        sha = ready(store)
        return store.query(
            "MATCH (d:Document {repo_id:$repo,revision:$sha,current:true})-[:SUPPORTS]->(s:Source) "
            "WHERE d.source_kind IN ['repository_document','app_upload','app_binary_upload'] "
            "RETURN s.uid AS id,d.path AS path,d.line_start AS start,d.line_end AS end "
            "ORDER BY path,start LIMIT 201",
            {"repo": store.cfg.repo_id, "sha": sha},
        )

    @app.get("/api/repositories/{project}/enrichments")
    def enrichments(project: str):
        state.get(project, "repository")
        return state.list("enrichment", project)

    @app.post("/api/repositories/{project}/enrichments", status_code=202)
    def enrich(project: str, body: EnrichmentInput):
        project_ready(project)
        if body.engine not in {"graphify", "sdk"} or len(set(body.sources)) != len(body.sources):
            raise ValueError("Choose Graphify or FalkorDB SDK and unique source sections")
        available = {d["id"] for d in documents(project)}
        if not set(body.sources) <= available:
            raise ValueError("Select current document source sections")
        with lock:
            if (
                active_ingestions(state, project)
                or active_actions(state, project)
                or any(
                    t["status"] in {"queued", "running"}
                    for s in state.list("session", project)
                    for t in state.list("turn", s["id"])
                )
            ):
                raise HTTPException(409, "Finish the active investigation, plan or ingestion first")
            if len(state.list("enrichment", project)) >= 40:
                raise HTTPException(409, "Local semantic ingestion history limit reached")
            job = state.create(
                "enrichment",
                project,
                project=project,
                engine=body.engine,
                sources=body.sources,
                model=state.model,
                status="queued",
                stage="Semantic extraction queued",
            )
            workers.submit(run_enrichment, state, job["id"])
        return job

    @app.get("/api/repositories/{project}/sessions")
    def sessions(project: str):
        state.get(project, "repository")
        return state.list("session", project)

    @app.post("/api/repositories/{project}/sessions", status_code=201)
    def new_session(project: str):
        project_ready(project)
        return state.create("session", project, project=project, title="New conversation")

    @app.get("/api/sessions/{session}/turns")
    def turns(session: str):
        state.get(session, "session")
        return state.list("turn", session)

    @app.post("/api/sessions/{session}/turns", status_code=202)
    def question(session: str, body: QuestionInput):
        chat = state.get(session, "session")
        project_ready(chat["project"])
        if not body.question.strip():
            raise ValueError("Enter a question")
        with lock:
            if (
                active_ingestions(state, chat["project"])
                or any(
                    a["status"] in {"queued", "running"}
                    for a in active_actions(state, chat["project"])
                )
                or any(
                    t["status"] in {"queued", "running"}
                    for s in state.list("session", chat["project"])
                    for t in state.list("turn", s["id"])
                )
            ):
                raise HTTPException(409, "Wait for the current investigation")
            turn = state.create(
                "turn",
                session,
                project=chat["project"],
                question=body.question,
                status="queued",
                stage="Queued",
            )
            state.update(session, title=body.question[:60])
            workers.submit(run_turn, state, chat["project"], session, turn["id"])
        return turn

    @app.get("/api/turns/{turn}/evidence/{evidence_id}")
    def citation(turn: str, evidence_id: str):
        import re

        if not re.fullmatch("[a-f0-9]{24}", evidence_id):
            raise HTTPException(404, "Unknown citation")
        value = state.get(turn, "turn")
        if value["status"] != "complete" or not any(
            s["evidence_id"] == evidence_id for c in value["claims"] for s in c["support"]
        ):
            raise HTTPException(404, "Citation is not part of this answer")
        project_ready(value["project"])
        path = (
            state.folder(value["project"]) / "turns" / turn / "evidence" / (evidence_id + ".json")
        )
        saved = json.loads(path.read_text(encoding="utf-8"))
        checked = resolve(GraphStore(state.config(value["project"])), saved)
        if checked["digest"] != saved["digest"] or checked["graph"] != saved["graph"]:
            raise HTTPException(409, "Cited evidence changed; ask again")
        return {"id": evidence_id, **checked}

    @app.get("/api/turns/{turn}/actions")
    def turn_actions(turn: str):
        value = state.get(turn, "turn")
        return [
            {key: action.get(key) for key in ("id", "status", "stage", "turn")}
            for action in state.list("action", value["project"])
            if action["turn"] == turn
        ]

    @app.post("/api/turns/{turn}/actions", status_code=202)
    def propose_action(turn: str, body: QuestionInput):
        value = state.get(turn, "turn")
        project = value["project"]
        project_ready(project)
        if value["status"] != "complete" or not body.question.strip():
            raise HTTPException(409, "Complete the investigation before requesting a plan")
        with lock:
            if (
                active_ingestions(state, project)
                or active_actions(state, project)
                or any(
                    t["status"] in {"queued", "running"}
                    for chat in state.list("session", project)
                    for t in state.list("turn", chat["id"])
                )
            ):
                raise HTTPException(409, "Finish or reject the active plan/investigation first")
            if len(state.list("action", project)) >= 20:
                raise HTTPException(409, "Local action history limit is 20 plans per repository")
            action = state.create(
                "action",
                project,
                project=project,
                turn=turn,
                objective=body.question,
                status="queued",
                phase="planning",
                stage="Plan queued",
            )
            workers.submit(prepare_plan, state, action["id"])
        return action

    @app.get("/api/actions/{action_id}")
    def action_detail(action_id: str):
        return state.get(action_id, "action")

    @app.post("/api/actions/{action_id}/approve", status_code=202)
    def approve_action(action_id: str, body: ApprovalInput):
        with lock:
            action = state.get(action_id, "action")
            project_ready(action["project"])
            if active_ingestions(state, action["project"]):
                raise HTTPException(409, "Wait for semantic ingestion before approving execution")
            if any(
                t["status"] in {"queued", "running"}
                for chat in state.list("session", action["project"])
                for t in state.list("turn", chat["id"])
            ):
                raise HTTPException(409, "Wait for the investigation before approving execution")
            result = approve(state, action_id, body.plan_digest)
            workers.submit(execute, state, action_id)
        return result

    @app.post("/api/actions/{action_id}/reject")
    def reject_action(action_id: str):
        if not state.transition(
            action_id,
            {"status": "awaiting_approval"},
            status="rejected",
            stage="Plan rejected; no execution",
        ):
            raise HTTPException(409, "Only a plan awaiting review can be rejected")
        return state.get(action_id, "action")

    @app.get("/api/actions/{action_id}/evidence/{evidence_id}")
    def action_citation(action_id: str, evidence_id: str):
        import re

        value = state.get(action_id, "action")
        if not re.fullmatch("[a-f0-9]{24}", evidence_id) or not any(
            s["evidence_id"] == evidence_id for c in value.get("claims", []) for s in c["support"]
        ):
            raise HTTPException(404, "Citation is not part of this plan")
        checked_action(state, value)
        path = (
            state.folder(value["project"])
            / "actions"
            / action_id
            / "plan"
            / "evidence"
            / (evidence_id + ".json")
        )
        saved = json.loads(path.read_text(encoding="utf-8"))
        return {"id": evidence_id, **resolve(GraphStore(state.config(value["project"])), saved)}

    assets = Path(assets) if assets else Path(__file__).parents[1] / "web" / "app"
    if (assets / "assets").is_dir() and (assets / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=assets / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(assets / "index.html")
    else:

        @app.get("/")
        def index():
            return JSONResponse(
                {"detail": "Build the React client: cd frontend && npm ci && npm run build"},
                status_code=503,
            )

    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Connection configuration for the operator-owned FalkorDB server",
    )
    parser.add_argument(
        "--data", type=Path, required=True, help="Ignored local application storage directory"
    )
    parser.add_argument(
        "--model", required=True, help="Explicit Codex model; chat consumes existing account usage"
    )
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    origin = f"http://127.0.0.1:{args.port}"
    state = State(args.data, load_config(args.config), args.model)
    print("Open locally: " + origin + "/#" + token, flush=True)
    app = create_app(state, token, origin)
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        app.state.workers.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    main()
