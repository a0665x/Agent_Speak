#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
if [[ ! -x "$VENV_DIR/bin/pytest" ]]; then
  echo "Project .venv test dependencies are missing. Run ./scripts/setup.sh." >&2
  exit 1
fi
cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/src" "$VENV_DIR/bin/pytest" "$@"
if command -v node >/dev/null 2>&1; then
  node --check web/app.js
else
  echo "STATIC_CHECKS_SKIPPED node_not_found"
fi
echo "TESTS_OK pytest_passed"
