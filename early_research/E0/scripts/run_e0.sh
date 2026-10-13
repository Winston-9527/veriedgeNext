#!/usr/bin/env bash
# E0 全流程（在执行节点上跑；默认按 CUDA 服务器的环境配置）。
#
#   bash run_e0.sh <run_dir> [limit]
#
# run_dir 下需已有：scripts/（本目录）和 data/qwen_prompt_splits_stratified_v2_200_500.jsonl
# limit>0 时只取前 limit 条 prompt（冒烟测试）。
# 可用环境变量覆盖：TORCH_PY、MLX_PY、GPU、SKIP_MLX=1、SKIP_BNB=1
set -euo pipefail

RUN_DIR=$(cd "$1" && pwd)
LIMIT=${2:-0}
TORCH_PY=${TORCH_PY:-/usr/bin/python3}
MLX_PY=${MLX_PY:-$HOME/verifiable-exo-smoke/.venv/bin/python}
PROMPTS=$RUN_DIR/data/qwen_prompt_splits_stratified_v2_200_500.jsonl
CAP=$RUN_DIR/captures
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1

# 选空闲显存最多的卡（节点是共享的）
if [[ -z "${GPU:-}" ]]; then
  GPU=$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits | sort -t, -k2 -nr | head -1 | cut -d, -f1)
fi
export CUDA_VISIBLE_DEVICES=$GPU
echo "run_dir=$RUN_DIR limit=$LIMIT gpu=$GPU"
cd "$RUN_DIR/scripts"
mkdir -p "$CAP" "$RUN_DIR/logs"

# ---- 1. contexts（fp32 参考贪心续写）
[[ -f $RUN_DIR/contexts_eval.jsonl ]] || $TORCH_PY e0_build_contexts.py --prompts "$PROMPTS" \
  --split evaluation --limit "$LIMIT" --out "$RUN_DIR/contexts_eval.jsonl"
[[ -f $RUN_DIR/contexts_calib.jsonl ]] || $TORCH_PY e0_build_contexts.py --prompts "$PROMPTS" \
  --split calibration --limit "$LIMIT" --out "$RUN_DIR/contexts_calib.jsonl"

torch_cap() {  # torch_cap <stack> <args...>
  local s=$1; shift
  [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
  echo "== $s"
  $TORCH_PY e0_capture_torch.py --contexts "$RUN_DIR/contexts_eval.jsonl" --out-dir "$CAP" \
    --stack "$s" "$@" 2>&1 | tee "$RUN_DIR/logs/$s.log"
}

# ---- 2a. torch 诚实栈
torch_cap torch_fp32        --dtype float32
torch_cap torch_fp32_eager  --dtype float32  --attn eager
torch_cap torch_bf16        --dtype bfloat16
torch_cap torch_fp16        --dtype float16
# ---- 2b. torch 作弊栈（权重 fake-quant，bf16 计算）
torch_cap torch_rtn_w8g128  --dtype bfloat16 --quant rtn  --bits 8 --group-size 128
torch_cap torch_rtn_w4g128  --dtype bfloat16 --quant rtn  --bits 4 --group-size 128
torch_cap torch_gptq_w4g128 --dtype bfloat16 --quant gptq --bits 4 --group-size 128 \
  --calib-contexts "$RUN_DIR/contexts_calib.jsonl"
if [[ -z "${SKIP_BNB:-}" ]]; then
  torch_cap torch_bnb_int8  --dtype float16  --quant bnb_int8
  torch_cap torch_bnb_nf4   --dtype bfloat16 --quant bnb_nf4
fi

# ---- 2c. mlx 栈（EXO 实际 kernel）
if [[ -z "${SKIP_MLX:-}" ]]; then
  MLXM=$RUN_DIR/mlx_models
  mkdir -p "$MLXM"
  [[ -d $MLXM/bf16 ]] || $MLX_PY -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B --mlx-path "$MLXM/bf16" --dtype bfloat16
  [[ -d $MLXM/q4 ]]   || $MLX_PY -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B --mlx-path "$MLXM/q4" -q --q-bits 4 --q-group-size 64
  mlx_cap() {
    local s=$1 m=$2
    [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
    echo "== $s"
    $MLX_PY e0_capture_mlx.py --contexts "$RUN_DIR/contexts_eval.jsonl" --out-dir "$CAP" \
      --stack "$s" --model "$m" 2>&1 | tee "$RUN_DIR/logs/$s.log"
  }
  mlx_cap mlx_bf16 "$MLXM/bf16"
  mlx_cap mlx_8bit mlx-community/Qwen3-0.6B-8bit
  mlx_cap mlx_q4   "$MLXM/q4"
fi

# ---- 3. 分析（Apple 侧 captures 拷回后可单独重跑 analyze_e0.sh）
TORCH_PY=$TORCH_PY bash "$RUN_DIR/scripts/analyze_e0.sh" "$RUN_DIR"
