"""Sanity check (reviewer point 9): histogram of u_i = sign(x_i)(y_i - x_i).

For honest (A/B hetero), Gaussian additive, and Scale 1.10x:
  - u_i should be ~zero-centered + sign-balanced for honest & gaussian
  - u_i = 0.1|x_i| >= 0 (all right of zero) for scale 1.10x
Shows why Gaussian != Scale for SignRadial.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run_fixed_fpr_comparison import bundles_for, _prompt_seed, TAMPER_STRENGTH, SCALE_EPS
from attacks import inject_gaussian, inject_scale

MAIN = Path("/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace")
CHECKPOINT = "C2"


def collect_u(base_bundle, ref_bundle, aname, seed, n_coords=4096):
    """u_i = sign(x_i)(y_i - x_i) with x = H_A (ref), y from H_B (uniform protocol).

    All cases share the honest A/B nuisance: y0 = H_B, attacks start from y0,
    x = H_A. So u = sign(H_A)(y - H_A) always.
    """
    r0 = ref_bundle[f"prefill__{CHECKPOINT}"][0].astype(np.float64)   # H_A
    y0 = base_bundle[f"prefill__{CHECKPOINT}"][0].astype(np.float64)  # H_B
    if aname == "honest":
        c0 = y0
    elif aname == "gaussian":
        c0 = inject_gaussian(base_bundle, TAMPER_STRENGTH, seed)[f"prefill__{CHECKPOINT}"][0].astype(np.float64)
    elif aname == "scale":
        c0 = inject_scale(base_bundle, SCALE_EPS, seed)[f"prefill__{CHECKPOINT}"][0].astype(np.float64)
    else:
        raise ValueError(aname)
    T = min(r0.shape[0], c0.shape[0])
    flat = np.random.default_rng(seed).choice(T * r0.shape[1], size=min(n_coords, T * r0.shape[1]), replace=False)
    x = r0.reshape(-1)[flat]
    y = c0.reshape(-1)[flat]
    return np.sign(x) * (y - x)


def main() -> None:
    left_eval, right_eval = bundles_for("A/B", "eval")
    ids = sorted(set(left_eval) & set(right_eval))
    seed = _prompt_seed("x")

    us = {"honest": [], "gaussian": [], "scale": []}
    for pid in ids[:40]:
        for aname in us:
            us[aname].append(collect_u(right_eval[pid], left_eval[pid], aname, seed))
    for aname in us:
        us[aname] = np.concatenate(us[aname])

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharex=False)
    titles = {
        "honest": "Honest (A/B hetero)",
        "gaussian": "Gaussian additive",
        "scale": "Scale 1.10x",
    }
    for ax, aname in zip(axes, ("honest", "gaussian", "scale")):
        u = us[aname]
        ax.hist(u, bins=80, color="#4C72B0", alpha=0.85)
        ax.set_title(f"{titles[aname]}\nmean={u.mean():.4f}  |sum|/sum|x|={np.abs(u).sum():.3e}  frac>0={np.mean(u>0):.3f}")
        ax.axvline(0, color="r", ls="--", lw=1)
        ax.set_xlabel("u = sign(x)(y-x)")
        ax.set_ylabel("count")
    plt.tight_layout()
    out = Path(__file__).parent / "results" / "u_histogram_sanity.png"
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")
    print("\nsummary (sampled coords, 40 eval prompts):")
    print(f"{'case':10s} {'mean':>10s} {'std':>10s} {'frac>0':>8s} {'|sum|/N':>10s}")
    for aname in ("honest", "gaussian", "scale"):
        u = us[aname]
        print(f"{aname:10s} {u.mean():10.5f} {u.std():10.5f} {np.mean(u>0):8.3f} {np.abs(u).sum()/u.size:10.5f}")


if __name__ == "__main__":
    raise SystemExit(main())
