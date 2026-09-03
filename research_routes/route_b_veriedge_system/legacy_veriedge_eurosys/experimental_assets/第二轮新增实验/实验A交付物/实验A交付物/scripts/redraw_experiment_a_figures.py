from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "placement_summary.csv"
FIGURES = ROOT / "figures"

LABELS = {
    "network_aware_scalar": "N-scalar",
    "network_aware_projcos4": "N-proj4",
    "verif_constrained_projcos4": "VC-proj4",
    "network_aware_adaptive": "N-adapt",
    "adaptive_verifier": "Adaptive",
    "queue_aware_network": "Q-network",
    "queue_aware_verif_constrained": "Q-VC",
    "queue_aware_adaptive": "Q-adapt",
    "homogeneous_only": "Homo-only",
}

COLORS = {
    "network_aware_scalar": "#b35806",
    "network_aware_projcos4": "#e08214",
    "verif_constrained_projcos4": "#2b8cbe",
    "network_aware_adaptive": "#31a354",
    "adaptive_verifier": "#756bb1",
    "queue_aware_network": "#d95f0e",
    "queue_aware_verif_constrained": "#3182bd",
    "queue_aware_adaptive": "#238b45",
    "homogeneous_only": "#636363",
}

MARKERS = {
    "network_aware_scalar": "o",
    "network_aware_projcos4": "s",
    "verif_constrained_projcos4": "D",
    "network_aware_adaptive": "^",
    "adaptive_verifier": "P",
    "queue_aware_network": "o",
    "queue_aware_verif_constrained": "D",
    "queue_aware_adaptive": "^",
    "homogeneous_only": "X",
}


def read_rows() -> list[dict[str, str]]:
    with SUMMARY.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def row_for(rows: list[dict[str, str]], policy: str, alpha: float = 0.10) -> dict[str, str]:
    return next(
        r
        for r in rows
        if r["workload"] == "queued-8"
        and r["policy"] == policy
        and abs(float(r["alpha"]) - alpha) < 1e-9
    )


def plot_frontier(rows: list[dict[str, str]]) -> None:
    mechanism = [
        "network_aware_scalar",
        "network_aware_projcos4",
        "verif_constrained_projcos4",
        "network_aware_adaptive",
        "adaptive_verifier",
        "homogeneous_only",
    ]
    queue = [
        "queue_aware_network",
        "queue_aware_verif_constrained",
        "queue_aware_adaptive",
    ]
    mechanism_offsets = {
        "network_aware_scalar": (-62, 14),
        "network_aware_projcos4": (-62, -16),
        "verif_constrained_projcos4": (10, -18),
        "network_aware_adaptive": (-72, 0),
        "adaptive_verifier": (10, 10),
        "homogeneous_only": (-84, 0),
    }
    queue_offsets = {
        "queue_aware_network": (10, 16),
        "queue_aware_verif_constrained": (10, -20),
        "queue_aware_adaptive": (10, 0),
    }

    def draw_one(name: str, policies: list[str], offsets: dict[str, tuple[int, int]], filename: str, xlim: tuple[float, float]) -> None:
        fig, ax = plt.subplots(figsize=(7.4, 4.8))
        for policy in policies:
            r = row_for(rows, policy)
            x = float(r["latency_median_s"])
            y = float(r["false_risk_mean"])
            ax.scatter(
                x,
                y,
                s=105,
                marker=MARKERS[policy],
                color=COLORS[policy],
                edgecolor="white",
                linewidth=0.8,
                zorder=3,
            )
            ax.annotate(
                LABELS[policy],
                (x, y),
                xytext=offsets[policy],
                textcoords="offset points",
                fontsize=8,
                arrowprops={"arrowstyle": "-", "lw": 0.55, "color": "0.45"},
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "0.72", "alpha": 0.94},
            )
        ax.set_xlabel("Median latency (s)")
        ax.set_ylabel("Expected false-dispute risk")
        ax.set_title(name)
        ax.set_xlim(*xlim)
        ax.set_ylim(-0.0009, 0.0183)
        ax.grid(True, linewidth=0.35, alpha=0.65)
        fig.tight_layout()
        fig.savefig(FIGURES / f"{filename}.png", dpi=220, bbox_inches="tight")
        fig.savefig(FIGURES / f"{filename}.pdf", bbox_inches="tight")
        plt.close(fig)

    draw_one(
        "A1 placement frontier at queued-8, alpha=0.10",
        mechanism,
        mechanism_offsets,
        "fig_placement_frontier_a1",
        (78, 126),
    )
    draw_one(
        "A3 queue-aware frontier at queued-8, alpha=0.10",
        queue,
        queue_offsets,
        "fig_placement_frontier_a3_queue",
        (4.5, 7.7),
    )


def plot_alpha(rows: list[dict[str, str]]) -> None:
    groups = [
        (
            "A1 mechanism policies",
            [
                "network_aware_scalar",
                "network_aware_projcos4",
                "verif_constrained_projcos4",
                "network_aware_adaptive",
                "adaptive_verifier",
            ],
        ),
        (
            "A3 queue-aware policies",
            [
                "queue_aware_network",
                "queue_aware_verif_constrained",
                "queue_aware_adaptive",
            ],
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8), sharey=True)
    for ax, (title, policies) in zip(axes, groups):
        for policy in policies:
            series = [
                r
                for r in rows
                if r["workload"] == "queued-8" and r["policy"] == policy
            ]
            series = sorted(series, key=lambda r: float(r["alpha"]))
            xs = [float(r["alpha"]) for r in series]
            ys = [float(r["infeasible_rate"] or 0.0) for r in series]
            ax.plot(
                xs,
                ys,
                marker=MARKERS[policy],
                linewidth=2.0,
                color=COLORS[policy],
                label=LABELS[policy],
            )
        ax.set_title(title)
        ax.set_xlabel("False-dispute target alpha")
        ax.set_xlim(0.045, 0.205)
        ax.set_ylim(-0.05, 1.08)
        ax.grid(True, linewidth=0.35, alpha=0.65)
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.20),
            ncol=2,
            fontsize=8,
            frameon=False,
            handlelength=2.2,
            columnspacing=1.1,
        )
    axes[0].set_ylabel("Infeasible usage rate")
    fig.suptitle("Alpha sensitivity: stricter targets increase baseline infeasibility", y=1.02, fontsize=12)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(FIGURES / "fig_alpha_sensitivity_infeasible.png", dpi=220, bbox_inches="tight")
    fig.savefig(FIGURES / "fig_alpha_sensitivity_infeasible.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_risk_composition(rows: list[dict[str, str]]) -> None:
    policies = [
        "network_aware_scalar",
        "network_aware_projcos4",
        "verif_constrained_projcos4",
        "network_aware_adaptive",
        "adaptive_verifier",
        "queue_aware_network",
        "queue_aware_verif_constrained",
        "queue_aware_adaptive",
        "homogeneous_only",
    ]
    selected = [row_for(rows, p) for p in policies]
    labels = [LABELS[r["policy"]] for r in selected]
    low = [float(r["low_risk_share"] or 0.0) for r in selected]
    infeasible = [float(r["infeasible_rate"] or 0.0) for r in selected]
    other = [max(0.0, 1.0 - l - i) for l, i in zip(low, infeasible)]

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.barh(labels, low, label="low-risk", color="#2ca25f")
    ax.barh(labels, other, left=low, label="other admitted", color="#bdbdbd")
    ax.barh(labels, infeasible, left=[l + o for l, o in zip(low, other)], label="infeasible", color="#de2d26")
    ax.set_xlabel("Share of selected placements")
    ax.set_title("Risk-class composition at queued-8, alpha=0.10")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, axis="x", linewidth=0.35, alpha=0.65)
    fig.tight_layout()
    fig.savefig(FIGURES / "fig_risk_class_composition.png", dpi=220, bbox_inches="tight")
    fig.savefig(FIGURES / "fig_risk_class_composition.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    plot_frontier(rows)
    plot_alpha(rows)
    plot_risk_composition(rows)


if __name__ == "__main__":
    main()
