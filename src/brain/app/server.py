"""Loopback-only FastAPI application for one trusted local operator."""

import argparse
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..config import load_config
from ..graph import GraphStore, GraphUnavailable
from . import exchange, github_actions, personal, team
from .actions import (
    active_actions,
    approve,
    checked_action,
    execute,
    plan_folder,
    prepare_plan,
    resume_execution,
)
from .agent import run_turn
from .enrichment import active_ingestions, run_document_enrichment, run_enrichment
from .evidence import canonical_graph, native_graph, ready, resolve
from .sources import onboard, repository_url, upload_binary, upload_document
from .state import State
from .streaming import snapshots


class TransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str = Field(min_length=32, max_length=32)
    records: list[str] = Field(min_length=1, max_length=10)
    consent_digest: str = Field(default="", pattern="^(?:[a-f0-9]{64})?$")


class CompanyBridgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class RepositoryInput(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    history: bool = True
    history_required: bool = False


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


class GitHubDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["issue", "pull_request", "comment"]
    title: str = Field(default="", max_length=256)
    body: str = Field(min_length=1, max_length=60000)
    number: int | None = Field(default=None, ge=1, le=1_000_000_000)
    head: str = Field(default="", max_length=200)
    base: str = Field(default="", max_length=200)


class GitHubPublishInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent_digest: str = Field(pattern="^[a-f0-9]{64}$")


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


class ExchangeExport(PersonalInput):
    selections: dict[str, str] = Field(min_length=1, max_length=50)
    collection: str = Field(pattern="^[A-Za-z0-9_-]{1,64}$")
    links: list[str] = Field(default_factory=list, max_length=100)
    expected_digest: str = Field(default="", pattern="^(?:[a-f0-9]{64})?$")


class ExchangeImport(PersonalInput):
    text: str = Field(min_length=1, max_length=1000000)
    consent_digest: str = Field(default="", pattern="^(?:[a-f0-9]{64})?$")


class LinkReview(PersonalInput):
    expected_state: str
    action: str
    reason: str = Field(min_length=1, max_length=1000)


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
                "selected_abhi_exchange",
                "reviewed_lesson_recall",
                "source_inspection",
                "approved_isolated_patch_tests",
                "reviewed_github_issues_pull_requests_comments",
            ],
            "deferred": ["hosted_identity"],
        }

    @app.get("/api/repositories")
    def repositories():
        return state.list("repository")

    @app.get("/api/github/connection")
    def github_connection():
        return github_actions.connection()

    @app.get("/api/repositories/{project}/github/actions")
    def github_history(project: str):
        state.get(project, "repository")
        return {"items": state.list("github_action", project)[-20:]}

    @app.post("/api/repositories/{project}/github/actions", status_code=201)
    def github_draft(project: str, body: GitHubDraftInput):
        project_ready(project)
        return github_actions.preview(state, project, body.model_dump())

    @app.post("/api/repositories/{project}/github/actions/{draft_id}/publish")
    def github_publish(project: str, draft_id: str, body: GitHubPublishInput):
        project_ready(project)
        return github_actions.publish(state, project, draft_id, body.consent_digest)

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
            workers.submit(onboard, state, project["id"], body.history, body.history_required)
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
                "company_enabled": personal.company_enabled(memory),
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
            view = projection.read(
                [personal.brain(memory)],
                include_proposals=True,
                include_company=personal.company_enabled(memory),
            )
            return {
                "status": view["status"],
                "graph": personal.graph_view(view),
                "warnings": view["warnings"],
            }

    @app.post("/api/repositories/{project}/memory/transfers/preview")
    def transfer_preview(project: str, body: TransferInput):
        from .transfers import preview

        with lock:
            return preview(state, project, body.origin, body.records)

    @app.post("/api/repositories/{project}/memory/transfers")
    def transfer_import(project: str, body: TransferInput):
        from .transfers import import_selected

        with lock:
            return import_selected(state, project, body.origin, body.records, body.consent_digest)

    @app.post("/api/repositories/{project}/memory/company-bridge")
    def company_bridge(project: str, body: CompanyBridgeInput):
        project_ready(project)
        with lock:
            return personal.connect_company(state.config(project), body.enabled)

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

    @app.post("/api/repositories/{project}/teams/{name}/abhi/export")
    def abhi_export(project: str, name: str, body: ExchangeExport):
        project_ready(project)
        with lock:
            return exchange.export(
                state.config(project),
                name,
                body.selections,
                body.collection,
                body.links,
                body.expected_digest,
            )

    @app.post("/api/repositories/{project}/teams/{name}/abhi/preview")
    def abhi_preview(project: str, name: str, body: ExchangeImport):
        project_ready(project)
        with lock:
            return exchange.preview_import(state.config(project), name, body.text)

    @app.post("/api/repositories/{project}/teams/{name}/abhi/import", status_code=201)
    def abhi_import(project: str, name: str, body: ExchangeImport):
        project_ready(project)
        with lock:
            return exchange.apply_import(
                state.config(project), name, body.text, body.consent_digest
            )

    @app.get("/api/repositories/{project}/teams/{name}/relationships")
    def team_relationships(project: str, name: str):
        project_ready(project)
        with lock:
            return exchange.relationships(state.config(project), name)

    @app.post("/api/repositories/{project}/teams/{name}/relationships/{uid}/review")
    def team_relationship_review(project: str, name: str, uid: str, body: LinkReview):
        project_ready(project)
        with lock:
            return exchange.review_relationship(
                state.config(project), name, uid, body.expected_state, body.action, body.reason
            )

    @app.get("/api/repositories/{project}/graph")
    def graph(
        project: str,
        query: str = "",
        offset: int = 0,
        kind: str = "",
        folder: str = "",
        context_neighbors: bool = False,
    ):
        from .graph_workspace import FOLDER

        project_ready(project)
        if len(query) > 100 or not 0 <= offset <= 50000 or len(kind) > 64 or len(folder) > 200:
            raise ValueError("Use a shorter graph filter")
        store = GraphStore(state.config(project))
        sha = ready(store)
        nodes = store.query(
            "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) "
            "AND ($kind='' OR $kind IN labels(n)) "
            f"AND ($folder='' OR ({FOLDER})=$folder) "
            "AND ($q='' OR any(value IN [n.path,n.qualname,n.title,n.name,n.uid,n.uri,n.source_kind] WHERE toLower(coalesce(value,'')) CONTAINS toLower($q))) "
            "WITH n, CASE WHEN n:Project THEN 0 WHEN n:File THEN 1 WHEN n:Symbol THEN 2 WHEN n:Document THEN 3 ELSE 4 END AS rank "
            "RETURN n.uid AS uid ORDER BY rank,uid SKIP $offset LIMIT 101",
            {
                "repo": store.cfg.repo_id,
                "q": query,
                "offset": offset,
                "kind": kind,
                "folder": folder,
            },
        )
        roots = [n["uid"] for n in nodes[:100]]
        sources = store.query(
            "MATCH (d:Document {repo_id:$repo})-[:SUPPORTS]->(s:Source {repo_id:$repo}) "
            "WHERE d.uid IN $roots RETURN DISTINCT s.uid AS uid ORDER BY uid LIMIT 51",
            {"repo": store.cfg.repo_id, "roots": roots},
        )
        context = []
        if context_neighbors and (kind or folder):
            context = store.query(
                "MATCH (n {repo_id:$repo})-[]-(m {repo_id:$repo}) "
                "WHERE n.uid IN $roots AND coalesce(n.current,true) "
                "AND coalesce(m.current,true) AND NOT m.uid IN $roots "
                "WITH DISTINCT m "
                "WITH m, CASE WHEN m:Project THEN 0 WHEN m:Symbol THEN 1 "
                "WHEN m:Document THEN 2 WHEN m:Source THEN 3 ELSE 4 END AS rank "
                "RETURN m.uid AS uid ORDER BY rank,uid LIMIT 51",
                {"repo": store.cfg.repo_id, "roots": roots},
            )
        result = native_graph(
            store, [*roots, *[n["uid"] for n in sources[:50]], *[n["uid"] for n in context[:50]]]
        )
        truncated = (
            len(nodes) > 100 or len(sources) > 50 or len(context) > 50 or len(result["edges"]) > 300
        )
        result["edges"] = result["edges"][:300]
        return {
            **result,
            "revision": sha,
            "root_count": len(roots),
            "context_count": len(context[:50]),
            "context_truncated": len(context) > 50,
            "offset": offset,
            "next_offset": offset + 100 if len(nodes) > 100 and offset < 50000 else None,
            "paging_bound_reached": len(nodes) > 100 and offset >= 50000,
            "counts": store.query(
                "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) "
                "RETURN labels(n)[0] AS kind,count(n) AS count ORDER BY kind",
                {"repo": store.cfg.repo_id},
            ),
            "entity_counts": store.query(
                "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) "
                "WITH CASE WHEN n:Document AND n.source_kind='graphify_structural' THEN 'CodeEntity' "
                "WHEN n:Document AND n.source_kind='repository_document' THEN 'RepositorySection' "
                "WHEN n:Document AND n.source_kind IN ['app_upload','app_binary_upload'] THEN 'UploadedSection' "
                "WHEN n:Document AND n.source_kind='semantic_advisory' THEN 'ExtractedConcept' "
                "WHEN n:Document THEN 'OtherEntity' ELSE labels(n)[0] END AS kind "
                "RETURN kind,count(*) AS count ORDER BY kind",
                {"repo": store.cfg.repo_id},
            ),
            "truncated": truncated,
            "limits": {"nodes": 150, "edges": 300, "roots": 100, "source_neighbors": 50},
        }

    @app.get("/api/repositories/{project}/graph/overview")
    def graph_overview(project: str, grouping: str = "type"):
        from .graph_workspace import overview

        project_ready(project)
        return overview(GraphStore(state.config(project)), grouping)

    @app.get("/api/repositories/{project}/graph/node")
    def graph_node(project: str, uid: str):
        from .graph_workspace import inspect_node

        project_ready(project)
        if not 1 <= len(uid) <= 2000:
            raise ValueError("Choose a bounded entity identifier")
        return inspect_node(GraphStore(state.config(project)), uid)

    @app.get("/api/repositories/{project}/graph/neighbors")
    def graph_neighbors(project: str, uid: str, offset: int = 0):
        project_ready(project)
        if not 1 <= len(uid) <= 2000 or not 0 <= offset <= 5000:
            raise HTTPException(400, "Invalid node or neighbor page")
        store = GraphStore(state.config(project))
        ready(store)
        params = {"repo": store.cfg.repo_id, "uid": uid, "offset": offset}
        root = store.query(
            "MATCH (n {repo_id:$repo,uid:$uid}) WHERE coalesce(n.current,true) RETURN n.uid AS uid LIMIT 1",
            params,
        )
        if not root:
            raise HTTPException(404, "Current repository node unavailable")
        rows = store.query(
            "MATCH (n {repo_id:$repo,uid:$uid})-[r]-(m {repo_id:$repo}) WHERE coalesce(m.current,true) RETURN DISTINCT m.uid AS uid ORDER BY uid SKIP $offset LIMIT 51",
            params,
        )
        graph = native_graph(store, [uid, *[r["uid"] for r in rows[:50]]])
        return {
            **graph,
            "edges": graph["edges"][:300],
            "root": uid,
            "next_offset": offset + 50 if len(rows) > 50 and offset < 5000 else None,
            "paging_bound_reached": len(rows) > 50 and offset >= 5000,
            "truncated": len(rows) > 50 or len(graph["edges"]) > 300,
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
                receipt = upload_binary(state, project, body.filename, raw)
            else:
                receipt = upload_document(state, project, body.filename, body.text)
            job = state.create(
                "enrichment",
                project,
                project=project,
                engine="graphify",
                sources=receipt.pop("source_ids"),
                model=state.model,
                status="queued",
                stage="Document saved; Graphify extraction queued",
            )
            workers.submit(run_document_enrichment, state, job["id"])
            return {**receipt, "enrichment": job}

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
        from .activity import investigation_progress

        return [
            {**t, "progress": investigation_progress(state, t)} for t in state.list("turn", session)
        ]

    def event_stream(request, snapshot, *, terminal=False):
        return StreamingResponse(
            snapshots(request, snapshot, terminal=terminal),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
        )

    @app.get("/api/sessions/{session}/events")
    def session_events(session: str, request: Request):
        state.get(session, "session")
        return event_stream(request, lambda: turns(session))

    @app.get("/api/turns/{turn}/events")
    def turn_events(turn: str, request: Request):
        state.get(turn, "turn")
        from .activity import investigation_progress

        def snapshot():
            value = state.get(turn, "turn")
            return {**value, "progress": investigation_progress(state, value)}

        return event_stream(request, snapshot, terminal=True)

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
        if checked["digest"] != saved["digest"] or canonical_graph(
            checked["graph"]
        ) != canonical_graph(saved["graph"]):
            raise HTTPException(409, "Cited evidence changed; ask again")
        return {"id": evidence_id, **checked}

    @app.get("/api/repositories/{project}/actions")
    def repository_actions(project: str):
        from .actions import verification_result

        state.get(project, "repository")
        items = []
        for action in state.list("action", project):
            turn = state.get(action["turn"], "turn")
            with state.connect() as db:
                parent = db.execute(
                    "SELECT parent FROM objects WHERE id=? AND kind='turn'", (turn["id"],)
                ).fetchone()
            items.append(
                {
                    **{
                        k: action.get(k)
                        for k in ("id", "turn", "status", "phase", "stage", "objective")
                    },
                    **verification_result(action),
                    "title": (action.get("plan") or {}).get("summary") or turn["question"],
                    "question": turn["question"],
                    "session": parent["parent"] if parent else None,
                }
            )
        with state.connect() as db:
            rows = db.execute(
                "SELECT t.body,t.parent FROM objects t JOIN objects s ON t.parent=s.id WHERE t.kind='turn' AND s.kind='session' AND s.parent=? ORDER BY t.rowid DESC LIMIT 21",
                (project,),
            ).fetchall()
        investigations = []
        for row in rows[:20]:
            t = json.loads(row["body"])
            investigations.append(
                {
                    "id": t["id"],
                    "turn": t["id"],
                    "session": row["parent"],
                    "question": t["question"],
                    "objective": t["question"],
                    "status": t["status"],
                    "stage": t.get("stage"),
                    "run_kind": "investigation",
                }
            )
        return {
            "items": items[-20:],
            "truncated": len(items) > 20,
            "investigations": investigations,
            "investigations_truncated": len(rows) > 20,
        }

    @app.get("/api/repositories/{project}/runs/{run_id}")
    def repository_run(project: str, run_id: str):
        from .activity import investigation_progress

        state.get(project, "repository")
        with state.connect() as db:
            row = db.execute(
                "SELECT kind,parent,body FROM objects WHERE id=? AND kind IN ('action','turn')",
                (run_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Run not found in this repository")
            value = json.loads(row["body"])
            if row["kind"] == "action":
                if row["parent"] != project:
                    raise HTTPException(404, "Run not found in this repository")
                turn = state.get(value["turn"], "turn")
                parent = db.execute(
                    "SELECT parent FROM objects WHERE id=? AND kind='turn'", (turn["id"],)
                ).fetchone()
                session_id = parent["parent"] if parent else None
            else:
                turn = value
                session_id = row["parent"]
            session_row = db.execute(
                "SELECT parent FROM objects WHERE id=? AND kind='session'", (session_id,)
            ).fetchone()
        if session_row is None or session_row["parent"] != project:
            raise HTTPException(404, "Run not found in this repository")
        if row["kind"] == "turn":
            return {
                "id": turn["id"],
                "turn": turn["id"],
                "session": session_id,
                "question": turn["question"],
                "objective": turn["question"],
                "status": turn["status"],
                "stage": turn.get("stage"),
                "run_kind": "investigation",
                "investigation": {**turn, "progress": investigation_progress(state, turn)},
            }
        return {
            **{k: value.get(k) for k in ("id", "turn", "status", "phase", "stage", "objective")},
            "question": turn["question"],
            "session": session_id,
        }

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
        value = state.get(action_id, "action")
        from .actions import action_progress, live_changes, verification_result

        return {
            **value,
            **verification_result(value),
            "progress": action_progress(state, value),
            "live_changes": live_changes(state, value),
        }

    @app.get("/api/actions/{action_id}/events")
    def action_events(action_id: str, request: Request):
        state.get(action_id, "action")
        return event_stream(request, lambda: action_detail(action_id), terminal=True)

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

    @app.post("/api/actions/{action_id}/resume", status_code=202)
    def resume_action(action_id: str, body: ApprovalInput):
        with lock:
            action = state.get(action_id, "action")
            project = action["project"]
            project_ready(project)
            if (
                active_ingestions(state, project)
                or active_actions(state, project)
                or any(
                    t["status"] in {"queued", "running"}
                    for chat in state.list("session", project)
                    for t in state.list("turn", chat["id"])
                )
            ):
                raise HTTPException(409, "Finish active repository work before resuming")
            result = resume_execution(state, action_id, body.plan_digest)
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
        value = state.get(action_id, "action")
        from .actions import verification_result

        return {**value, **verification_result(value)}

    @app.get("/api/actions/{action_id}/evidence/{evidence_id}")
    def action_citation(action_id: str, evidence_id: str):
        import re

        value = state.get(action_id, "action")
        if not re.fullmatch("[a-f0-9]{24}", evidence_id) or not any(
            s["evidence_id"] == evidence_id for c in value.get("claims", []) for s in c["support"]
        ):
            raise HTTPException(404, "Citation is not part of this plan")
        checked_action(state, value)
        path = plan_folder(state, value) / "evidence" / (evidence_id + ".json")
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
