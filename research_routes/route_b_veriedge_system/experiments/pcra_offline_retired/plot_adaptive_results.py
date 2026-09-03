#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PCRA_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot aggregate adaptive-attack detection rates.")
    parser.add_argument(
        "--input",
        type=Path,
        default=PCRA_DIR / "results" / "adaptive_harm_preserving" / "adaptive_rates.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PCRA_DIR / "results" / "adaptive_harm_preserving" / "adaptive_detection.png",
    )
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["statistic"] == "combined"]

    grouped: dict[tuple[int, float, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["q"]), float(row["rho"]), row["attack"])].append(
            float(row["test_rate"])
        )
    q_values = sorted({key[0] for key in grouped})
    strengths = sorted({key[1] for key in grouped if key[1] > 0})
    styles = {
        "adaptive_joint": ("Adaptive joint", "#1F4E46", "o"),
        "fixed_sparse16": ("Fixed 16-sparse", "#777777", "s"),
        "fixed_diffuse": ("Fixed diffuse", "#78A890", "^"),
        "fixed_directional": ("Fixed directional", "#B0B0B0", "D"),
    }

    fig, axes = plt.subplots(1, len(strengths), figsize=(11.2, 3.6), sharey=True)
    for axis, rho in zip(axes, strengths):
        honest = [np.mean(grouped[(q, 0.0, "honest")]) for q in q_values]
        axis.plot(q_values, honest, "--", color="#444444", linewidth=1.2, label="Honest FPR")
        for attack, (label, color, marker) in styles.items():
            values = [np.mean(grouped[(q, rho, attack)]) for q in q_values]
            axis.plot(
                q_values,
                values,
                color=color,
                marker=marker,
                linewidth=1.5,
                markersize=4,
                label=label,
            )
        axis.set_title(f"rho = {rho:g}")
        axis.set_xlabel("post-commit opening size q")
        axis.set_xticks(q_values)
        axis.set_ylim(-0.02, 1.02)
        axis.grid(True, alpha=0.25, linewidth=0.6)
    axes[0].set_ylabel("mean detection rate / honest FPR")
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, frameon=False, fontsize=8)
    fig.suptitle("White-box non-anticipating attack on the three-statistic check", y=0.98)
    fig.tight_layout(rect=(0, 0.14, 1, 0.92))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
