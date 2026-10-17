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
from pydantic import BaseModel, Field

from ..config import load_config
from ..graph import GraphStore, GraphUnavailable
from .actions import active_actions, approve, checked_action, execute, prepare_plan
from .agent import run_turn
from .evidence import native_graph, ready, resolve
from .sources import onboard, repository_url, upload_document
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
    text: str = Field(min_length=1, max_length=500000)


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
                "markdown_rst_upload",
                "company_chat",
                "source_inspection",
                "approved_isolated_patch_tests",
            ],
            "deferred": ["personal_team_controls", "pdf"],
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
            if active_actions(state, project) or any(
                t["status"] in {"queued", "running"}
                for s in state.list("session", project)
                for t in state.list("turn", s["id"])
            ):
                raise HTTPException(
                    409, "Wait for the current investigation before changing sources"
                )
            return upload_document(state, project, body.filename, body.text)

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
            if any(
                a["status"] in {"queued", "running"} for a in active_actions(state, chat["project"])
            ) or any(
                t["status"] in {"queued", "running"}
                for s in state.list("session", chat["project"])
                for t in state.list("turn", s["id"])
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
            if active_actions(state, project) or any(
                t["status"] in {"queued", "running"}
                for chat in state.list("session", project)
                for t in state.list("turn", chat["id"])
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
