import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    repo_root: Path
    repo_id: str
    repo_url: str = ""
    principal: str = "demo_operator"
    host: str = "127.0.0.1"
    port: int = 6379

    def __post_init__(self):
        root = Path(self.repo_root)
        if not root.is_absolute() or not root.is_dir():
            raise ValueError("repo_root must be an existing absolute directory")
        object.__setattr__(self, "repo_root", root.resolve())
        if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", self.principal):
            raise ValueError("Invalid trusted principal")
        if not self.repo_id or len(self.repo_id) > 200:
            raise ValueError("Invalid repo_id")
        if self.repo_url and not self.repo_url.startswith("https://github.com/"):
            raise ValueError("repo_url must identify a public GitHub repository")

    def graph_name(self, scope):
        if scope == "org":
            return "org_demo"
        if scope == "private":
            return "private_" + self.principal
        raise ValueError("scope must be org or private")

    def path(self, value):
        p = Path(value)
        if p.is_absolute() or not value or ".." in p.parts:
            raise ValueError("Expected repo-relative path")
        resolved = (self.repo_root / p).resolve()
        if not resolved.is_relative_to(self.repo_root):
            raise ValueError("Path escapes configured repository")
        return p.as_posix()


def load_config():
    path = Path(os.environ["BRAIN_CONFIG"])
    if not path.is_absolute():
        raise ValueError("BRAIN_CONFIG must be absolute")
    return Config(**yaml.safe_load(path.read_text()))
