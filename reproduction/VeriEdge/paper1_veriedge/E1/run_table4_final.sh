#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REMOTE_REPO="${REMOTE_REPO:-~/repo/paper/bc-ra-paper}"
REMOTE_REPO_REL="${REMOTE_REPO_REL:-repo/paper/bc-ra-paper}"
LOCAL_REPO="$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/.venv/bin/python3}"
PROMPT_GENERATOR="$REPO_ROOT/paper1_veriedge/E1/generate_qwen_prompt_splits.py"
PROMPT_DATASET="$REPO_ROOT/artifacts/thc/data/qwen_prompt_splits_40_200.jsonl"
CONFIG_PATH="${CONFIG_PATH:-$REPO_ROOT/artifacts/thc/config/e1_real_qwen_tstc_prefill_1x1_40_200.json}"

LOCAL_LOG_DIR="$REPO_ROOT/paper1_veriedge/E1/logs/table4_final"
REMOTE_LOG_REL="${REMOTE_LOG_REL:-$REMOTE_REPO_REL/paper1_veriedge/E1/logs/table4_final_remote}"
mkdir -p "$LOCAL_LOG_DIR"

REMOTE_TARGETS=(
  "jlmini_1@mini1"
  "jlmini_3@mini3"
  "siyuan@172.31.100.17"
)

run_local_bg() {
  local tag="$1"
  shift
  local log_path="$LOCAL_LOG_DIR/${tag}.log"
  nohup "$@" >"$log_path" 2>&1 &
  echo $!
}

remote_exec() {
  local target="$1"
  shift
  ssh -n "$target" "$@"
}

sync_repo_bits() {
  for target in "${REMOTE_TARGETS[@]}"; do
    rsync -az \
      --delete \
      --exclude ".venv" \
      --exclude "workspace/hf-cache" \
      --exclude "workspace/models" \
      "$REPO_ROOT/artifacts/thc/" "$target:$REMOTE_REPO/artifacts/thc/"
    rsync -az \
      --delete \
      "$REPO_ROOT/paper1_veriedge/E1/" "$target:$REMOTE_REPO/paper1_veriedge/E1/"
    rsync -az "$REPO_ROOT/pyproject.toml" "$REPO_ROOT/uv.lock" "$target:$REMOTE_REPO/"
  done
}

prepare_remote_cluster_copy() {
  local src="$1"
  local dst="${src%.json}.remote.json"
  "$PYTHON_BIN" - "$src" "$dst" <<'PY'
import json
import sys
from pathlib import Path

src = Path(sys.argv[1]).expanduser().resolve()
dst = Path(sys.argv[2]).expanduser().resolve()
payload = json.loads(src.read_text(encoding="utf-8"))
payload["model_id"] = "~/repo/paper/bc-ra-paper/workspace/models/Qwen3-0.6B"
dst.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
print(dst)
PY
}

generate_prompts() {
  "$PYTHON_BIN" "$PROMPT_GENERATOR" --output "$PROMPT_DATASET"
}

stop_all_known_servers() {
  pkill -f "[h]etero_qwen_server.py" || true
  for target in "${REMOTE_TARGETS[@]}"; do
    remote_exec "$target" "pkill -f '[h]etero_qwen_server.py' || true"
  done
}

start_local_server() {
  local cluster_file="$1"
  local local_node="$2"
  run_local_bg \
    "server_${local_node}" \
    env CLUSTER_FILE="$cluster_file" LOCAL_NODE="$local_node" PYTHON_BIN="$PYTHON_BIN" \
    bash "$REPO_ROOT/artifacts/thc/scripts/run_t3_hetero_server.sh" >/dev/null
}

start_remote_server() {
  local target="$1"
  local cluster_file="$2"
  local local_node="$3"
  local cluster_rel="${cluster_file#$REPO_ROOT/}"
  local remote_rel="${cluster_rel%.json}.remote.json"
  ssh -f -n "$target" "mkdir -p \"\$HOME/$REMOTE_LOG_REL\" && cd \"\$HOME/$REMOTE_REPO_REL\" && nohup env CLUSTER_FILE=\"\$HOME/$REMOTE_REPO_REL/$remote_rel\" LOCAL_NODE='$local_node' PYTHON_BIN='.venv/bin/python3' bash artifacts/thc/scripts/run_t3_hetero_server.sh > \"\$HOME/$REMOTE_LOG_REL/server_${local_node}.log\" 2>&1 </dev/null &"
}

wait_for_cluster() {
  local cluster_file="$1"
  "$PYTHON_BIN" - "$cluster_file" <<'PY'
import json
import sys
import time
from urllib.request import Request, urlopen

cluster_file = sys.argv[1]
nodes = json.load(open(cluster_file, "r", encoding="utf-8"))["nodes"]
deadline = time.time() + 180
while time.time() < deadline:
    pending = []
    for node in nodes:
        url = f"http://{node['host']}:{node['port']}/ping"
        try:
            req = Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=2.0) as resp:
                if resp.status != 200:
                    pending.append(url)
        except Exception:
            pending.append(url)
    if not pending:
        print("cluster ready")
        raise SystemExit(0)
    time.sleep(2)
raise SystemExit("cluster did not become ready in time")
PY
}

capture_variant() {
  local run_tag="$1"
  local cluster_file="$2"
  local split="$3"
  local output_dir="$4"

  OUTPUT_DIR="$output_dir" \
  CLUSTER_FILE="$cluster_file" \
  CONFIG_PATH="$CONFIG_PATH" \
  PYTHON_BIN="$PYTHON_BIN" \
  bash "$REPO_ROOT/paper1_veriedge/E1/run_capture.sh" --split "$split"
}

export_pair() {
  local owner="$1"
  local pair_label="$2"
  local left_eval="$3"
  local right_eval="$4"
  local delta_dir="$5"
  local log_dir="$6"
  mkdir -p "$log_dir"
  CONFIG_PATH="$CONFIG_PATH" PYTHON_BIN="$PYTHON_BIN" \
    bash "$REPO_ROOT/paper1_veriedge/E1/export_pairwise.sh" \
      --pair "${pair_label}::${left_eval}::${right_eval}" \
      --delta-map-file "$delta_dir/delta_map.json" \
      --stage-family prefill \
      --owner "$owner" \
      --output-dir "$log_dir"
}

run_pair() {
  local pair_id="$1"
  local pair_label="$2"
  local left_cluster="$3"
  local left_local_node="$4"
  local left_remote_a="$5"
  local left_remote_a_node="$6"
  local left_remote_b="$7"
  local left_remote_b_node="$8"
  local right_cluster="$9"
  local right_local_node="${10}"
  local right_remote_a="${11}"
  local right_remote_a_node="${12}"
  local right_remote_b="${13}"
  local right_remote_b_node="${14}"

  local base="$REPO_ROOT/workspace/captures/E1/${pair_id}"
  local left_calib="${base}_left_calib"
  local right_calib="${base}_right_calib"
  local left_eval="${base}_left_eval"
  local right_eval="${base}_right_eval"
  local delta_dir="${base}_delta"
  local log_dir="$REPO_ROOT/paper1_veriedge/E1/logs/${pair_id}"

  stop_all_known_servers
  start_local_server "$left_cluster" "$left_local_node"
  start_remote_server "$left_remote_a" "$left_cluster" "$left_remote_a_node"
  start_remote_server "$left_remote_b" "$left_cluster" "$left_remote_b_node"
  wait_for_cluster "$left_cluster"
  capture_variant "$pair_id" "$left_cluster" calibration "$left_calib"
  capture_variant "$pair_id" "$left_cluster" evaluation "$left_eval"

  stop_all_known_servers
  start_local_server "$right_cluster" "$right_local_node"
  start_remote_server "$right_remote_a" "$right_cluster" "$right_remote_a_node"
  start_remote_server "$right_remote_b" "$right_cluster" "$right_remote_b_node"
  wait_for_cluster "$right_cluster"
  capture_variant "$pair_id" "$right_cluster" calibration "$right_calib"
  capture_variant "$pair_id" "$right_cluster" evaluation "$right_eval"

  stop_all_known_servers
  PYTHON_BIN="$PYTHON_BIN" bash "$REPO_ROOT/artifacts/thc/scripts/run_t3_delta_calibration.sh" \
    "$delta_dir" "$left_calib" "$right_calib"
  export_pair "$pair_id" "$pair_label" "$left_eval" "$right_eval" "$delta_dir" "$log_dir"
}

main() {
  generate_prompts
  prepare_remote_cluster_copy "$REPO_ROOT/artifacts/thc/config/t4bf16_current_mixed_ref.json"
  prepare_remote_cluster_copy "$REPO_ROOT/artifacts/thc/config/t4bf16_current_mixed_metal.json"
  prepare_remote_cluster_copy "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_bf16_ref.json"
  prepare_remote_cluster_copy "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_metal_vs_apple_bf16.json"
  prepare_remote_cluster_copy "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_metal_vs_rtx_bf16.json"
  prepare_remote_cluster_copy "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_bf16_vs_rtx_fp32.json"
  sync_repo_bits

  run_pair \
    "t4_final_current_mixed_40_200" \
    "current_mixed_stack" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_current_mixed_ref.json" \
    "localm5bf16c1" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "siyuan@172.31.100.17" "linux17c3fp32" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_current_mixed_metal.json" \
    "localm5metalc1" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "siyuan@172.31.100.17" "linux17c3fp32"

  run_pair \
    "t4_final_applemetal_vs_applebf16_40_200" \
    "apple_metal_vs_apple_bf16" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_bf16_ref.json" \
    "localm5bf16c1" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "jlmini_1@mini1" "mini1bf16c3" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_metal_vs_apple_bf16.json" \
    "localm5metalc1" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "jlmini_1@mini1" "mini1bf16c3"

  run_pair \
    "t4_final_applemetal_vs_rtxbf16_40_200" \
    "apple_metal_vs_rtx_bf16" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_metal_vs_apple_bf16.json" \
    "localm5metalc1" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "jlmini_1@mini1" "mini1bf16c3" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_metal_vs_rtx_bf16.json" \
    "linux17c1bf16" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "jlmini_1@mini1" "mini1bf16c3"

  run_pair \
    "t4_final_applebf16_vs_rtxfp32_40_200" \
    "apple_bf16_vs_rtx_fp32" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_bf16_ref.json" \
    "localm5bf16c1" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "jlmini_1@mini1" "mini1bf16c3" \
    "$REPO_ROOT/artifacts/thc/config/t4bf16_apple_bf16_vs_rtx_fp32.json" \
    "linux17c1fp32" \
    "jlmini_3@mini3" "mini3bf16c2" \
    "jlmini_1@mini1" "mini1bf16c3"

  stop_all_known_servers
}

main "$@"
