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
