"""Fail closed on tracked local execution records before committing or publishing."""

import argparse
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


def audit_history(repo="."):
    """Check every reachable commit tree, including records deleted from HEAD."""

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])

    if git("rev-parse", "--is-shallow-repository").strip() != b"false":
        return [("history", "shallow clone cannot verify complete reachable history")]
    errors, checked, contents = [], set(), {}
    for commit in git("rev-list", "HEAD").decode().splitlines():
        for entry in git("ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
            if not entry:
                continue
            metadata, path = entry.split(b"\t", 1)
            _, kind, oid = metadata.decode().split()
            if kind != "blob":
                continue
            path = path.decode()
            key = (oid, path)
            if key in checked:
                continue
            checked.add(key)

            # Raw-path rejection does not require reading or displaying its contents.
            def read(_path, oid=oid):
                if oid not in contents:
                    contents[oid] = git("cat-file", "blob", oid)
                return contents[oid]

            errors.extend(audit([path], read))
    return sorted(set(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        action="store_true",
        help="also reject unsafe content in all commits reachable from HEAD",
    )
    args = parser.parse_args()
    # Read the index, not potentially different working copies.
    paths = subprocess.check_output(["git", "ls-files", "-z"]).decode().strip("\0").split("\0")
    errors = audit(paths, lambda p: subprocess.check_output(["git", "show", ":" + p]))
    if args.history:
        errors.extend((path, "reachable history: " + kind) for path, kind in audit_history())
    for path, kind in errors:
        print(f"{path}: {kind}", file=sys.stderr)
    if errors:
        return 1
    print(
        f"Publication boundary passed for {len(paths)} indexed files"
        + (" and complete reachable history" if args.history else "")
        + ". Separate secret scanning and export review still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
