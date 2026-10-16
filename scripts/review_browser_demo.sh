#!/bin/sh
# Optional compatibility wrapper; Windows uses the Python entry point directly.
set -eu
cd "$(dirname "$0")/.."
exec uv run --frozen python scripts/review_browser_demo.py "$@"
