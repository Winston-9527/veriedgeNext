#!/usr/bin/env python3
"""E0 第 2 步（mlx 栈）：用真实 mlx 低比特 kernel 跑同一批 contexts。

覆盖 EXO 实际执行路径：mlx-community 8-bit（EXO 默认）、本地转换的 4-bit / bf16。
直接喂 token id，不重新分词，因此与 torch 栈逐 context 对齐。

准备模型（在有 mlx_lm 的环境里，一次性）：
    python -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B --mlx-path mlx_q4 -q --q-bits 4 --q-group-size 64
    python -m mlx_lm convert --hf-path Qwen/Qwen3-0.6B --mlx-path mlx_bf16 --dtype bfloat16
示例：
    python e0_capture_mlx.py --contexts contexts_eval.jsonl --stack mlx_8bit \
        --model mlx-community/Qwen3-0.6B-8bit
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_lm import load

from e0_common import (CaptureWriter, context_positions, host_meta, layer_index, load_contexts,
                       parse_layers)


def quantize_in_memory(model, bits: int, group_size: int, layers):
    """与 `mlx_lm convert -q` 相同的 affine 按组量化，直接作用于已加载的模型。

    layers=None：量化所有可量化模块（含 embedding / lm_head，与 mlx-community 发布版一致）；
    layers=(a, b)：只量化第 a..b 个 decoder 层（模拟流水线里单个分片降精度）。
    """
    def pred(path, module):
        if not hasattr(module, "to_quantized") or module.weight.shape[-1] % group_size:
            return False
        if layers is None:
            return True
        idx = layer_index(path)
        return idx is not None and layers[0] <= idx <= layers[1]
    nn.quantize(model, group_size=group_size, bits=bits, class_predicate=pred)


def model_quantization(model: str):
    """从模型目录或 HF 缓存的 config.json 读量化配置（未量化返回 None）。"""
    cfg = Path(model) / "config.json"
    if not cfg.exists():
        from huggingface_hub import hf_hub_download
        cfg = Path(hf_hub_download(model, "config.json"))
    c = json.loads(cfg.read_text())
    return c.get("quantization") or c.get("quantization_config")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contexts", type=Path, required=True)
    ap.add_argument("--stack", required=True)
    ap.add_argument("--model", required=True, help="HF repo id 或本地 mlx 模型目录")
    ap.add_argument("--out-dir", type=Path, default=Path("captures"))
    ap.add_argument("--q-bits", type=int, default=0, help=">0 时加载后在内存中量化（模型需为未量化版）")
    ap.add_argument("--q-group-size", type=int, default=64)
    ap.add_argument("--layers", default="", help="只量化这些层，如 12-23；默认全部")
    args = ap.parse_args()

    rows, ctx_sha = load_contexts(args.contexts)
    # 共享显存的节点上不让 mlx 缓存释放后的缓冲区，避免峰值占用叠加
    if hasattr(mx, "set_cache_limit"):
        mx.set_cache_limit(0)
    t0 = time.time()
    model, _ = load(args.model)
    if args.q_bits:
        quantize_in_memory(model, args.q_bits, args.q_group_size, parse_layers(args.layers))
    t_prep = time.time() - t0

    writer = CaptureWriter()
    t0 = time.time()
    for r in rows:
        logits = model(mx.array([r["input_ids"]]))[0].astype(mx.float32)
        mx.eval(logits)
        writer.add(r["seq_idx"], context_positions(r), np.array(logits))
    t_fwd = time.time() - t0

    meta = {"stack": args.stack, "framework": "mlx", "model": str(args.model),
            "quantization": ({"bits": args.q_bits, "group_size": args.q_group_size, "mode": "affine",
                              "in_memory": True, "layers": args.layers or "all"}
                             if args.q_bits else model_quantization(args.model)),
            "device": str(mx.default_device()), "contexts_sha256": ctx_sha,
            "prep_s": round(t_prep, 2), "forward_s": round(t_fwd, 2),
            "mlx": getattr(mx, "__version__", "?"), **host_meta()}
    writer.save(args.out_dir / f"{args.stack}.npz", meta)


if __name__ == "__main__":
    main()
