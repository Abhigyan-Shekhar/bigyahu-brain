"""Durable local jobs, sessions and per-repository configuration."""

import json
import sqlite3
import uuid
from dataclasses import asdict, replace
from pathlib import Path

import yaml

from ..config import load_config


class State:
    def __init__(self, root, base, model, *, recover=True):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.base, self.model = base, model
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS objects (id TEXT PRIMARY KEY, kind TEXT, parent TEXT, body TEXT)"
            )
            for row in db.execute("SELECT id,body FROM objects").fetchall() if recover else []:
                body = json.loads(row["body"])
                if body.get("status") in {"queued", "running"}:
                    body.update(
                        status="unknown" if body.get("delivery_started") else "failed",
                        error="Application stopped during email sending. Check with your provider before sending again."
                        if body.get("delivery_started")
                        else "Application stopped; start a new job to retry.",
                    )
                    db.execute(
                        "UPDATE objects SET body=? WHERE id=?", (json.dumps(body), row["id"])
                    )

    def connect(self):
        db = sqlite3.connect(self.root / "application.db", timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def create(self, object_kind, parent="", **body):
        uid = uuid.uuid4().hex
        value = dict(id=uid, **body)
        with self.connect() as db:
            db.execute(
                "INSERT INTO objects VALUES(?,?,?,?)", (uid, object_kind, parent, json.dumps(value))
            )
        return value

    def get(self, uid, kind=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM objects WHERE id=?", (uid,)).fetchone()
        if row is None or (kind and row["kind"] != kind):
            raise KeyError("Unknown resource")
        return json.loads(row["body"])

    def update(self, uid, **fields):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM objects WHERE id=?", (uid,)).fetchone()
            body = {**json.loads(row["body"]), **fields}
            db.execute("UPDATE objects SET body=? WHERE id=?", (json.dumps(body), uid))
        return body

    def transition(self, uid, expected, **fields):
        """Consume an exact lifecycle state once, including across concurrent HTTP retries."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM objects WHERE id=?", (uid,)).fetchone()
            if row is None:
                raise KeyError("Unknown resource")
            body = json.loads(row["body"])
            if any(body.get(key) != value for key, value in expected.items()):
                return False
            db.execute(
                "UPDATE objects SET body=? WHERE id=?", (json.dumps({**body, **fields}), uid)
            )
        return True

    def list(self, kind, parent=""):
        with self.connect() as db:
            rows = db.execute(
                "SELECT body FROM objects WHERE kind=? AND parent=? ORDER BY rowid", (kind, parent)
            ).fetchall()
        return [json.loads(row["body"]) for row in rows]

    def folder(self, project):
        self.get(project, "repository")
        return self.root / project

    def configure(self, project, url):
        folder = self.folder(project)
        cfg = replace(
            self.base,
            repo_root=folder / "checkout",
            repo_id="app:" + project,
            repo_url=url,
            principal="app_operator",
            tenant_id="app_" + project,
            memory_db=None,
            memory_graph_enabled=False,
            embedding_model_dir=None,
        )
        values = asdict(cfg)
        values["repo_root"] = str(cfg.repo_root)
        (folder / "brain.local.yaml").write_text(yaml.safe_dump(values), encoding="utf-8")
        return cfg

    def config(self, project):
        return load_config(self.folder(project) / "brain.local.yaml")
