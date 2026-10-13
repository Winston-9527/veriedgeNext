#!/usr/bin/env python3
"""同档诚实栈：以"该档的标准实现"为参考，重算诚实误差与作弊误差。

E0 原来的设定把不同精度（fp32/bf16/fp16/8-bit）都当成诚实栈，并统一以 fp32 为参考。
但在分档收费的网络里，同一档的诚实节点用的是同一份权重、同一种计算精度，
只有硬件和后端不同。本脚本按档重新划分：

  档        参考栈（标准实现）   诚实栈（同权重、同计算精度、不同硬件/后端）
  fp16      torch_fp16 (CUDA)    apple_mps_fp16
  bf16      torch_bf16 (CUDA)    mlx_bf16, apple_mps_bf16, apple_mlx_bf16
  int8      mlx_8bit (CUDA)      apple_mlx_8bit（mlx 内存量化，参数相同 ⇒ 权重逐位相同）

在 run_dir 下运行：python scripts/e0_same_tier.py > analysis/same_tier.txt
"""

from __future__ import annotations

import glob
import os
import sys

import numpy as np

sys.path.insert(0, "scripts")
from e0_common import exact_binomial_design, load_capture  # noqa: E402

TIERS = {
    "fp16": ("torch_fp16", ["apple_mps_fp16"]),
    "bf16": ("torch_bf16", ["mlx_bf16", "apple_mps_bf16", "apple_mlx_bf16"]),
    "int8": ("mlx_8bit", ["apple_mlx_8bit"]),
}


def gap_err(ref, cap):
    """参考 top-1/top-2 logit 差在该栈上的偏差（两 token 都在该栈 top-5 内时）。"""
    rid, rv, ids, v = ref["topk_ids"], ref["topk_val"], cap["topk_ids"], cap["topk_val"]
    m1, m2 = ids == rid[:, :1], ids == rid[:, 1:2]
    ok = m1.any(1) & m2.any(1)
    e = (np.where(m1, v, 0).sum(1) - np.where(m2, v, 0).sum(1)) - (rv[:, 0] - rv[:, 1])
    return np.abs(e[ok])


def wilson_upper(x, z=1.645):
    n, p = len(x), float(np.mean(x))
    c = p + z * z / (2 * n) + z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, c / (1 + z * z / n))


def main():
    caps = {os.path.basename(f)[:-4]: load_capture(f) for f in glob.glob("captures/*.npz")}
    for tier, (ref_name, honest) in TIERS.items():
        ref = caps[ref_name]
        rid = ref["topk_ids"][:, 0]
        rm = ref["topk_val"][:, 0] - ref["topk_val"][:, 1]
        band = rm >= 0.5
        h_med = max(np.median(gap_err(ref, caps[h])) for h in honest)
        p_h = max(wilson_upper((caps[h]["topk_ids"][:, 0] != rid)[band]) for h in honest)
        print(f"\n### 档 = {tier}   参考 = {ref_name}   诚实栈 = {', '.join(honest)}")
        print(f"诚实误差中位数（取最差者）= {h_med:.4f}；高 margin 区诚实失配上界 = {p_h:.5f}"
              f"（区内 context 数 {int(band.sum())}）")
        print("%-28s %10s %8s %12s %10s %10s" % ("栈", "|dgap|中位", "误差比", "失配(全体)", "失配(区内)", "N(区内)"))
        for name in sorted(caps):
            if name in (ref_name, "torch_fp32"):
                continue
            c = caps[name]
            med = np.median(gap_err(ref, c))
            mis = c["topk_ids"][:, 0] != rid
            p_q = float(mis[band].mean())
            role = "诚实" if name in honest else ""
            d = exact_binomial_design(p_h, p_q, 1e-3, 1e-3) if not role else None
            n = d["N"] if d else ("—" if not role else "")
            print("%-28s %10.4f %8.1f %12.4f %10.4f %10s %s" %
                  (name, med, med / h_med, mis.mean(), p_q, n, role))


if __name__ == "__main__":
    main()
