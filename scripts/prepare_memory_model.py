"""Explicit one-time download of pinned Apache-2.0 MiniLM artifacts, then offline only."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision) or args.output.exists():
        parser.error("Immutable 40-character Hub revision and new output directory required")
    from huggingface_hub import snapshot_download

    model = "sentence-transformers/all-MiniLM-L6-v2"
    snapshot = Path(
        snapshot_download(
            model,
            revision=args.revision,
            allow_patterns=[
                "*.json",
                "*.txt",
                "model.safetensors",
                "1_Pooling/config.json",
                "LICENSE",
            ],
        )
    )
    args.output.mkdir(parents=True)
    hashes = {}
    # Copy materialized bytes; runtime does not follow Hub cache symlinks.
    for path in snapshot.rglob("*"):
        if path.is_file():
            relative = path.relative_to(snapshot)
            if (
                relative.suffix not in {".json", ".txt", ".safetensors"}
                and relative.name != "LICENSE"
            ):
                continue
            target = args.output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            target.write_bytes(raw)
            hashes[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
    manifest = {"model": model, "revision": args.revision, "license": "Apache-2.0", "files": hashes}
    (args.output / "brain-model.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"model": model, "revision": args.revision, "files": len(hashes)}))


if __name__ == "__main__":
    main()
