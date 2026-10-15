import os
import re
import stat
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
    username: str | None = None
    password_file: str | None = None
    tls: bool = False
    ca_file: str | None = None

    def connection_options(self):
        options = {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "ssl": self.tls,
            "socket_connect_timeout": 5,
            "socket_timeout": 30,
        }
        if self.tls:
            options.update(ssl_cert_reqs="required", ssl_check_hostname=True)
            if self.ca_file:
                options["ssl_ca_certs"] = self.ca_file
        if self.password_file:
            try:
                path = Path(self.password_file)
                with path.open() as stream:
                    mode = os.fstat(stream.fileno()).st_mode
                    if not stat.S_ISREG(mode) or mode & 0o077:
                        raise ValueError(
                            "Password file must be a regular file with mode 0600 or 0400"
                        )
                    password = stream.read(16385).rstrip("\r\n")
                if not password or len(password) > 16384:
                    raise ValueError("Password file is empty or exceeds size limit")
            except OSError:
                raise ValueError("Cannot read configured password file") from None
            options["password"] = password
        return options

    def __post_init__(self):
        if (
            not isinstance(self.host, str)
            or not self.host
            or any(c in self.host for c in "/@ \r\n")
        ):
            raise ValueError("host must be a hostname, not a URL or credential string")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        if type(self.tls) is not bool:
            raise ValueError("tls must be a boolean")
        if self.host not in {"localhost", "127.0.0.1", "::1"} and not self.tls:
            raise ValueError("Remote connections require TLS")
        for value in (self.password_file, self.ca_file):
            if value is not None and (not isinstance(value, str) or not Path(value).is_absolute()):
                raise ValueError("Credential and CA file paths must be absolute")
        if self.ca_file and not self.tls:
            raise ValueError("ca_file requires TLS")
        if self.username is not None and (not isinstance(self.username, str) or not self.username):
            raise ValueError("username must be a nonempty string when supplied")
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


def load_config(config_path=None):
    path = Path(config_path or os.environ["BRAIN_CONFIG"])
    if not path.is_absolute():
        raise ValueError("BRAIN_CONFIG must be absolute")
    return Config(**yaml.safe_load(path.read_text()))
