"""Reviewed GitHub writes using the local operator's GitHub CLI connection."""

import json
import re
import subprocess
from datetime import UTC, datetime
from urllib.parse import urlsplit

from ..memory import canonical, digest
from .sources import repository_url


class GitHubConnectionError(ValueError):
    """A bounded, credential-free error suitable for the local UI."""


def request(method, endpoint, payload=None):
    argv = [
        "gh",
        "api",
        "--hostname",
        "github.com",
        "--method",
        method,
        endpoint,
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
    ]
    if payload is not None:
        argv += ["--input", "-"]
    try:
        result = subprocess.run(
            argv,
            input=canonical(payload) if payload is not None else None,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitHubConnectionError(
            "GitHub CLI is unavailable or the request timed out. Check gh auth status on the app server."
        ) from exc
    if result.returncode or len(result.stdout.encode()) > 2_000_000:
        raise GitHubConnectionError(
            "GitHub request failed. Check gh auth status, repository permissions and request details."
        )
    try:
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise TypeError("Expected object")
        return value
    except (ValueError, TypeError) as exc:
        raise GitHubConnectionError("GitHub returned an unexpected response") from exc


def connection():
    try:
        user = request("GET", "user")
        login = user.get("login", "")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
            raise GitHubConnectionError("GitHub account identity unavailable")
        return {"connected": True, "login": login}
    except GitHubConnectionError as exc:
        return {
            "connected": False,
            "error": str(exc),
            "setup": "gh auth login --hostname github.com",
        }


def repository(state, project):
    repo = state.get(project, "repository")
    slug = urlsplit(repository_url(repo["url"])).path.strip("/")
    remote = request("GET", "repos/" + slug)
    if remote.get("full_name", "").casefold() != slug.casefold() or not isinstance(
        remote.get("id"), int
    ):
        raise ValueError("GitHub repository identity changed")
    return remote["full_name"], remote


def branch(value, *, head=False):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 200
        or not re.fullmatch(r"[A-Za-z0-9_./:-]+", value)
        or ".." in value
        or "//" in value
        or value.endswith(("/", ".", ".lock"))
        or value.startswith(("/", "-"))
        or (":" in value and not head)
        or value.count(":") > 1
    ):
        raise ValueError("Select a literal existing GitHub branch")
    return value


def preview(state, project, values):
    account = connection()
    if not account["connected"]:
        raise ValueError(account["error"] + " Run " + account["setup"] + " on the app server.")
    slug, remote = repository(state, project)
    kind, body = values.get("kind"), values.get("body", "")
    if not isinstance(body, str) or not body.strip() or len(body) > 60000:
        raise ValueError("Use a nonempty body of at most 60000 characters")
    payload = {"body": body}
    if kind in {"issue", "pull_request"}:
        title = values.get("title", "")
        if not isinstance(title, str) or not title.strip() or len(title) > 256:
            raise ValueError("Use a title of 1 to 256 characters")
        payload["title"] = title
        endpoint = "repos/" + slug + ("/issues" if kind == "issue" else "/pulls")
        if kind == "pull_request":
            payload.update(
                head=branch(values.get("head"), head=True),
                base=branch(values.get("base") or remote.get("default_branch")),
                draft=True,
            )
    elif kind == "comment":
        number = values.get("number")
        if type(number) is not int or not 1 <= number <= 1_000_000_000:
            raise ValueError("Select an issue or pull request number")
        item = request("GET", f"repos/{slug}/issues/{number}")
        if item.get("number") != number:
            raise ValueError("GitHub comment target changed")
        endpoint = f"repos/{slug}/issues/{number}/comments"
    else:
        raise ValueError("Choose an issue, pull request or comment")
    content = {
        "project": project,
        "repository": slug,
        "repository_id": remote["id"],
        "login": account["login"],
        "operation": kind,
        "endpoint": endpoint,
        "payload": payload,
    }
    return state.create(
        "github_action",
        project,
        **content,
        status="draft",
        consent_digest=digest(canonical(content)),
        created_at=datetime.now(UTC).isoformat(),
    )


def publish(state, project, uid, expected_digest):
    draft = state.get(uid, "github_action")
    if draft["project"] != project:
        raise KeyError("Unknown resource")
    content = {
        k: draft[k]
        for k in (
            "project",
            "repository",
            "repository_id",
            "login",
            "operation",
            "endpoint",
            "payload",
        )
    }
    if draft["consent_digest"] != expected_digest or digest(canonical(content)) != expected_digest:
        raise ValueError("GitHub draft changed; prepare and review it again")
    if draft["status"] == "published":
        return draft
    if draft["status"] != "draft":
        raise ValueError(
            "This GitHub publication was already attempted; inspect GitHub before retrying"
        )
    account = connection()
    if not account["connected"] or account["login"] != draft["login"]:
        raise ValueError("Connected GitHub account changed; prepare a new draft")
    slug, remote = repository(state, project)
    if slug != draft["repository"] or remote["id"] != draft["repository_id"]:
        raise ValueError("GitHub repository changed; prepare a new draft")
    if not state.transition(
        uid, {"status": "draft", "consent_digest": expected_digest}, status="publishing"
    ):
        raise ValueError("GitHub publication is already in progress")
    try:
        result = request("POST", draft["endpoint"], draft["payload"])
        url = result.get("html_url", "")
        if not re.fullmatch(
            r"https://github\.com/"
            + re.escape(slug)
            + r"/(?:issues|pull)/[0-9]+(?:#issuecomment-[0-9]+)?",
            url,
        ):
            raise ValueError("GitHub returned an unexpected publication link")
        return state.update(
            uid, status="published", url=url, published_at=datetime.now(UTC).isoformat()
        )
    except Exception as exc:
        # A timeout may follow a successful write. Never retry the mutation automatically.
        state.update(
            uid,
            status="unknown",
            error="Publication outcome is unknown. Inspect GitHub before creating another draft.",
        )
        raise ValueError(
            "Publication outcome is unknown. Inspect GitHub before creating another draft."
        ) from exc
