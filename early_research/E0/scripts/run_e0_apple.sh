#!/usr/bin/env bash
# E0 Apple 侧采集（Apple M4 节点）：torch-MPS 与 mlx-Metal 栈。
#
#   bash run_e0_apple.sh <run_dir>
#
# run_dir 下需已有 scripts/ 和从 CUDA 节点拷来的 contexts_eval.jsonl（同一份，sha256 必须一致）。
# 采完后把 captures/apple_*.npz 拷回 CUDA 节点的 captures/，再跑 analyze_e0.sh。
# 可用环境变量覆盖：TORCH_PY、MLX_PY、MLX_8BIT（8-bit 模型目录）、SKIP_MLX=1
set -euo pipefail

RUN_DIR=$(cd "$1" && pwd)
TORCH_PY=${TORCH_PY:-$HOME/VeriEdge-repro/.venv/bin/python}
MLX_PY=${MLX_PY:-$HOME/verifiable-exo-smoke/.venv/bin/python}
# EXO 在 Apple M4 节点上实际加载的 8-bit 权重（HF 缓存的 snapshot 不完整；safetensors sha256 与 CUDA 服务器的 HF 缓存一致：3ad5c96e…）
MLX_8BIT=${MLX_8BIT:-$HOME/.exo/models/mlx-community--Qwen3-0.6B-8bit}
CAP=$RUN_DIR/captures
CTX=$RUN_DIR/contexts_eval.jsonl
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1 PYTORCH_ENABLE_MPS_FALLBACK=0
cd "$RUN_DIR/scripts"
mkdir -p "$CAP" "$RUN_DIR/logs"

torch_cap() {
  local s=$1; shift
  [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
  echo "== $s"
  $TORCH_PY e0_capture_torch.py --contexts "$CTX" --out-dir "$CAP" --device mps \
    --stack "$s" "$@" 2>&1 | tee "$RUN_DIR/logs/$s.log"
}

# 诚实栈：Apple GPU 上的计算精度
torch_cap apple_mps_fp32 --dtype float32
torch_cap apple_mps_bf16 --dtype bfloat16
torch_cap apple_mps_fp16 --dtype float16
# 作弊栈：跨硬件的 4-bit（检验 canary 在 Apple 作弊者上是否同样有效）
torch_cap apple_mps_rtn_w4g128 --dtype bfloat16 --quant rtn --bits 4 --group-size 128

if [[ -z "${SKIP_MLX:-}" ]]; then
  MLXM=$RUN_DIR/mlx_models
  mkdir -p "$MLXM"
  [[ -d $MLXM/bf16 ]] || $MLX_PY -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B --mlx-path "$MLXM/bf16" --dtype bfloat16
  [[ -d $MLXM/q4 ]]   || $MLX_PY -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B --mlx-path "$MLXM/q4" -q --q-bits 4 --q-group-size 64
  mlx_cap() {
    local s=$1 m=$2
    [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
    echo "== $s"
    $MLX_PY e0_capture_mlx.py --contexts "$CTX" --out-dir "$CAP" --stack "$s" --model "$m" \
      2>&1 | tee "$RUN_DIR/logs/$s.log"
  }
  mlx_cap apple_mlx_bf16 "$MLXM/bf16"
  mlx_cap apple_mlx_8bit "$MLX_8BIT"   # EXO 在 Apple 节点上的实际路径
  mlx_cap apple_mlx_q4   "$MLXM/q4"
fi
echo "apple captures done: $CAP"
