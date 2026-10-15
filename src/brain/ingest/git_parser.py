import subprocess


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True, timeout=30
    ).stdout.strip()


def revision(root):
    return git(root, "rev-parse", "HEAD")


def clean(root):
    return not git(root, "status", "--porcelain", "--untracked-files=all")


def commits(root, limit=100):
    for sha in git(root, "log", f"-n{min(limit, 300)}", "--format=%H").splitlines():
        fields = git(root, "show", "-s", "--format=%an%x00%ae%x00%aI%x00%B", sha).split("\0", 3)
        yield {
            "sha": sha,
            "name": fields[0],
            "email": fields[1],
            "timestamp": fields[2],
            "body": fields[3],
            "files": git(
                root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha
            ).splitlines(),
        }
