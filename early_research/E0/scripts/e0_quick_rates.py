import numpy as np, sys, glob, os
sys.path.insert(0, "scripts")
from e0_common import load_capture
ref = load_capture("captures/torch_fp32.npz"); rid = ref["topk_ids"]; rv = ref["topk_val"]
rm = rv[:, 0] - rv[:, 1]
print("contexts", len(rid), " frac ref_margin>=0.5:", round((rm >= 0.5).mean(), 3))
print("%-26s %8s %10s %10s %11s %9s" % ("stack", "mism", "mism|rm>=.5", "own-m@flip", "med|dlogit|", "p90"))
for f in sorted(glob.glob("captures/*.npz")):
    n = os.path.basename(f)[:-4]
    if n == "torch_fp32": continue
    c = load_capture(f); ids = c["topk_ids"]; v = c["topk_val"]
    m = ids[:, 0] != rid[:, 0]; om = v[:, 0] - v[:, 1]
    d = []
    for i in range(0, len(rid), 7):
        a = np.where(ids[i] == rid[i, 0])[0]
        if len(a): d.append(abs(v[i, a[0]] - rv[i, 0]))
    print("%-26s %8.4f %10.4f %10.3f %11.4f %9.3f" % (n, m.mean(), m[rm >= .5].mean(),
          np.median(om[m]) if m.any() else float("nan"), np.median(d), np.percentile(d, 90)))
