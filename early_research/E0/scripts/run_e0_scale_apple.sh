#!/usr/bin/env bash
# E0-scale Apple 侧（Apple M4 节点，16 GB 内存）：torch-MPS 与 mlx-Metal 栈。
#
#   MODEL=Qwen/Qwen3-4B bash run_e0_scale_apple.sh <run_dir>
#
# run_dir 下需已有 scripts/ 和从 CUDA 节点拷来的 contexts_eval.jsonl（sha256 必须一致）。
# 16 GB 内存放不下 4B fp32，所以 Apple 侧只跑 bf16/fp16 与量化栈。
set -euo pipefail

RUN_DIR=$(cd "$1" && pwd)
MODEL=${MODEL:-Qwen/Qwen3-4B}
TORCH_PY=${TORCH_PY:-$HOME/VeriEdge-repro/.venv/bin/python}
MLX_PY=${MLX_PY:-$HOME/verifiable-exo-smoke/.venv/bin/python}
CAP=$RUN_DIR/captures
CTX=$RUN_DIR/contexts_eval.jsonl
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1 PYTORCH_ENABLE_MPS_FALLBACK=0
cd "$RUN_DIR/scripts"
mkdir -p "$CAP" "$RUN_DIR/logs"

torch_cap() {
  local s=$1; shift
  [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
  echo "== $s  $(date +%H:%M:%S)"
  $TORCH_PY e0_capture_torch.py --contexts "$CTX" --out-dir "$CAP" --device mps --model "$MODEL" \
    --stack "$s" "$@" 2>&1 | tee "$RUN_DIR/logs/$s.log"
}
torch_cap apple_mps_bf16 --dtype bfloat16
torch_cap apple_mps_fp16 --dtype float16
torch_cap apple_mps_rtn_w4g128 --dtype bfloat16 --quant rtn --bits 4 --group-size 128

if [[ -z "${SKIP_MLX:-}" ]]; then
  mlx_cap() {
    local s=$1; shift
    [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
    echo "== $s  $(date +%H:%M:%S)"
    $MLX_PY e0_capture_mlx.py --contexts "$CTX" --out-dir "$CAP" --model "$MODEL" --stack "$s" "$@" \
      2>&1 | tee "$RUN_DIR/logs/$s.log"
  }
  mlx_cap apple_mlx_bf16
  mlx_cap apple_mlx_8bit --q-bits 8
  mlx_cap apple_mlx_q4   --q-bits 4
fi
echo "apple captures done: $CAP"
