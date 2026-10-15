"""Read-only public GitHub snapshot collection. Run with uv run python."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def api(endpoint):
    return json.loads(
        subprocess.run(["gh", "api", endpoint], check=True, capture_output=True, text=True).stdout
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo")
    parser.add_argument("sha")
    parser.add_argument("--output", type=Path, default=Path("data/sources"))
    args = parser.parse_args()
    metadata = api(f"repos/{args.repo}")
    if metadata["private"]:
        raise SystemExit("Only public repositories are allowed")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    records = api(f"repos/{args.repo}/issues?state=all&per_page=20")
    if args.repo == "psf/requests":
        records.append(api(f"repos/{args.repo}/issues/4716"))
    for record in records:
        number = record["number"]
        record["comments_snapshot"] = api(
            f"repos/{args.repo}/issues/{number}/comments?per_page=100"
        )
        if "pull_request" in record:
            record["reviews_snapshot"] = api(
                f"repos/{args.repo}/pulls/{number}/reviews?per_page=100"
            )
            record["files_snapshot"] = api(f"repos/{args.repo}/pulls/{number}/files?per_page=100")
    raw = json.dumps(records, indent=2) + "\n"
    (out / "work.json").write_text(raw)
    manifest = {
        "repo_url": metadata["html_url"],
        "repo_id": "github.com/" + args.repo,
        "sha": args.sha,
        "license": (metadata.get("license") or {}).get("spdx_id"),
        "collected_at": datetime.now(UTC).isoformat(),
        "visibility": "public",
        "records": len(records),
        "sources": [r["html_url"] for r in records],
        "work_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "limitations": [
            "API discussion state is a collection-time snapshot, not commit-time state",
            "First 100 comments/reviews/files per item only; pagination omitted",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
