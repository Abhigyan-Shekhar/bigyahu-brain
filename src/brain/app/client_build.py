"""Keep a source checkout's served UI in sync with its frontend sources."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


def source_digest(frontend):
    paths = [p for p in (frontend / "src").rglob("*") if p.is_file()]
    paths.extend(frontend / name for name in (
        "index.html", "package.json", "package-lock.json", "vite.config.js",
    ))
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(frontend).as_posix()):
        digest.update(path.relative_to(frontend).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def current_build(assets, expected):
    """Treat malformed or incomplete manifests as rebuildable cache misses."""
    try:
        manifest = json.loads((assets / "build-info.json").read_text())
        if not isinstance(manifest, dict) or manifest.get("source_digest") != expected:
            return False
        names = manifest.get("assets")
        return (
            isinstance(names, list)
            and bool(names)
            and (assets / "index.html").is_file()
            and all(
                isinstance(name, str)
                and bool(name)
                and not Path(name).is_absolute()
                and ".." not in Path(name).parts
                and (assets / name).is_file()
                for name in names
            )
        )
    except (OSError, ValueError, TypeError):
        return False


def ensure_client(*, root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    frontend = root / "frontend"
    assets = root / "src/brain/web/app"
    if not (frontend / "package.json").is_file():
        # Installed wheels have prebuilt assets but no frontend source tree.
        if (Path(__file__).resolve().parents[1] / "web/app/index.html").is_file():
            return
        raise RuntimeError("UI assets missing. Start from a source checkout and build frontend first.")
    expected = source_digest(frontend)
    if current_build(assets, expected):
        return
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError(
            "The UI is missing or outdated. Install Node.js/npm, then restart the app. "
            "Manual build: npm ci --prefix frontend && npm run --prefix frontend build"
        )
    print("UI sources changed; building the current interface before startup…", flush=True)
    lock = hashlib.sha256((frontend / "package-lock.json").read_bytes()).hexdigest()
    stamp = frontend / "node_modules/.company-brain-lock"
    try:
        installed = stamp.read_text() == lock
    except OSError:
        installed = False
    try:
        if not installed:
            subprocess.run([npm, "ci", "--ignore-scripts"], cwd=frontend, check=True, timeout=300)
            stamp.write_text(lock)
        subprocess.run([npm, "run", "build"], cwd=frontend, check=True, timeout=180)
        if not current_build(assets, expected) or source_digest(frontend) != expected:
            raise ValueError("UI build is incomplete or sources changed; restart to retry")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise RuntimeError("UI build failed; app startup stopped to avoid serving an old interface.") from exc
