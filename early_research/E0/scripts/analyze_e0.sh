#!/usr/bin/env bash
# E0 分析：两种规格设定。只使用 captures/ 里已经存在的栈，缺的自动跳过。
#
#   bash analyze_e0.sh <run_dir>
set -euo pipefail

RUN_DIR=$(cd "$1" && pwd)
TORCH_PY=${TORCH_PY:-/usr/bin/python3}
CAP=$RUN_DIR/captures
cd "$RUN_DIR/scripts"
have() { local out=(); for s in "$@"; do [[ -f $CAP/$s.npz ]] && out+=("$s"); done; (IFS=,; echo "${out[*]}"); }
# 单分片降精度栈（run_e0_scale.sh 产出，命名 *_L<a>-<b>）
SHARD_4BIT=$(cd "$CAP" && ls *_L*-*.npz 2>/dev/null | sed 's/\.npz$//' | tr '\n' ' ' || true)

# 跨硬件诚实栈（CUDA + Apple），按规格精度分组
HONEST_BF16="torch_fp32_eager torch_bf16 torch_fp16 mlx_bf16 apple_mps_fp32 apple_mps_bf16 apple_mps_fp16 apple_mlx_bf16"
HONEST_8BIT="torch_rtn_w8g128 torch_bnb_int8 mlx_8bit apple_mlx_8bit"
CHEAT_8BIT="torch_rtn_w8g128 torch_bnb_int8 mlx_8bit apple_mlx_8bit"
CHEAT_4BIT="torch_rtn_w4g128 torch_gptq_w4g128 torch_bnb_nf4 mlx_q4 apple_mps_rtn_w4g128 apple_mlx_q4"
SELECTORS="torch_rtn_w4g128 torch_gptq_w4g128"

# 规格 = bf16/fp16 级：任何权重量化都算作弊
$TORCH_PY e0_analyze.py --captures-dir "$CAP" --ref torch_fp32 \
  --honest "$(have $HONEST_BF16)" --cheat "$(have $CHEAT_8BIT $CHEAT_4BIT $SHARD_4BIT)" \
  --escalate-to torch_bf16 --selectors "$(have $SELECTORS)" \
  --out-dir "$RUN_DIR/analysis/spec_bf16"

# 规格 = 8-bit（EXO 默认）：只有 4-bit 算作弊
$TORCH_PY e0_analyze.py --captures-dir "$CAP" --ref torch_fp32 \
  --honest "$(have $HONEST_BF16 $HONEST_8BIT)" --cheat "$(have $CHEAT_4BIT $SHARD_4BIT)" \
  --escalate-to "$( [[ -f $CAP/mlx_8bit.npz ]] && echo mlx_8bit || echo torch_rtn_w8g128 )" \
  --selectors "$(have $SELECTORS)" \
  --out-dir "$RUN_DIR/analysis/spec_8bit"

echo "E0 analysis done: $RUN_DIR/analysis/*/E0_REPORT.md"
