#!/bin/sh
# Run this yourself in an interactive terminal after reviewing the linked sources.
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src"
export BRAIN_CONFIG="$PWD/config/brain.browser-demo.local.yaml"
export BRAIN_OPERATOR_SESSION=1
printf '%s\n' 'LOCAL DEMO ONLY. Review D-1 and its sources before approving.'
.venv/bin/python -m brain inspect D-1
.venv/bin/python -m brain approve D-1
printf '%s\n' 'Review D-2 and all sources. Approval replaces D-1 and retains its evidence.'
.venv/bin/python -m brain inspect D-2
.venv/bin/python -m brain approve D-2
printf '%s\n' 'Human approval steps finished. Browser query 05 now shows supersession.'
