from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = REPO_ROOT / "paper1_veriedge" / "E1" / "tables"
FIG_DIR = REPO_ROOT / "paper1_veriedge" / "E1" / "figures"

VARIANTS = [
    {
        "csv": TABLE_DIR / "table4_results.csv",
        "png": FIG_DIR / "table4_paired_capture_fpr_baseline.png",
        "pdf": FIG_DIR / "table4_paired_capture_fpr_baseline.pdf",
        "title": "Table 4 Cross-Device Paired-Capture Results (Baseline)",
    },
    {
        "csv": TABLE_DIR / "table4_results_tuned_current_mixed_p9999.csv",
        "png": FIG_DIR / "table4_paired_capture_fpr_tuned_current_mixed_p9999.png",
        "pdf": FIG_DIR / "table4_paired_capture_fpr_tuned_current_mixed_p9999.pdf",
        "title": "Table 4 Cross-Device Paired-Capture Results (Tuned Current Mixed Stack, p99.99)",
    },
]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _soften_axis(ax: plt.Axes) -> None:
    ax.set_facecolor("#F8FAFC")
    ax.grid(axis="y", linestyle=(0, (3, 3)), linewidth=0.8, alpha=0.28, color="#64748B")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")


def _plot_one(rows: list[dict[str, str]], title: str, png: Path, pdf: Path) -> None:
    labels = [row["actual_label"] for row in rows]
    thc = [float(row["thc_fpr"]) for row in rows]
    tstc = [float(row["tstc_fpr"]) for row in rows]

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )

    fig, ax = plt.subplots(figsize=(12.6, 5.6), constrained_layout=True)
    x = np.arange(len(labels))
    width = 0.34
    colors = {"thc": "#6B7280", "tstc": "#0F766E"}

    thc_bars = ax.bar(
        x - width / 2,
        thc,
        width=width,
        color=colors["thc"],
        edgecolor="white",
        linewidth=1.2,
        label="THC",
        zorder=3,
    )
    tstc_bars = ax.bar(
        x + width / 2,
        tstc,
        width=width,
        color=colors["tstc"],
        edgecolor="white",
        linewidth=1.2,
        label="TSTC",
        zorder=3,
    )

    for bars, values, color in (
        (thc_bars, thc, colors["thc"]),
        (tstc_bars, tstc, colors["tstc"]),
    ):
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                value + 0.03,
                f"{value:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
                color=color,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=14, ha="right")
    ax.set_ylim(0.0, 1.12)
    ax.set_ylabel("False Positive Rate")
    ax.set_title(title)
    ax.legend(loc="upper right")
    _soften_axis(ax)

    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=240, bbox_inches="tight")
    fig.savefig(pdf, dpi=240, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote figure to {png}")


def main() -> None:
    for variant in VARIANTS:
        rows = _read_rows(variant["csv"])
        if not rows:
            raise ValueError(f"empty csv: {variant['csv']}")
        _plot_one(rows, str(variant["title"]), Path(variant["png"]), Path(variant["pdf"]))


if __name__ == "__main__":
    main()
