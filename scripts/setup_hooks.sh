#!/usr/bin/env bash
# Shell wrapper for scripts/setup_hooks.py
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if command -v uv &> /dev/null; then
    uv run python scripts/setup_hooks.py
else
    python3 scripts/setup_hooks.py
fi
