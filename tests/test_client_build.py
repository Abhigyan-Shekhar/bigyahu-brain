"""A pulled source change must not silently retain an old served interface."""
import hashlib
import json
from unittest.mock import Mock

import pytest

from brain.app import client_build


@pytest.fixture
def checkout(tmp_path):
    frontend = tmp_path / 'frontend'
    (frontend / 'src').mkdir(parents=True)
    for name in ('index.html', 'package.json', 'package-lock.json', 'vite.config.js'):
        (frontend / name).write_text('{}')
    (frontend / 'src/main.jsx').write_text('new interface')
    assets = tmp_path / 'src/brain/web/app'
    assets.mkdir(parents=True)
    return tmp_path, frontend, assets


def mark_built(frontend, assets):
    (assets / 'index.html').write_text('<html>new interface</html>')
    (assets / 'current.js').write_text('new interface')
    (assets / 'build-info.json').write_text(json.dumps({
        'source_digest': client_build.source_digest(frontend), 'assets': ['current.js', 'index.html'],
    }))


def test_current_build_does_not_call_npm(checkout, monkeypatch):
    root, frontend, assets = checkout
    mark_built(frontend, assets)
    run = Mock()
    monkeypatch.setattr(client_build.subprocess, 'run', run)
    client_build.ensure_client(root=root)
    run.assert_not_called()


def test_pulled_sources_and_deleted_assets_trigger_rebuild(checkout, monkeypatch):
    root, frontend, assets = checkout
    mark_built(frontend, assets)
    (frontend / 'src/main.jsx').write_text('pulled interface')
    monkeypatch.setattr(client_build.shutil, 'which', lambda _: 'npm')
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        if 'ci' in argv:
            (frontend / 'node_modules').mkdir(exist_ok=True)
        else:
            mark_built(frontend, assets)

    monkeypatch.setattr(client_build.subprocess, 'run', run)
    client_build.ensure_client(root=root)
    assert calls == [['npm', 'ci', '--ignore-scripts'], ['npm', 'run', 'build']]
    calls.clear()
    (assets / 'current.js').unlink()
    client_build.ensure_client(root=root)
    assert calls == [['npm', 'run', 'build']]
    assert (frontend / 'node_modules/.company-brain-lock').read_text() == hashlib.sha256(
        (frontend / 'package-lock.json').read_bytes()).hexdigest()


def test_missing_npm_or_failed_build_blocks_stale_ui(checkout, monkeypatch):
    root, frontend, assets = checkout
    mark_built(frontend, assets)
    (frontend / 'src/main.jsx').write_text('changed')
    monkeypatch.setattr(client_build.shutil, 'which', lambda _: None)
    with pytest.raises(RuntimeError, match='outdated'):
        client_build.ensure_client(root=root)
    monkeypatch.setattr(client_build.shutil, 'which', lambda _: 'npm')
    def fail(*args, **kwargs):
        raise client_build.subprocess.CalledProcessError(1, 'npm')
    monkeypatch.setattr(client_build.subprocess, 'run', fail)
    with pytest.raises(RuntimeError, match='startup stopped'):
        client_build.ensure_client(root=root)
