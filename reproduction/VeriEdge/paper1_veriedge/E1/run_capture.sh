#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/artifacts/thc/scripts/common.sh"

PYTHON_BIN="${PYTHON_BIN:-$REPO_VENV_PYTHON}"
thc_prepare_python_bin "$PYTHON_BIN"
thc_install_missing_modules "$PYTHON_BIN" \
  "numpy::numpy" \
  "transformers::transformers" \
  "safetensors::safetensors" \
  "accelerate::accelerate" \
  "sentencepiece::sentencepiece"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  exec "$PYTHON_BIN" "$REPO_ROOT/artifacts/thc/scripts/t3_hetero_cli.py" capture --help
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_ROOT/workspace/captures/E1/$STAMP}"
CLUSTER_FILE="${CLUSTER_FILE:-$REPO_ROOT/artifacts/thc/config/hetero_qwen_cluster.json}"
CONFIG_PATH="${CONFIG_PATH:-$REPO_ROOT/artifacts/thc/config/qwen.yaml}"
mkdir -p "$OUTPUT_DIR"

exec "$PYTHON_BIN" "$REPO_ROOT/artifacts/thc/scripts/t3_hetero_cli.py" capture \
  --cluster-file "$CLUSTER_FILE" \
  --config-path "$CONFIG_PATH" \
  --output-dir "$OUTPUT_DIR" \
  "$@"
