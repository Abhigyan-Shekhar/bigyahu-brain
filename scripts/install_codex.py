"""Install the Company Brain skill and register its standalone MCP server.

Run with the toolkit environment: uv run python scripts/install_codex.py --config ...
"""

import argparse
import filecmp
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brain.config import load_config
from brain.registry import load_registry


def same_tree(source, target):
    if not target.is_dir() or target.is_symlink():
        return False
    files = {p.relative_to(source) for p in source.rglob("*") if p.is_file()}
    installed = {p.relative_to(target) for p in target.rglob("*") if p.is_file()}
    return files == installed and all(
        filecmp.cmp(source / p, target / p, shallow=False) for p in files
    )


def install_skill(source, target, force=False):
    if same_tree(source, target):
        return
    if (target.exists() or target.is_symlink()) and not force:
        raise ValueError(f"Different skill already exists at {target}; use --force to back it up")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="company-brain-", dir=target.parent.parent) as tmp:
        staged = Path(tmp) / "company-brain"
        shutil.copytree(source, staged)
        backup = None
        if target.exists() or target.is_symlink():
            backups = target.parent.parent / "skill-backups"
            backups.mkdir(exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix="company-brain-", dir=backups)) / target.name
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
        if backup is not None:
            print(f"Previous skill backed up to {backup}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--config", type=Path)
    selection.add_argument("--registry", type=Path)
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--skill-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="Replace a differing skill or MCP entry")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    home = (args.codex_home or Path(os.environ.get("CODEX_HOME", "~/.codex"))).expanduser().resolve()
    source = ROOT / "skills/company-brain"
    target = home / "skills/company-brain"
    if (target.exists() or target.is_symlink()) and not same_tree(source, target) and not args.force:
        parser.error(f"Different skill exists at {target}; use --force to back it up")
    env = dict(os.environ, CODEX_HOME=str(home))
    command = None
    if not args.skill_only:
        config = (args.registry or args.config or ROOT / "config/brain.local.yaml").expanduser().resolve()
        variable = "BRAIN_REGISTRY" if args.registry else "BRAIN_CONFIG"
        try:
            (load_registry if args.registry else load_config)(config)
        except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
            parser.error(f"Invalid config: {exc}. See docs/codex.md for 'brain init'.")
        codex = shutil.which("codex")
        if not codex:
            parser.error("Codex CLI is required; use --skill-only to install just the workflow")
        desired = {
            "type": "stdio", "command": sys.executable,
            "args": ["-m", "brain.mcp_server"],
            "env": {variable: str(config), "PYTHONPATH": str(ROOT / "src")},
        }
        current = subprocess.run(
            [codex, "mcp", "get", "company-brain", "--json"],
            check=False, capture_output=True, text=True, env=env, timeout=30,
        ) if home.exists() else subprocess.CompletedProcess(
            [], 1, stdout="", stderr="No MCP server named company-brain"
        )
        if current.returncode == 0:
            registered = json.loads(current.stdout)
            transport = registered["transport"]
            matches = all(transport.get(key) == value for key, value in desired.items())
            if (not matches or not registered.get("enabled", True)) and not args.force:
                parser.error("A different/disabled company-brain MCP entry exists; use --force to replace")
        elif "No MCP server named" not in current.stderr:
            parser.error("Cannot inspect Codex MCP configuration: " + current.stderr.strip())
        command = [
            codex, "mcp", "add", "company-brain",
            "--env", f"{variable}={config}", "--env", f"PYTHONPATH={ROOT / 'src'}",
            "--", sys.executable, "-m", "brain.mcp_server",
        ]
    print(f"Skill: {source} -> {target}")
    if command:
        print("MCP: " + shlex.join(command))
    if args.dry_run:
        print("Dry run: no changes made")
        return
    # Register first: a CLI failure must not replace an existing skill.
    if command:
        home.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, check=True, env=env, timeout=30)
    install_skill(source, target, args.force)
    print("Installed. Start a new Codex chat and invoke $company-brain.")


if __name__ == "__main__":
    main()
