"""Isolated deterministic Graphify invocation; never executes repository code."""

import json
import sys
from importlib.metadata import version
from pathlib import Path

PIN = "0.9.92"


def main():
    if version("graphifyy") != PIN:
        raise ValueError("Install the pinned graphify extra")
    from graphify.extract import extract

    root, cache, output = map(Path, sys.argv[1:4])
    paths = json.loads(Path(sys.argv[4]).read_text())
    result = extract([root / p for p in paths], root=root, cache_root=cache, parallel=False)
    # Omit upstream absolute input/cache paths from the interchange format.
    output.write_text(json.dumps({k: result[k] for k in ("nodes", "edges", "failed_sources")}))


if __name__ == "__main__":
    main()
