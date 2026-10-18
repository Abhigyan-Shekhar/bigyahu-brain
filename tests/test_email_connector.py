"""Email intent, one-shot delivery, SMTP isolation and truthful outcomes."""

import json
import smtplib
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from brain.app import email_connector as mail
from brain.app.server import create_app
from brain.app.state import State
from brain.config import Config


@pytest.fixture
def configured(tmp_path, monkeypatch):
    path = tmp_path / "smtp.json"
    cfg = {
        "sender": "sender@example.com",
        "host": "smtp.example.com",
        "port": 465,
        "security": "ssl",
        "username": "sender@example.com",
        "password": "fixture-password",
    }
    path.write_text(json.dumps(cfg))
    path.chmod(0o600)
    monkeypatch.setenv("BRAIN_EMAIL_CONFIG", str(path))
    state = State(tmp_path / "app", Config(tmp_path, "fixture"), "fixture-model")
    repo = state.create(
        "repository",
        name="example/project",
        url="https://github.com/example/project",
        status="ready",
    )
    turn = state.create(
        "turn",
        project=repo["id"],
        status="complete",
        question="Why do jobs stop?",
        claims=[{"text": "The queue lives in memory."}],
        limitations=["Provider recovery unverified"],
    )
    return state, repo["id"], turn["id"], cfg, path


class SMTPFixture:
    def __init__(self, failure=None, refusal=None):
        self.sent = []
        self.closed = False
        self.failure = failure
        self.refusal = refusal

    def send_message(self, message, **kwargs):
        self.sent.append((message, kwargs))
        if self.failure:
            raise self.failure
        return self.refusal or {}

    def close(self):
        self.closed = True


def enqueue(configured, *, purpose="", turn=True, request_id=None):
    state, project, turn_id, *_ = configured
    return mail.enqueue(
        state,
        project,
        "colleague@example.com",
        purpose,
        turn_id if turn else None,
        request_id or str(uuid4()),
    )


def test_generation_and_send_keep_user_recipient_and_truthful_receipt(configured, monkeypatch):
    state, _, _, cfg, _ = configured
    prompts, smtp = [], SMTPFixture()

    def extract(prompt, schema, model):
        prompts.append(prompt)
        assert cfg["password"] not in prompt
        assert "The queue lives in memory." in prompt and "Provider recovery unverified" in prompt
        assert model == "fixture-model"
        return {
            "subject": "Queue recovery discussion",
            "body": "Hi,\nCould you clarify persistence requirements?",
        }

    monkeypatch.setattr(mail, "structured_extract", extract)
    monkeypatch.setattr(mail, "connect", lambda *_: smtp)
    job, created = enqueue(configured)
    assert created
    mail.run_email(state, job["id"])
    result = state.get(job["id"])
    assert result["status"] == "sent" and "Inbox delivery is not confirmed" in result["notice"]
    assert len(prompts) == len(smtp.sent) == 1 and smtp.closed
    message, envelope = smtp.sent[0]
    assert message["To"] == "colleague@example.com" and message["From"] == cfg["sender"]
    assert envelope == {"from_addr": cfg["sender"], "to_addrs": ["colleague@example.com"]}
    assert message["Message-ID"] == result["message_id"]
    assert cfg["password"] not in json.dumps(result)
    assert "context" not in mail.public(result) and "connection_identity" not in mail.public(result)


def test_concurrent_requests_and_workers_never_duplicate_email(configured, monkeypatch):
    state, *_ = configured
    request_id, smtp = str(uuid4()), SMTPFixture()
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: enqueue(configured, request_id=request_id), range(4)))
    assert sum(created for _, created in jobs) == 1
    assert len({job["id"] for job, _ in jobs}) == 1
    monkeypatch.setattr(
        mail, "generate", lambda *_: {"subject": "Project discussion", "body": "Question"}
    )
    monkeypatch.setattr(mail, "connect", lambda *_: smtp)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: mail.run_email(state, jobs[0][0]["id"]), range(4)))
    assert len(smtp.sent) == 1
    assert enqueue(configured, request_id=request_id)[0]["status"] == "sent"


def test_idempotency_key_cannot_change_recipient_or_purpose(configured):
    state, project, turn_id, *_ = configured
    request_id = str(uuid4())
    enqueue(configured, request_id=request_id)
    with pytest.raises(ValueError, match="request changed"):
        mail.enqueue(state, project, "other@example.com", "", turn_id, request_id)


@pytest.mark.parametrize(
    "recipient",
    [
        "a@example.com,b@example.com",
        "User <a@example.com>",
        "a@example.com\r\nBcc: x@example.com",
        "bad",
        "a..b@example.com",
    ],
)
def test_single_recipient_blocks_header_injection(recipient):
    with pytest.raises(ValueError):
        mail.address(recipient)


@pytest.mark.parametrize("change", ["cross_project", "running", "missing_context"])
def test_email_uses_only_selected_completed_project_context(configured, change):
    state, project, turn_id, *_ = configured
    if change == "cross_project":
        state.update(turn_id, project="another-project")
    if change == "running":
        state.update(turn_id, status="running")
    with pytest.raises(ValueError):
        mail.enqueue(
            state,
            project,
            "recipient@example.com",
            "",
            None if change == "missing_context" else turn_id,
            str(uuid4()),
        )
    assert state.list("email", project) == []


@pytest.mark.parametrize(
    "subject", ["Bad\nBcc: x@example.com", "", "x" * 201, "Bad\rSubject", "Bad\0header"]
)
def test_generated_headers_are_validated_before_smtp(configured, monkeypatch, subject):
    state, *_ = configured
    monkeypatch.setattr(
        mail, "structured_extract", lambda *_: {"subject": subject, "body": "Details"}
    )
    monkeypatch.setattr(mail, "connect", lambda *_: pytest.fail("Invalid output reached SMTP"))
    job, _ = enqueue(configured)
    mail.run_email(state, job["id"])
    assert state.get(job["id"])["status"] == "failed"


def test_generation_failure_never_opens_smtp(configured, monkeypatch):
    state, *_ = configured

    def fail(*_):
        raise ValueError("private diagnostics")

    monkeypatch.setattr(mail, "generate", fail)
    monkeypatch.setattr(mail, "connect", lambda *_: pytest.fail("Generation failed before SMTP"))
    job, _ = enqueue(configured)
    mail.run_email(state, job["id"])
    result = state.get(job["id"])
    assert result["status"] == "failed" and "private diagnostics" not in result["error"]


def test_smtp_timeout_after_data_is_unknown_and_not_retried(configured, monkeypatch):
    state, *_ = configured
    smtp = SMTPFixture(failure=TimeoutError("private server diagnostics"))
    monkeypatch.setattr(mail, "generate", lambda *_: {"subject": "Discussion", "body": "Question"})
    monkeypatch.setattr(mail, "connect", lambda *_: smtp)
    job, _ = enqueue(configured)
    mail.run_email(state, job["id"])
    mail.run_email(state, job["id"])
    result = state.get(job["id"])
    assert result["status"] == "unknown" and len(smtp.sent) == 1
    assert "private server diagnostics" not in result["error"] and smtp.closed


def test_provider_rejection_is_not_reported_as_sent(configured, monkeypatch):
    state, *_ = configured
    smtp = SMTPFixture(refusal={"colleague@example.com": (550, b"Rejected")})
    monkeypatch.setattr(mail, "generate", lambda *_: {"subject": "Discussion", "body": "Question"})
    monkeypatch.setattr(mail, "connect", lambda *_: smtp)
    job, _ = enqueue(configured)
    mail.run_email(state, job["id"])
    result = state.get(job["id"])
    assert result["status"] == "failed" and result["stage"] == "Email rejected by provider"


def test_authentication_failure_does_not_attempt_delivery(configured, monkeypatch):
    state, *_ = configured

    def fail(_):
        raise smtplib.SMTPAuthenticationError(535, b"private details")

    monkeypatch.setattr(mail, "generate", lambda *_: {"subject": "Discussion", "body": "Question"})
    monkeypatch.setattr(mail, "connect", fail)
    job, _ = enqueue(configured)
    mail.run_email(state, job["id"])
    result = state.get(job["id"])
    assert result["status"] == "failed" and not result["delivery_started"]
    assert "private details" not in result["error"]


@pytest.mark.parametrize("sending", [False, True])
def test_restart_does_not_resend_interrupted_emails(configured, sending):
    state, *_ = configured
    job, _ = enqueue(configured)
    state.update(job["id"], status="running", delivery_started=sending)
    recovered = State(state.root, state.base, state.model)
    assert recovered.get(job["id"])["status"] == ("unknown" if sending else "failed")


def test_sender_change_stops_send(configured, monkeypatch):
    state, _, _, cfg, path = configured
    job, _ = enqueue(configured)
    path.write_text(json.dumps({**cfg, "sender": "changed@example.com"}))
    monkeypatch.setattr(mail, "generate", lambda *_: {"subject": "Discussion", "body": "Question"})
    monkeypatch.setattr(mail, "connect", lambda *_: pytest.fail("Sender changed"))
    mail.run_email(state, job["id"])
    assert state.get(job["id"])["status"] == "failed"


@pytest.mark.parametrize("security", ["ssl", "starttls"])
def test_smtp_tls_before_login_and_no_message_on_connection_check(
    configured, monkeypatch, security
):
    _, _, _, cfg, path = configured
    cfg["security"] = security
    path.write_text(json.dumps(cfg))
    events = []

    class Client:
        def __init__(self, host, port, **kwargs):
            events.append("connect")
            assert kwargs["timeout"] == 30
            if security == "ssl":
                assert kwargs["context"].check_hostname

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, **kwargs):
            assert kwargs["context"].check_hostname
            events.append("tls")

        def login(self, username, password):
            if security == "starttls":
                assert "tls" in events
            assert password == cfg["password"]
            events.append("login")

        def close(self):
            events.append("close")

    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", Client)
    monkeypatch.setattr(mail.smtplib, "SMTP", Client)
    result = mail.connection(verify=True)
    assert result == {"configured": True, "verified": True, "sender": cfg["sender"]}
    assert events[-2:] == ["login", "close"]


def test_missing_config_and_insecure_file_never_expose_password(configured, monkeypatch):
    _, _, _, cfg, path = configured
    path.chmod(0o644)
    if __import__("os").name != "nt":
        assert not mail.connection()["configured"]
    monkeypatch.delenv("BRAIN_EMAIL_CONFIG")
    assert not mail.connection()["configured"]
    assert cfg["password"] not in str(mail.connection())


def test_api_session_boundary_background_send_and_cross_project_access(configured, monkeypatch):
    state, project, turn_id, _, _ = configured
    smtp = SMTPFixture()
    monkeypatch.setattr(
        mail, "generate", lambda *_: {"subject": "Project question", "body": "Could you review?"}
    )
    monkeypatch.setattr(mail, "connect", lambda *_: smtp)
    app = create_app(state, "token", "http://testserver")
    try:
        with TestClient(app) as client:
            headers = {"Authorization": "Bearer token"}
            route = f"/api/repositories/{project}/emails"
            assert client.get("/api/email/connection").status_code == 401
            response = client.post(
                route,
                headers=headers,
                json={
                    "recipient": "person@example.com",
                    "turn": turn_id,
                    "request_id": str(uuid4()),
                },
            )
            assert response.status_code == 202
            uid = response.json()["id"]
            app.state.workers.shutdown(wait=True)
            result = client.get(route + "/" + uid, headers=headers).json()
            assert result["status"] == "sent" and "context" not in result
            other = state.create(
                "repository", name="other", url="https://github.com/example/other", status="ready"
            )
            assert (
                client.get(
                    f"/api/repositories/{other['id']}/emails/{uid}", headers=headers
                ).status_code
                == 404
            )
            assert len(client.get(route, headers=headers).json()["items"]) == 1
    finally:
        app.state.workers.shutdown(wait=True)
