from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
FIGURE_DIR = REPO_ROOT / "paper1_veriedge" / "E1" / "figures"

PAIR_SPECS = [
    {
        "label": "M5 fp16 vs mini1 metal8",
        "summary_csv": REPO_ROOT
        / "paper1_veriedge"
        / "E1"
        / "logs"
        / "e1_paper_c1swap_tuned"
        / "exp_e1_20260502_e1_paper_c1swap_tuned_summary.csv",
        "delta_json": REPO_ROOT
        / "workspace"
        / "captures"
        / "E1"
        / "e1_paper_c1swap_delta"
        / "delta_map.json",
    },
    {
        "label": "mini1 fp16 vs mini1 metal8",
        "summary_csv": REPO_ROOT
        / "paper1_veriedge"
        / "E1"
        / "logs"
        / "e1_pair2_mini1fp16_vs_mini1metal8"
        / "exp_e1_20260502_e1_pair2_mini1fp16_vs_mini1metal8_summary.csv",
        "delta_json": REPO_ROOT
        / "workspace"
        / "captures"
        / "E1"
        / "e1_pair2_mini1fp16_vs_mini1metal8_delta"
        / "delta_map.json",
    },
    {
        "label": "M5 fp16 vs M5 metal8",
        "summary_csv": REPO_ROOT
        / "paper1_veriedge"
        / "E1"
        / "logs"
        / "e1_pair3_localm5fp16_vs_localm5metal8"
        / "exp_e1_20260502_e1_pair3_localm5fp16_vs_localm5metal8_summary.csv",
        "delta_json": REPO_ROOT
        / "workspace"
        / "captures"
        / "E1"
        / "e1_pair3_localm5fp16_vs_localm5metal8_delta"
        / "delta_map.json",
    },
]


def _read_summary_row(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"summary csv is empty: {path}")
    return rows[0]


def _read_delta_map(path: Path) -> Dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        checkpoint: float(value)
        for checkpoint, value in dict(payload.get("delta_map", {}).get("prefill", {})).items()
    }


def _soften_axis(ax: plt.Axes) -> None:
    ax.set_facecolor("#F8FAFC")
    ax.grid(axis="y", linestyle=(0, (3, 3)), linewidth=0.8, alpha=0.28, color="#64748B")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")


def build_plot() -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    labels: List[str] = []
    thc_fpr: List[float] = []
    tstc_fpr: List[float] = []
    c1_delta: List[float] = []
    c2_delta: List[float] = []
    c3_delta: List[float] = []

    for spec in PAIR_SPECS:
        summary = _read_summary_row(Path(spec["summary_csv"]))
        delta_map = _read_delta_map(Path(spec["delta_json"]))

        labels.append(str(spec["label"]))
        thc_fpr.append(float(summary["thc_fpr"]))
        tstc_fpr.append(float(summary["tstc_fpr"]))
        c1_delta.append(float(delta_map.get("C1", 0.0)))
        c2_delta.append(float(delta_map.get("C2", 0.0)))
        c3_delta.append(float(delta_map.get("C3", 0.0)))

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.8), constrained_layout=True)

    x = np.arange(len(labels))
    width = 0.34
    fpr_colors = {"thc": "#6B7280", "tstc": "#0F766E"}

    thc_bars = axes[0].bar(
        x - width / 2,
        thc_fpr,
        width=width,
        color=fpr_colors["thc"],
        edgecolor="white",
        linewidth=1.2,
        label="THC",
        zorder=3,
    )
    tstc_bars = axes[0].bar(
        x + width / 2,
        tstc_fpr,
        width=width,
        color=fpr_colors["tstc"],
        edgecolor="white",
        linewidth=1.2,
        label="TSTC",
        zorder=3,
    )
    for bars, values, color in (
        (thc_bars, thc_fpr, fpr_colors["thc"]),
        (tstc_bars, tstc_fpr, fpr_colors["tstc"]),
    ):
        for bar, value in zip(bars, values):
            axes[0].text(
                bar.get_x() + bar.get_width() / 2.0,
                value + 0.03,
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color=color,
            )
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=14, ha="right")
    axes[0].set_ylim(0.0, 1.12)
    axes[0].set_ylabel("False Positive Rate")
    axes[0].set_title("E1 Honest-Honest FPR")
    axes[0].legend(loc="upper right")
    _soften_axis(axes[0])

    width = 0.22
    delta_colors = {"C1": "#A16207", "C2": "#1D4ED8", "C3": "#BE185D"}
    bars_by_ckpt = [
        ("C1", c1_delta, x - width),
        ("C2", c2_delta, x),
        ("C3", c3_delta, x + width),
    ]
    for checkpoint, values, offsets in bars_by_ckpt:
        bars = axes[1].bar(
            offsets,
            values,
            width=width,
            color=delta_colors[checkpoint],
            edgecolor="white",
            linewidth=1.0,
            label=checkpoint,
            zorder=3,
        )
        for bar, value in zip(bars, values):
            axes[1].text(
                bar.get_x() + bar.get_width() / 2.0,
                value + max(0.02, value * 0.015),
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color=delta_colors[checkpoint],
            )
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=14, ha="right")
    axes[1].set_ylabel("Calibrated Delta")
    axes[1].set_title("E1 Prefill Delta Map")
    axes[1].legend(loc="upper right", ncol=3)
    _soften_axis(axes[1])

    fig.suptitle("Experiment 1: Real Honest-Honest Heterogeneous Pairs", fontsize=13, y=1.02)

    png_path = FIGURE_DIR / "e1_real_pairs_fpr_delta.png"
    pdf_path = FIGURE_DIR / "e1_real_pairs_fpr_delta.pdf"
    fig.savefig(png_path, dpi=240, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return png_path


def main() -> None:
    output_path = build_plot()
    print(f"Wrote E1 figure to {output_path}")


if __name__ == "__main__":
    main()
