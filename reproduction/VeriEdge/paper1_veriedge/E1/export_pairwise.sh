#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/artifacts/thc/scripts/common.sh"

PYTHON_BIN="${PYTHON_BIN:-$REPO_VENV_PYTHON}"
thc_prepare_python_bin "$PYTHON_BIN"
thc_install_missing_modules "$PYTHON_BIN" "numpy::numpy"
CONFIG_PATH="${CONFIG_PATH:-$REPO_ROOT/artifacts/thc/config/qwen.yaml}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  exec "$PYTHON_BIN" "$REPO_ROOT/artifacts/thc/src/e1_pairwise_report.py" --help
fi

exec "$PYTHON_BIN" "$REPO_ROOT/artifacts/thc/src/e1_pairwise_report.py" \
  --config "$CONFIG_PATH" \
  "$@"
