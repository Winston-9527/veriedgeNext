#!/usr/bin/env python3
"""E0 第 2 步（torch 栈）：在固定 contexts 上 teacher-forced 前向，保存逐位置 top-K logits。

一个调用 = 一个执行栈。栈由 计算精度 × 权重量化方式 决定：
    --dtype  float32 | bfloat16 | float16          （诚实栈：只改计算精度）
    --quant  none | rtn | gptq | bnb_nf4 | bnb_int8 （作弊栈：降低权重精度）

示例：
    python e0_capture_torch.py --contexts contexts_eval.jsonl --stack torch_fp32 --dtype float32
    python e0_capture_torch.py --contexts contexts_eval.jsonl --stack torch_rtn_w4g128 \
        --dtype bfloat16 --quant rtn --bits 4 --group-size 128
    python e0_capture_torch.py --contexts contexts_eval.jsonl --stack torch_gptq_w4g128 \
        --dtype bfloat16 --quant gptq --bits 4 --group-size 128 --calib-contexts contexts_calib.jsonl
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM

from e0_common import (CaptureWriter, context_positions, decoder_linears, gptq_quantize_,
                       host_meta, load_contexts, parse_layers, rtn_quantize_)

DTYPES = {"float32": torch.float32, "bfloat16": torch.bfloat16, "float16": torch.float16}


def load_model(args):
    kw = {"attn_implementation": args.attn} if args.attn else {}
    if args.quant in ("bnb_nf4", "bnb_int8"):
        from transformers import BitsAndBytesConfig
        qc = (BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=DTYPES[args.dtype])
              if args.quant == "bnb_nf4" else BitsAndBytesConfig(load_in_8bit=True))
        return AutoModelForCausalLM.from_pretrained(
            args.model, dtype=DTYPES[args.dtype], quantization_config=qc,
            device_map={"": args.device}, **kw).eval()
    # Qwen3 的 checkpoint 本身就是 bf16，直接按计算精度加载不丢信息；
    # 量化函数内部逐个权重升到 fp32 做数学运算。fp32 只用于参考栈（大模型放 CPU）。
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=DTYPES[args.dtype], **kw)
    return model.to(args.device).eval()


@torch.no_grad()
def collect_hessians(model, calib_rows, device, layers):
    """对每个被量化的 decoder Linear 累积 H = 2·XᵀX/n（非逐层顺序版 GPTQ）。

    H 放在 CPU 的 fp32 上：4B 模型 down_proj 的 H 单个就有 9728² 个元素，全放显存放不下。
    """
    linears = decoder_linears(model, layers)
    H = {n: None for n, _ in linears}
    count = {n: 0 for n, _ in linears}

    def make_hook(name):
        def hook(mod, inp, out):
            x = inp[0].reshape(-1, inp[0].shape[-1]).float().cpu()
            n_new = x.shape[0]
            if H[name] is None:
                H[name] = torch.zeros(x.shape[1], x.shape[1])
            H[name] *= count[name] / (count[name] + n_new)
            count[name] += n_new
            x = x * (2 / count[name]) ** 0.5
            H[name] += x.T @ x
        return hook

    handles = [m.register_forward_hook(make_hook(n)) for n, m in linears]
    for r in calib_rows:
        model(torch.tensor([r["input_ids"]], device=device))
    for h in handles:
        h.remove()
    return H


def apply_weight_quant(model, args):
    layers = parse_layers(args.layers)
    if args.quant == "rtn":
        for _, m in decoder_linears(model, layers):
            rtn_quantize_(m.weight, args.bits, args.group_size, args.sym)
    elif args.quant == "gptq":
        calib, _ = load_contexts(args.calib_contexts)
        H = collect_hessians(model, calib[: args.calib_n], args.device, layers)
        dev = "cuda" if torch.cuda.is_available() else None
        for name, m in decoder_linears(model, layers):
            gptq_quantize_(m.weight, H.pop(name), args.bits, args.group_size, args.sym, device=dev)
        torch.cuda.empty_cache() if torch.cuda.is_available() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contexts", type=Path, required=True)
    ap.add_argument("--stack", required=True, help="栈名，用作输出文件名")
    ap.add_argument("--out-dir", type=Path, default=Path("captures"))
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", choices=list(DTYPES), default="float32")
    ap.add_argument("--attn", default="", help="eager / sdpa，留空用默认（诚实漂移的额外来源）")
    ap.add_argument("--quant", choices=["none", "rtn", "gptq", "bnb_nf4", "bnb_int8"], default="none")
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--group-size", type=int, default=128)
    ap.add_argument("--sym", action="store_true", help="对称量化（默认非对称 + zero point）")
    ap.add_argument("--layers", default="", help="只量化这些层，如 12-23（闭区间）；默认全部层")
    ap.add_argument("--calib-contexts", type=Path, help="GPTQ 校准用 contexts（用 calibration split）")
    ap.add_argument("--calib-n", type=int, default=128)
    args = ap.parse_args()
    if args.quant == "gptq" and not args.calib_contexts:
        ap.error("--quant gptq 需要 --calib-contexts")

    rows, ctx_sha = load_contexts(args.contexts)
    t0 = time.time()
    model = load_model(args)
    apply_weight_quant(model, args)
    t_prep = time.time() - t0

    writer = CaptureWriter()
    t0 = time.time()
    with torch.no_grad():
        for r in rows:
            ids = torch.tensor([r["input_ids"]], device=args.device)
            logits = model(ids).logits[0].float().cpu().numpy()
            writer.add(r["seq_idx"], context_positions(r), logits)
    t_fwd = time.time() - t0

    dev_name = torch.cuda.get_device_name(0) if str(args.device).startswith("cuda") else str(args.device)
    meta = {"stack": args.stack, "framework": "torch", "model": args.model,
            "dtype": args.dtype, "attn": args.attn or "default", "quant": args.quant,
            "bits": args.bits if args.quant in ("rtn", "gptq") else None,
            "group_size": args.group_size if args.quant in ("rtn", "gptq") else None,
            "sym": args.sym if args.quant in ("rtn", "gptq") else None,
            "layers": args.layers or "all",
            "calib_n": args.calib_n if args.quant == "gptq" else None,
            "device": dev_name, "contexts_sha256": ctx_sha,
            "prep_s": round(t_prep, 2), "forward_s": round(t_fwd, 2),
            "torch": torch.__version__, **host_meta()}
    writer.save(args.out_dir / f"{args.stack}.npz", meta)


if __name__ == "__main__":
    main()
