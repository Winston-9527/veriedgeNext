"""Plot SRR vs baseline results.

Produces three figures from results/srr_vs_baseline.csv:
- fig1_scale_tpr_bar.png : scale-attack TPR by variant, grouped by pair.
- fig2_fpr_vs_scale_tpr.png: honest FPR vs scale TPR scatter (the go/no-go plane).
- fig3_cost.png          : ops / reads / ref-bytes per variant (structural cost).
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
RESULTS = HERE / "results"
FIG = HERE / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def load() -> list[dict]:
    with (RESULTS / "srr_vs_baseline.csv").open() as f:
        return list(csv.DictReader(f))


def f(x): return float(x)


def main() -> None:
    rows = load()
    pairs = ["A/B", "A/C", "A/D", "B/D"]
    variants = ["scalar16", "scalar64", "projscalar1_abs", "projcos4", "projcos8", "projcos16", "SRR-32", "SRR-64", "SRR-128"]

    # ---- fig1: scale TPR bar by pair ----
    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    x = np.arange(len(pairs))
    width = 0.10
    colors = {
        "scalar16": "#64748b", "scalar64": "#94a3b8",
        "projscalar1_abs": "#059669", "projcos4": "#ea580c", "projcos8": "#f97316",
        "projcos16": "#fb923c", "SRR-32": "#4338ca", "SRR-64": "#4f46e5", "SRR-128": "#6366f1",
    }
    for i, v in enumerate(variants):
        vals = [f(next(r for r in rows if r["pair"] == p and r["variant"] == v)["tpr_scale"]) for p in pairs]
        ax.bar(x + (i - len(variants)/2) * width, vals, width, label=v, color=colors[v])
    ax.set_xticks(x); ax.set_xticklabels(pairs)
    ax.set_ylabel("Scale-attack TPR (1.10x, C2)")
    ax.set_ylim(0, 1.05)
    ax.axhline(0.9, color="red", ls="--", lw=1, label="0.9 target")
    ax.legend(ncol=3, fontsize=8)
    ax.set_title("Scale-attack detection: SRR vs baselines (higher is better)")
    fig.savefig(FIG / "fig1_scale_tpr_bar.png", dpi=200)
    plt.close(fig)

    # ---- fig2: FPR vs scale-TPR scatter (go/no-go plane) ----
    fig, ax = plt.subplots(figsize=(9, 7), constrained_layout=True)
    for v in variants:
        xs, ys = [], []
        for p in pairs:
            r = next(r for r in rows if r["pair"] == p and r["variant"] == v)
            xs.append(f(r["eval_hetero_fpr"])); ys.append(f(r["tpr_scale"]))
        ax.scatter(xs, ys, s=90, label=v, color=colors[v], edgecolor="black", linewidth=0.5, zorder=3)
        for p, xv, yv in zip(pairs, xs, ys):
            ax.annotate(p, (xv, yv), textcoords="offset points", xytext=(5, 5), fontsize=7)
    ax.axhline(0.9, color="red", ls="--", lw=1)
    ax.axvline(0.10, color="red", ls="--", lw=1)
    ax.set_xlabel("Honest-hetero FPR (held-out)")
    ax.set_ylabel("Scale-attack TPR (1.10x)")
    ax.set_title("SRR go/no-go plane: need FPR≤0.10 AND scale TPR≥0.9 (lower-left quadrant)")
    ax.set_xlim(-0.02, 0.65); ax.set_ylim(-0.02, 1.05)
    ax.legend(ncol=3, fontsize=8)
    fig.savefig(FIG / "fig2_fpr_vs_scale_tpr.png", dpi=200)
    plt.close(fig)

    # ---- fig3: cost comparison ----
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2), constrained_layout=True)
    cost = {
        "scalar16": (16*2, 16, 64), "scalar64": (64*2, 64, 256),
        "projscalar1_abs": (16*1024*1, 16, 64), "projcos4": (16*1024*4, 16*1024, 256),
        "projcos8": (16*1024*8, 16*1024, 512), "projcos16": (16*1024*16, 16*1024, 1024),
        "SRR-32": (32*5, 32, 64), "SRR-64": (64*5, 64, 128), "SRR-128": (128*5, 128, 256),
    }
    labels = variants
    for ax, key, ylabel in zip(axes, ["ops", "reads", "bytes"], ["Arith ops / tensor", "Activation reads / tensor", "Ref bytes / checkpoint"]):
        vals = [cost[v][["ops", "reads", "bytes"].index(key)] for v in labels]
        ax.bar(labels, vals, color=[colors[v] for v in labels])
        ax.set_yscale("log")
        ax.set_ylabel(ylabel)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_title(f"Cost ({key})")
    fig.suptitle("Structural cost: SRR vs baselines (log scale)")
    fig.savefig(FIG / "fig3_cost.png", dpi=200)
    plt.close(fig)

    print("figures written to", FIG)


if __name__ == "__main__":
    main()
