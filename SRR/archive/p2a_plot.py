"""P2a: q-scaling law + u_i histogram figures.

fig5_q_scaling.png:
  - honest SignRadial p99(q) for each pair (should fall ~ 1/sqrt(q))
  - horizontal line at scale-attack value 0.10 (independent of q)
  - cross-over point = q above which honest p99 < scale signal

fig6_ui_hist.png:
  - histogram of u_i = sign(x_i)(y_i-x_i) for:
      honest (heterogeneous)  -> zero-centered, symmetric
      scale 1.10x             -> all >= 0 (positive side)
      scale 0.90x             -> all <= 0 (negative side)
  Shows the cancellation mechanism: honest u_i has E[u]~0, scale u_i is one-sided.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN
from run_srr_offline import PAIRS as PAIR_CFG
from radial import sign_radial_stat
from attacks import inject_scale

FIG = HERE / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

QS = [16, 32, 64, 128, 256, 512, 1024]
PAIR_LIST = ["A/B", "A/C", "A/D", "B/D"]


def _cfg(pair):
    return PAIR_CFG[pair]


def honest_p99_curve():
    table = {}
    for pair in PAIR_LIST:
        pcfg = _cfg(pair)
        base = pcfg["base"]
        Le = load_split(base, pcfg["left_eval"])
        Re = load_split(base, pcfg["right_eval"])
        eval_ids = sorted(set(Le) & set(Re))
        vals = []
        for q in QS:
            scores = []
            for s in (1, 2, 3):
                for pid in eval_ids:
                    P, B = sign_radial_stat(Le[pid]["prefill__C1"], Re[pid]["prefill__C1"], s, n=q)
                    scores.append(abs(P) / (B + 1e-12))
            vals.append(np.percentile(scores, 99))
        table[pair] = vals
    return table


def ui_histogram():
    pair = "A/B"
    pcfg = _cfg(pair)
    base = pcfg["base"]
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re))
    q = 256
    seed = 1

    def ui_values(cand, ref, ck):
        c0 = cand[ck][0]
        r0 = ref[ck][0]
        T = min(c0.shape[0], r0.shape[0])
        D = c0.shape[1]
        rng = np.random.default_rng(seed)
        flat = rng.choice(T * D, size=q, replace=False)
        rows, cols = np.unravel_index(flat, (T, D))
        x = r0[rows, cols]
        y = c0[rows, cols]
        return np.sign(x) * (y - x)

    honest_u = np.concatenate([ui_values(Le[pid], Re[pid], "prefill__C1") for pid in eval_ids[:20]])
    scale_up = np.concatenate([ui_values(inject_scale(Re[pid], 0.10), Re[pid], "prefill__C2") for pid in eval_ids[:20]])
    scale_dn = np.concatenate([ui_values(inject_scale(Re[pid], -0.10), Re[pid], "prefill__C2") for pid in eval_ids[:20]])
    return honest_u, scale_up, scale_dn


def main():
    # fig5: q-scaling
    table = honest_p99_curve()
    fig, ax = plt.subplots(figsize=(9, 6), constrained_layout=True)
    for pair in PAIR_LIST:
        ax.plot(QS, table[pair], "o-", label=f"{pair} honest C1 p99")
    ax.axhline(0.10, color="red", ls="--", lw=2, label="scale 1.10x = 0.10")
    ax.set_xscale("log", base=2)
    ax.set_xticks(QS)
    ax.set_xticklabels([str(q) for q in QS])
    ax.set_xlabel("sampled coordinates q")
    ax.set_ylabel("SignRadial honest score (p99)")
    ax.set_title("P2a: honest noise floor falls ~1/sqrt(q), scale signal is constant")
    ax.legend(fontsize=9)
    ax.grid(True, ls="--", alpha=0.3)
    fig.savefig(FIG / "fig5_q_scaling.png", dpi=200)
    plt.close(fig)

    # fig6: u_i histogram
    hu, su, sd = ui_histogram()
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    for ax, data, title in [
        (axes[0], hu, "honest heterogeneous (u_i = sign(x)e)"),
        (axes[1], su, "scale 1.10x (u_i >= 0, one-sided)"),
        (axes[2], sd, "scale 0.90x (u_i <= 0, one-sided)"),
    ]:
        ax.hist(data, bins=80, color="#2563eb", alpha=0.7)
        ax.axvline(0, color="black", lw=1)
        ax.set_title(title)
        ax.set_xlabel("u_i = sign(x_i)(y_i-x_i)")
        if ax is axes[0]:
            ax.set_ylabel("count")
    fig.suptitle("P2a: cancellation mechanism — honest u_i is zero-centered, scale u_i is one-sided", fontsize=13)
    fig.savefig(FIG / "fig6_ui_hist.png", dpi=200)
    plt.close(fig)

    print("saved fig5_q_scaling.png, fig6_ui_hist.png")


if __name__ == "__main__":
    main()

