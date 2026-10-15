"""Fail closed on tracked local execution records before committing or publishing."""

import re
import subprocess
import sys
from pathlib import PurePosixPath

RAW_ROOTS = ("data/experiments/", "data/validation/", "data/demo/", ".secrets/")
RUNTIME_NAMES = {"trace.jsonl", "stderr.txt", "invocation.json", "commands.json"}


def audit(paths, read):
    errors = []
    for path in paths:
        name = PurePosixPath(path).name
        if path.startswith(RAW_ROOTS) or name in RUNTIME_NAMES or name.endswith("-trace.jsonl"):
            errors.append((path, "raw local record"))
            continue
        data = read(path)
        # Binary exports require separate review; this guard only scans text content.
        if b"\0" in data[:8000]:
            continue
        if re.search(rb"/(?:Users/[^/\s]+|private/(?:tmp|var))/", data):
            errors.append((path, "machine-specific path"))
        if re.search(
            rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)",
            data,
        ):
            errors.append((path, "credential-shaped value"))
    return errors


def main():
    # Read the index, not potentially different working copies.
    paths = subprocess.check_output(["git", "ls-files", "-z"]).decode().strip("\0").split("\0")
    errors = audit(paths, lambda p: subprocess.check_output(["git", "show", ":" + p]))
    for path, kind in errors:
        print(f"{path}: {kind}", file=sys.stderr)
    if errors:
        return 1
    print(
        f"Publication boundary passed for {len(paths)} indexed files. Separate secret/history scans and export review still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
