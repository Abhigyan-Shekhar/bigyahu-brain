import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
audit = runpy.run_path(str(ROOT / "scripts/check_publication.py"))["audit"]


def test_rejects_raw_records_and_sensitive_export_content():
    paths = [
        "data/experiments/attempt/trace.jsonl",
        "docs/demo/trace.jsonl",
        "docs/demo/report.md",
        "docs/demo/token.txt",
    ]
    content = {
        "docs/demo/report.md": ("/" + "Users/local-person/project").encode(),
        "docs/demo/token.txt": ("ghp_" + "A" * 32).encode(),
    }
    findings = dict(audit(paths, lambda p: content[p]))
    assert findings[paths[0]] == "raw local record"
    assert findings[paths[1]] == "raw local record"
    assert findings[paths[2]] == "machine-specific path"
    assert findings[paths[3]] == "credential-shaped value"


def test_reviewed_export_with_provenance_is_allowed():
    assert not audit(
        ["docs/demo/report.md"], lambda p: b"Public source: https://github.com/org/repo/issues/1"
    )


def make_history_repo(tmp_path, files):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    commit_history(tmp_path)


def commit_history(repo):
    import subprocess

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )


def test_removed_trace_stays_blocked_in_history(tmp_path):
    import subprocess

    history = runpy.run_path(str(ROOT / "scripts/check_publication.py"))["audit_history"]
    make_history_repo(tmp_path, {"data/experiments/run/trace.jsonl": "{}", "README.md": "safe"})
    subprocess.run(["git", "-C", str(tmp_path), "rm", "-qr", "data"], check=True)
    commit_history(tmp_path)
    assert not (tmp_path / "data").exists()
    assert ("data/experiments/run/trace.jsonl", "raw local record") in history(tmp_path)


def test_removed_credential_shape_stays_blocked_in_history(tmp_path):
    import subprocess

    history = runpy.run_path(str(ROOT / "scripts/check_publication.py"))["audit_history"]
    make_history_repo(tmp_path, {"old.txt": "ghp_" + "A" * 32, "README.md": "safe"})
    subprocess.run(["git", "-C", str(tmp_path), "rm", "-q", "old.txt"], check=True)
    commit_history(tmp_path)
    assert ("old.txt", "credential-shaped value") in history(tmp_path)


def test_clean_history_passes_and_shallow_clone_fails(tmp_path):
    import subprocess

    history = runpy.run_path(str(ROOT / "scripts/check_publication.py"))["audit_history"]
    source = tmp_path / "source"
    make_history_repo(source, {"README.md": "public source provenance"})
    assert not history(source)
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth=1", source.as_uri(), str(shallow)], check=True)
    assert history(shallow) == [
        ("history", "shallow clone cannot verify complete reachable history")
    ]
