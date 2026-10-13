"""E0 补充：各栈相对 fp32 参考的 logit 误差尺度（每 7 个 context 抽 1 个）。
在 run_dir 下运行：python scripts/e0_error_scale.py
dlogit = 参考 top-1 token 的 logit 偏差；dgap12 = 参考 top-1/top-2 logit 差的偏差（两者都在该栈 top-5 内时）。
"""
import numpy as np, sys
sys.path.insert(0, "scripts")
from e0_common import load_capture
ref = load_capture("captures/torch_fp32.npz"); rid = ref["topk_ids"]; rv = ref["topk_val"]
names = ["apple_mps_fp32","torch_fp16","torch_bf16","apple_mps_bf16","mlx_bf16","apple_mlx_bf16",
         "torch_rtn_w8g128","mlx_8bit","apple_mlx_8bit","torch_bnb_int8",
         "torch_gptq_w4g128","torch_bnb_nf4","mlx_q4","torch_rtn_w4g128"]
print("%-20s %12s %8s %14s" % ("stack", "med|dlogit|", "p90", "med|dgap12|"))
for n in names:
    c = load_capture(f"captures/{n}.npz"); ids = c["topk_ids"]; v = c["topk_val"]
    d, g = [], []
    for i in range(0, len(rid), 7):
        a = np.where(ids[i] == rid[i, 0])[0]; b = np.where(ids[i] == rid[i, 1])[0]
        if len(a): d.append(v[i, a[0]] - rv[i, 0])
        if len(a) and len(b): g.append((v[i, a[0]] - v[i, b[0]]) - (rv[i, 0] - rv[i, 1]))
    d = np.abs(d); g = np.abs(g)
    print("%-20s %12.4f %8.3f %14.4f" % (n, np.median(d), np.percentile(d, 90), np.median(g)))
