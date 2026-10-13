#!/usr/bin/env bash
# E0-scale（CUDA 节点）：在更大的模型上重跑被动基线，并加入"流水线里只有一个分片降精度"的栈。
#
#   MODEL=Qwen/Qwen3-4B bash run_e0_scale.sh <run_dir> [limit]
#
# 与 run_e0.sh（0.6B 记录版）的区别：
#   - fp32 参考默认放 CPU（4B fp32 约 16 GB，共享 GPU 放不下）；contexts 用 bf16 生成
#   - 其余 torch 栈直接按 bf16/fp16 加载（Qwen3 checkpoint 本身是 bf16，不丢信息）
#   - mlx 栈从原版权重加载后在内存中量化（与 mlx_lm convert 同参数：affine，group 64）
#   - 新增分片栈：把层均分三段，每段单独做 4-bit（RTN / GPTQ / mlx），命名 *_L<a>-<b>
# 可用环境变量覆盖：MODEL、TORCH_PY、MLX_PY、GPU、REF_DEVICE、CTX_DTYPE、SKIP_MLX=1、SKIP_BNB=1
set -euo pipefail

RUN_DIR=$(cd "$1" && pwd)
LIMIT=${2:-0}
MODEL=${MODEL:-Qwen/Qwen3-4B}
TORCH_PY=${TORCH_PY:-/usr/bin/python3}
MLX_PY=${MLX_PY:-$HOME/verifiable-exo-smoke/.venv/bin/python}
REF_DEVICE=${REF_DEVICE:-cpu}
CTX_DTYPE=${CTX_DTYPE:-bfloat16}
PROMPTS=$RUN_DIR/data/qwen_prompt_splits_stratified_v2_200_500.jsonl
CAP=$RUN_DIR/captures
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1

if [[ -z "${GPU:-}" ]]; then
  GPU=$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits | sort -t, -k2 -nr | head -1 | cut -d, -f1)
fi
export CUDA_VISIBLE_DEVICES=$GPU
cd "$RUN_DIR/scripts"
mkdir -p "$CAP" "$RUN_DIR/logs"

NL=$($TORCH_PY -c "from transformers import AutoConfig as A; print(A.from_pretrained('$MODEL').num_hidden_layers)")
T=$((NL / 3))
SHARDS="0-$((T - 1)) $T-$((2 * T - 1)) $((2 * T))-$((NL - 1))"
echo "run_dir=$RUN_DIR model=$MODEL layers=$NL shards=[$SHARDS] limit=$LIMIT gpu=$GPU ref_device=$REF_DEVICE"

# ---- 1. contexts
build_ctx() {  # build_ctx <split> <out>
  [[ -f $2 ]] || $TORCH_PY e0_build_contexts.py --prompts "$PROMPTS" --model "$MODEL" \
    --split "$1" --limit "$LIMIT" --dtype "$CTX_DTYPE" --out "$2"
}
build_ctx evaluation  "$RUN_DIR/contexts_eval.jsonl"
build_ctx calibration "$RUN_DIR/contexts_calib.jsonl"

torch_cap() {  # torch_cap <stack> <args...>
  local s=$1; shift
  [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
  echo "== $s  $(date +%H:%M:%S)"
  $TORCH_PY e0_capture_torch.py --contexts "$RUN_DIR/contexts_eval.jsonl" --out-dir "$CAP" \
    --model "$MODEL" --stack "$s" "$@" 2>&1 | tee "$RUN_DIR/logs/$s.log"
}
CALIB=(--calib-contexts "$RUN_DIR/contexts_calib.jsonl")

# ---- 2a. torch 诚实栈
torch_cap torch_fp32 --dtype float32 --device "$REF_DEVICE"
torch_cap torch_bf16 --dtype bfloat16
torch_cap torch_fp16 --dtype float16
# ---- 2b. 8-bit（spec_bf16 下算作弊，spec_8bit 下算诚实）
torch_cap torch_rtn_w8g128 --dtype bfloat16 --quant rtn --bits 8 --group-size 128
if [[ -z "${SKIP_BNB:-}" ]]; then torch_cap torch_bnb_int8 --dtype float16 --quant bnb_int8; fi
# ---- 2c. 整模型 4-bit
torch_cap torch_rtn_w4g128  --dtype bfloat16 --quant rtn  --bits 4 --group-size 128
torch_cap torch_gptq_w4g128 --dtype bfloat16 --quant gptq --bits 4 --group-size 128 "${CALIB[@]}"
if [[ -z "${SKIP_BNB:-}" ]]; then torch_cap torch_bnb_nf4 --dtype bfloat16 --quant bnb_nf4; fi
# ---- 2d. 单分片 4-bit
for L in $SHARDS; do
  torch_cap "torch_rtn_w4g128_L$L"  --dtype bfloat16 --quant rtn  --bits 4 --group-size 128 --layers "$L"
  torch_cap "torch_gptq_w4g128_L$L" --dtype bfloat16 --quant gptq --bits 4 --group-size 128 --layers "$L" "${CALIB[@]}"
done

# ---- 2e. mlx 栈（EXO 的 kernel 路径）
if [[ -z "${SKIP_MLX:-}" ]]; then
  mlx_cap() {  # mlx_cap <stack> <args...>
    local s=$1; shift
    [[ -f $CAP/$s.npz ]] && { echo "skip $s"; return; }
    echo "== $s  $(date +%H:%M:%S)"
    $MLX_PY e0_capture_mlx.py --contexts "$RUN_DIR/contexts_eval.jsonl" --out-dir "$CAP" \
      --model "$MODEL" --stack "$s" "$@" 2>&1 | tee "$RUN_DIR/logs/$s.log"
  }
  mlx_cap mlx_bf16
  mlx_cap mlx_8bit --q-bits 8
  mlx_cap mlx_q4   --q-bits 4
  for L in $SHARDS; do
    mlx_cap "mlx_q4_L$L" --q-bits 4 --layers "$L"
  done
fi

# ---- 3. 分析（Apple 侧 captures 拷回后可单独重跑）
TORCH_PY=$TORCH_PY bash "$RUN_DIR/scripts/analyze_e0.sh" "$RUN_DIR"
echo "E0-scale done: $RUN_DIR"
