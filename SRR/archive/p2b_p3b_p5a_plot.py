"""Generate figures for P2b, P2b2, P3b, P5a experiments.

- fig7_p2b_balanced_channel.png : SignRadial vs ProjCos TPR vs balanced per-channel scale
- fig8_p2b2_token_scale.png    : SignRadial vs ProjCos TPR vs per-token scale amplitude
- fig9_p3b_partial_replay.png  : SignRadial vs ProjCos TPR vs p_replay
- fig10_p5a_layerwise.png      : honest SignRadial p50/p90/p99 per layer (C1/C2/C3)
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

from run_srr_offline import load_split, MAIN, PAIRS
from radial import sign_radial, sign_radial_stat
from attacks import (
    inject_per_channel_scale, inject_per_token_scale, inject_partial_replay,
)
from baselines import baseline_detect, calibrate_proj_delta

FIG = HERE / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

Q = 256
PCTL = 99.0
SC = 3.0
SEED = 1
CKPTS = ["C1", "C2", "C3"]
PAIR = "A/B"


def setup():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re))

    def calib_gamma(ck):
        ratios = []
        for pid in sorted(set(Lc) & set(Rc)):
            P, B = sign_radial_stat(Lc[pid][f"prefill__{ck}"], Rc[pid][f"prefill__{ck}"], SEED, n=Q)
            ratios.append(abs(P) / (B + 1e-12))
        return float(np.percentile(ratios, PCTL))

    gm = {c: calib_gamma(c) * SC for c in CKPTS}

    def srr_det(cand, ref):
        for ck in CKPTS:
            a, _, _, _ = sign_radial(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], SEED, n=Q, gamma=gm[ck])
            if a:
                return True
        return False

    d4 = calibrate_proj_delta(Lc, Rc, 99.0, 16, 4, 911, SEED, "tstc_projcos")
    sd4 = {"prefill": {c: d4["prefill"][c] * 1.5 for c in CKPTS}}

    def pc_det(cand, ref):
        ok, _ = baseline_detect("projcos4", cand, ref, SEED, sd4, 16, 0, 4, 911, "tstc_projcos")
        return ok

    return Re, eval_ids, srr_det, pc_det


def tpr(det, cand_fn, refs, ids):
    return sum(1 for pid in ids if det(cand_fn(refs[pid]), refs[pid])) / len(ids)


def main():
    Re, ids, srr, pc = setup()

    # P2b: balanced per-channel scaling
    pairs_b = [(1.1, 0.9), (1.2, 0.8), (1.3, 0.7), (1.5, 0.5)]
    s_b = [tpr(srr, lambda b, au=au, ad=ad: inject_per_channel_scale(b, au, ad, SEED), Re, ids) for au, ad in pairs_b]
    p_b = [tpr(pc, lambda b, au=au, ad=ad: inject_per_channel_scale(b, au, ad, SEED), Re, ids) for au, ad in pairs_b]

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    x = np.arange(len(pairs_b))
    w = 0.35
    ax.bar(x - w / 2, s_b, w, label="SignRadial", color="#059669")
    ax.bar(x + w / 2, p_b, w, label="ProjCos4", color="#ea580c")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{a}/{d}" for a, d in pairs_b])
    ax.set_xlabel("per-channel alpha (half up / half down)")
    ax.set_ylabel("TPR")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.9, color="red", ls="--", lw=1)
    ax.legend()
    ax.set_title("P2b: balanced per-channel scaling — SignRadial cancels, ProjCos recovers")
    fig.savefig(FIG / "fig7_p2b_balanced_channel.png", dpi=200)
    plt.close(fig)

    # P2b2: per-token scaling
    amps = [0.1, 0.2, 0.3]
    alphas = lambda amp: [1 + amp if i % 2 == 0 else 1 - amp for i in range(32)]
    s_t = [tpr(srr, lambda b, a=amp: inject_per_token_scale(b, alphas(a), "C2"), Re, ids) for amp in amps]
    p_t = [tpr(pc, lambda b, a=amp: inject_per_token_scale(b, alphas(a), "C2"), Re, ids) for amp in amps]

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    x = np.arange(len(amps))
    ax.bar(x - w / 2, s_t, w, label="SignRadial", color="#059669")
    ax.bar(x + w / 2, p_t, w, label="ProjCos4", color="#ea580c")
    ax.set_xticks(x)
    ax.set_xticklabels([f"amp={a:.1f}" for a in amps])
    ax.set_xlabel("per-token scale amplitude (alternating)")
    ax.set_ylabel("TPR")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.9, color="red", ls="--", lw=1)
    ax.legend()
    ax.set_title("P2b2: per-token scaling (alternating alpha) — both weak")
    fig.savefig(FIG / "fig8_p2b2_token_scale.png", dpi=200)
    plt.close(fig)

    # P3b: partial replay
    prs = [0.10, 0.25, 0.50, 0.75, 1.0]
    s_r = [tpr(srr, lambda b, p=pr: inject_partial_replay(b, Re["eval_002"], p, SEED), Re, ids) for pr in prs]
    p_r = [tpr(pc, lambda b, p=pr: inject_partial_replay(b, Re["eval_002"], p, SEED), Re, ids) for pr in prs]

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    ax.plot([p * 100 for p in prs], s_r, "o-", label="SignRadial", color="#059669", lw=2)
    ax.plot([p * 100 for p in prs], p_r, "s--", label="ProjCos4", color="#ea580c", lw=2)
    ax.set_xlabel("p_replay (% tokens from previous prompt)")
    ax.set_ylabel("TPR")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.9, color="red", ls="--", lw=1)
    ax.legend()
    ax.set_title("P3b: partial replay — 10% token replay already detected")
    fig.savefig(FIG / "fig9_p3b_partial_replay.png", dpi=200)
    plt.close(fig)

    # P5a: layer-wise honest p99
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re_ = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re_))
    stats = {}
    for ck in CKPTS:
        hon = []
        for pid in eval_ids:
            P, B = sign_radial_stat(Le[pid][f"prefill__{ck}"], Re_[pid][f"prefill__{ck}"], SEED, n=Q)
            hon.append(abs(P) / (B + 1e-12))
        h = np.array(hon)
        stats[ck] = [np.percentile(h, 50), np.percentile(h, 90), np.percentile(h, 99), h.max()]

    fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
    cks = CKPTS
    pcts = ["p50", "p90", "p99", "max"]
    colors = ["#94a3b8", "#64748b", "#1d4ed8", "#dc2626"]
    x = np.arange(len(cks))
    for i, p in enumerate(pcts):
        ax.plot(x, [stats[c][i] for c in cks], "o-", label=p, color=colors[i], lw=2)
    ax.axhline(0.10, color="red", ls="--", lw=1.5, label="scale 1.10x = 0.10")
    ax.set_xticks(x)
    ax.set_xticklabels(cks)
    ax.set_xlabel("checkpoint (layer position)")
    ax.set_ylabel("SignRadial honest score")
    ax.set_yscale("log")
    ax.legend()
    ax.set_title("P5a: honest SignRadial per layer — needs per-layer gamma (8.7x spread)")
    fig.savefig(FIG / "fig10_p5a_layerwise.png", dpi=200)
    plt.close(fig)

    print("saved fig7_p2b_balanced_channel.png, fig8_p2b2_token_scale.png, fig9_p3b_partial_replay.png, fig10_p5a_layerwise.png")


if __name__ == "__main__":
    main()
