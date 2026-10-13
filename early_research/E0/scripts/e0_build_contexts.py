#!/usr/bin/env python3
"""E0 第 1 步：用参考模型生成贪心续写，固化 token 级 contexts。

默认 fp32；大模型在显存不足时可用 --dtype bfloat16 生成。contexts 只是 token 序列，
生成精度不影响之后的比较（参考 logits 由 fp32 栈单独 teacher-forced 计算）。

每条 prompt 生成 L 个贪心 token。之后所有执行栈都在同一串 token id 上做
teacher-forced 前向，于是每个续写位置都是一个独立的 canary context。

用法：
    python e0_build_contexts.py --prompts qwen_prompt_splits_stratified_v2_200_500.jsonl \
        --split evaluation --out contexts_eval.jsonl --gen-len 64 --device cuda
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM

from e0_common import host_meta

DEFAULT_MODEL = "Qwen/Qwen3-0.6B"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", type=Path, required=True)
    ap.add_argument("--split", default="evaluation", help="evaluation / calibration / all")
    ap.add_argument("--limit", type=int, default=0, help="只取前 N 条（冒烟测试用）")
    ap.add_argument("--gen-len", type=int, default=64)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dtype", choices=["float32", "bfloat16"], default="float32")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.prompts.read_text().splitlines() if l.strip()]
    if args.split != "all":
        rows = [r for r in rows if r["split"] == args.split]
    if args.limit:
        rows = rows[: args.limit]

    torch.manual_seed(0)
    dtype = torch.float32 if args.dtype == "float32" else torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=dtype).to(args.device).eval()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f, torch.no_grad():
        for i, r in enumerate(rows):
            ids = torch.tensor([r["input_ids"]], device=args.device)
            gen = model.generate(ids, max_new_tokens=args.gen_len, do_sample=False,
                                 attention_mask=torch.ones_like(ids))
            full = gen[0].tolist()
            f.write(json.dumps({
                "seq_idx": i, "prompt_id": r["prompt_id"], "split": r["split"],
                "prompt_len": len(r["input_ids"]), "input_ids": full,
                "family_id": r.get("family_id"),
            }) + "\n")
            if i % 50 == 0:
                print(f"[{i}/{len(rows)}] prompt_len={len(r['input_ids'])} total={len(full)}")

    sha = hashlib.sha256(args.out.read_bytes()).hexdigest()
    meta = {"model": args.model, "dtype": args.dtype, "device": str(args.device),
            "gen_len": args.gen_len, "split": args.split, "n": len(rows),
            "prompts_file": args.prompts.name,
            "prompts_sha256": hashlib.sha256(args.prompts.read_bytes()).hexdigest(),
            "contexts_sha256": sha, "torch": torch.__version__, **host_meta()}
    args.out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    print(f"contexts -> {args.out} sha256={sha[:16]}")


if __name__ == "__main__":
    main()
