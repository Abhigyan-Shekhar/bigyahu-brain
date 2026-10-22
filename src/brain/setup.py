"""Create a standalone repository configuration without the web application."""

from dataclasses import asdict
from pathlib import Path

import yaml

from .config import Config
from .ingest.git_parser import git, revision


def initialize(repo, config_path, repo_id, principal, host="127.0.0.1", port=6379, repo_url=""):
    root = Path(git(Path(repo).resolve(), "rev-parse", "--show-toplevel")).resolve()
    revision(root)  # Reject repositories without a committed revision.
    cfg = Config(root, repo_id, repo_url=repo_url, principal=principal, host=host, port=port)
    destination = Path(config_path).expanduser().resolve()
    if destination.is_relative_to(root):
        relative = destination.relative_to(root).as_posix()
        import subprocess

        ignored = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "--quiet", "--", relative],
            check=False, timeout=30,
        )
        if ignored.returncode != 0:
            raise ValueError("Configuration inside the checkout must be gitignored")
    payload = asdict(cfg)
    payload["repo_root"] = str(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(yaml.safe_dump(payload, sort_keys=False))
    return cfg, destination
