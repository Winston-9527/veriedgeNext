#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

echo "[e4-strict] building strict E4 raw tables"
"$PYTHON_BIN" "$REPO_ROOT/paper1_veriedge/E4/build_e4_strict_tables.py"

echo "[e4-strict] aggregating manuscript tables"
"$PYTHON_BIN" "$REPO_ROOT/paper1_veriedge/E4/build_e4_strict_views.py"

echo "[e4-strict] plotting figures"
"$PYTHON_BIN" "$REPO_ROOT/paper1_veriedge/E4/plot_e4_strict_results.py"

echo "[e4-strict] done"
