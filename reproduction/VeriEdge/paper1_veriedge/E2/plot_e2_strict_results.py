from __future__ import annotations

import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
E2_DIR = REPO_ROOT / "paper1_veriedge" / "E2"
TABLE_DIR = E2_DIR / "tables"
FIG_DIR = E2_DIR / "figures"
OWNER = "strict_ab_mainline"


def _latest_stamp() -> str:
    pattern = re.compile(r"exp_e2_(\d{8})_" + re.escape(OWNER) + r"_samplesweep\.csv$")
    matches: list[str] = []
    for path in TABLE_DIR.glob(f"exp_e2_*_{OWNER}_samplesweep.csv"):
        m = pattern.match(path.name)
        if m:
            matches.append(m.group(1))
    if not matches:
        raise FileNotFoundError(f"no strict E2 tables found for owner={OWNER}")
    return sorted(matches)[-1]


STAMP = _latest_stamp()


def _read_csv(path: Path) -> list[dict[str, str]]:
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


def _save(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=240, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.pdf", dpi=240, bbox_inches="tight")
    plt.close(fig)


def plot_sample_sweep() -> None:
    rows = _read_csv(TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_samplesweep.csv")
    xs = [int(row["sample_size"]) for row in rows]
    homo_fpr = [float(row["honest_homo_tstc_fpr"]) for row in rows]
    hetero_fpr = [float(row["honest_hetero_tstc_fpr"]) for row in rows]
    tamper_tpr = [float(row["tamper_tstc_tpr"]) for row in rows]
    runtime = [float(row["honest_hetero_tstc_runtime_ms_per_trace"]) for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.6), constrained_layout=True)
    axes[0].plot(xs, hetero_fpr, marker="o", linewidth=2.3, color="#0F766E", label="honest hetero FPR")
    axes[0].plot(xs, homo_fpr, marker="o", linewidth=1.8, linestyle="--", color="#94A3B8", label="honest homo FPR")
    axes[0].set_xlabel("Sample Size")
    axes[0].set_ylabel("TSTC FPR")
    axes[0].legend(loc="upper left")
    _soften_axis(axes[0])

    axes[1].plot(xs, tamper_tpr, marker="o", linewidth=2.3, color="#B45309")
    axes[1].set_xlabel("Sample Size")
    axes[1].set_ylabel("TSTC TPR")
    _soften_axis(axes[1])

    axes[2].plot(xs, runtime, marker="o", linewidth=2.3, color="#1D4ED8")
    axes[2].set_xlabel("Sample Size")
    axes[2].set_ylabel("TSTC Runtime / Trace (ms)")
    _soften_axis(axes[2])
    axes[1].set_title("Strict E2 Sample-size Sweep")
    _save(fig, "e2_strict_sample_size_fpr_tpr_runtime")


def plot_percentile_sweep() -> None:
    rows = _read_csv(TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_percentilesweep.csv")
    checkpoint_rows = [row for row in rows if row["tolerance_mode"] == "checkpoint_specific"]
    global_rows = [row for row in rows if row["tolerance_mode"] == "global_shared"]
    xs_checkpoint = [float(row["percentile"]) for row in checkpoint_rows]
    xs_global = [float(row["percentile"]) for row in global_rows]
    hetero_fpr_checkpoint = [float(row["honest_hetero_tstc_fpr"]) for row in checkpoint_rows]
    hetero_fpr_global = [float(row["honest_hetero_tstc_fpr"]) for row in global_rows]
    tamper_tpr_checkpoint = [float(row["tamper_tstc_tpr"]) for row in checkpoint_rows]
    tamper_tpr_global = [float(row["tamper_tstc_tpr"]) for row in global_rows]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.6), constrained_layout=True)
    axes[0].plot(xs_checkpoint, hetero_fpr_checkpoint, marker="o", linewidth=2.3, color="#0F766E", label="checkpoint-specific")
    axes[0].plot(xs_global, hetero_fpr_global, marker="o", linewidth=2.0, linestyle="--", color="#1D4ED8", label="global shared")
    axes[0].set_xlabel("Calibration Percentile")
    axes[0].set_ylabel("TSTC FPR (honest hetero)")
    axes[0].legend(loc="upper right")
    _soften_axis(axes[0])

    axes[1].plot(xs_checkpoint, tamper_tpr_checkpoint, marker="o", linewidth=2.3, color="#B45309", label="checkpoint-specific")
    axes[1].plot(xs_global, tamper_tpr_global, marker="o", linewidth=2.0, linestyle="--", color="#7C3AED", label="global shared")
    axes[1].set_xlabel("Calibration Percentile")
    axes[1].set_ylabel("TSTC TPR (tamper)")
    axes[1].legend(loc="upper right")
    _soften_axis(axes[1])
    axes[0].set_title("Strict E2 Percentile Sweep")
    _save(fig, "e2_strict_percentile_fpr_tpr")


def plot_sampling_grid() -> None:
    rows = _read_csv(TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_sampling_grid.csv")
    labels = [f"{row['token_samples']}x{row['channel_samples']}" for row in rows]
    x = np.arange(len(labels))
    hetero_fpr = [float(row["honest_hetero_tstc_fpr"]) for row in rows]
    tamper_tpr = [float(row["tamper_tstc_tpr"]) for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8), constrained_layout=True)
    axes[0].bar(x, hetero_fpr, color="#0F766E")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=35, ha="right")
    axes[0].set_ylabel("TSTC FPR (honest hetero)")
    _soften_axis(axes[0])

    axes[1].bar(x, tamper_tpr, color="#B45309")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=35, ha="right")
    axes[1].set_ylabel("TSTC TPR (tamper)")
    _soften_axis(axes[1])
    axes[0].set_title("Strict E2 2D Sampling Grid")
    _save(fig, "e2_strict_sampling_grid_fpr_tpr")


def plot_tolerance_sweep() -> None:
    rows = _read_csv(TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_tolerancesweep.csv")
    xs = [float(row["tolerance_scale"]) for row in rows]
    homo_fpr = [float(row["honest_homo_tstc_fpr"]) for row in rows]
    hetero_fpr = [float(row["honest_hetero_tstc_fpr"]) for row in rows]
    tamper_tpr = [float(row["tamper_tstc_tpr"]) for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.6), constrained_layout=True)
    axes[0].plot(xs, hetero_fpr, marker="o", linewidth=2.3, color="#0F766E", label="honest hetero FPR")
    axes[0].plot(xs, homo_fpr, marker="o", linewidth=1.8, linestyle="--", color="#94A3B8", label="honest homo FPR")
    axes[0].set_xlabel("Tolerance Scale")
    axes[0].set_ylabel("TSTC FPR")
    axes[0].legend(loc="upper left")
    _soften_axis(axes[0])

    axes[1].plot(xs, tamper_tpr, marker="o", linewidth=2.3, color="#B45309")
    axes[1].set_xlabel("Tolerance Scale")
    axes[1].set_ylabel("TSTC TPR")
    _soften_axis(axes[1])
    axes[0].set_title("Strict E2 Tolerance-scale Sweep")
    _save(fig, "e2_strict_tolerance_scale_fpr_tpr")


def plot_global_vs_checkpoint() -> None:
    rows = _read_csv(TABLE_DIR / f"exp_e2_{STAMP}_{OWNER}_global_vs_checkpoint_delta.csv")
    labels = [row["tolerance_mode"] for row in rows]
    x = np.arange(len(labels))
    width = 0.24
    hetero_fpr = [float(row["honest_hetero_tstc_fpr"]) for row in rows]
    tamper_tpr = [float(row["tamper_tstc_tpr"]) for row in rows]
    tamper_loc = [float(row["tamper_tstc_locacc"]) for row in rows]

    fig, axes = plt.subplots(1, 3, figsize=(13.4, 4.6), constrained_layout=True)
    specs = [
        ("TSTC FPR (honest hetero)", hetero_fpr, "#0F766E"),
        ("TSTC TPR (tamper)", tamper_tpr, "#B45309"),
        ("TSTC LocAcc (tamper)", tamper_loc, "#1D4ED8"),
    ]
    for ax, (ylabel, ys, color) in zip(axes, specs):
        ax.bar(x, ys, width=0.55, color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel(ylabel)
        _soften_axis(ax)
    axes[1].set_title("Strict E2 Global vs Checkpoint-specific")
    _save(fig, "e2_strict_global_vs_checkpoint")


def main() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )
    plot_sample_sweep()
    plot_percentile_sweep()
    plot_sampling_grid()
    plot_tolerance_sweep()
    plot_global_vs_checkpoint()
    print(f"Wrote strict E2 figures to {FIG_DIR}")


if __name__ == "__main__":
    main()
