#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/artifacts/thc/scripts/common.sh"

PYTHON_BIN="${PYTHON_BIN:-$REPO_VENV_PYTHON}"
CLUSTER_FILE="${CLUSTER_FILE:-$REPO_ROOT/artifacts/thc/config/hetero_qwen_cluster.json}"
CONFIG_PATH="${CONFIG_PATH:-$REPO_ROOT/artifacts/thc/config/qwen.yaml}"
RUN_TAG="${RUN_TAG:-real_e1}"
CAPTURE_ROOT_BASE="${CAPTURE_ROOT_BASE:-$REPO_ROOT/workspace/captures/E1/$RUN_TAG}"
CALIB_A_DIR="${CALIB_A_DIR:-${CAPTURE_ROOT_BASE}_calib_a}"
CALIB_B_DIR="${CALIB_B_DIR:-${CAPTURE_ROOT_BASE}_calib_b}"
EVAL_A_DIR="${EVAL_A_DIR:-${CAPTURE_ROOT_BASE}_eval_a}"
EVAL_B_DIR="${EVAL_B_DIR:-${CAPTURE_ROOT_BASE}_eval_b}"
DELTA_DIR="${DELTA_DIR:-${CAPTURE_ROOT_BASE}_delta}"
LOG_DIR="${LOG_DIR:-$REPO_ROOT/paper1_veriedge/E1/logs/$RUN_TAG}"
PAIR_LABEL="${PAIR_LABEL:-jlmini3_linux124_jlmini2}"
OWNER="${OWNER:-$RUN_TAG}"
LIMIT_PROMPTS="${LIMIT_PROMPTS:-0}"
PERCENTILE="${PERCENTILE:-99.0}"
LOCAL_NODE="${LOCAL_NODE:-}"

thc_prepare_python_bin "$PYTHON_BIN"
thc_install_missing_modules "$PYTHON_BIN" \
  "numpy::numpy" \
  "transformers::transformers" \
  "safetensors::safetensors" \
  "accelerate::accelerate" \
  "sentencepiece::sentencepiece"

usage() {
  cat <<'EOF'
Usage:
  bash paper1_veriedge/E1/real_e1.sh prefetch
  LOCAL_NODE=jlmini_3 bash paper1_veriedge/E1/real_e1.sh check
  LOCAL_NODE=jlmini_3 bash paper1_veriedge/E1/real_e1.sh server
  RUN_TAG=real_e1_round1 bash paper1_veriedge/E1/real_e1.sh capture-calib-a
  RUN_TAG=real_e1_round1 bash paper1_veriedge/E1/real_e1.sh capture-calib-b
  RUN_TAG=real_e1_round1 bash paper1_veriedge/E1/real_e1.sh capture-eval-a
  RUN_TAG=real_e1_round1 bash paper1_veriedge/E1/real_e1.sh capture-eval-b
  RUN_TAG=real_e1_round1 bash paper1_veriedge/E1/real_e1.sh calibrate
  RUN_TAG=real_e1_round1 bash paper1_veriedge/E1/real_e1.sh export
EOF
}

prefetch() {
  "$PYTHON_BIN" - <<'PY'
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

model_id = "Qwen/Qwen3-0.6B"
config = AutoConfig.from_pretrained(model_id, trust_remote_code=False)
print("model_type", getattr(config, "model_type", None))
print("num_hidden_layers", getattr(config, "num_hidden_layers", None))
AutoTokenizer.from_pretrained(model_id, trust_remote_code=False)
AutoModelForCausalLM.from_pretrained(
    model_id,
    trust_remote_code=False,
    torch_dtype="auto",
    low_cpu_mem_usage=True,
)
print("prefetch complete")
PY
}

need_local_node() {
  [[ -n "$LOCAL_NODE" ]] || thc_die "LOCAL_NODE is required for this action"
}

capture_once() {
  local split="$1"
  local output_dir="$2"
  OUTPUT_DIR="$output_dir" CLUSTER_FILE="$CLUSTER_FILE" CONFIG_PATH="$CONFIG_PATH" PYTHON_BIN="$PYTHON_BIN" \
    bash "$REPO_ROOT/paper1_veriedge/E1/run_capture.sh" --split "$split" --limit-prompts "$LIMIT_PROMPTS"
}

case "${1:-}" in
  prefetch)
    prefetch
    ;;
  check)
    need_local_node
    LOCAL_NODE="$LOCAL_NODE" CLUSTER_FILE="$CLUSTER_FILE" PYTHON_BIN="$PYTHON_BIN" \
      bash "$REPO_ROOT/artifacts/thc/scripts/check_t3_hetero_env.sh"
    ;;
  server)
    need_local_node
    LOCAL_NODE="$LOCAL_NODE" CLUSTER_FILE="$CLUSTER_FILE" PYTHON_BIN="$PYTHON_BIN" \
      bash "$REPO_ROOT/artifacts/thc/scripts/run_t3_hetero_server.sh"
    ;;
  capture-calib-a)
    capture_once calibration "$CALIB_A_DIR"
    ;;
  capture-calib-b)
    capture_once calibration "$CALIB_B_DIR"
    ;;
  capture-eval-a)
    capture_once evaluation "$EVAL_A_DIR"
    ;;
  capture-eval-b)
    capture_once evaluation "$EVAL_B_DIR"
    ;;
  calibrate)
    PYTHON_BIN="$PYTHON_BIN" bash "$REPO_ROOT/artifacts/thc/scripts/run_t3_delta_calibration.sh" \
      "$DELTA_DIR" "$CALIB_A_DIR" "$CALIB_B_DIR"
    ;;
  export)
    mkdir -p "$LOG_DIR"
    CONFIG_PATH="$CONFIG_PATH" PYTHON_BIN="$PYTHON_BIN" \
      bash "$REPO_ROOT/paper1_veriedge/E1/export_pairwise.sh" \
        --pair "${PAIR_LABEL}::${EVAL_A_DIR}::${EVAL_B_DIR}" \
        --delta-map-file "$DELTA_DIR/delta_map.json" \
        --stage-family prefill \
        --owner "$OWNER" \
        --output-dir "$LOG_DIR"
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    thc_die "unknown action: $1"
    ;;
esac
