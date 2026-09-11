from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
E4_DIR = REPO_ROOT / "paper1_veriedge" / "E4"
TABLE_DIR = E4_DIR / "tables"
FIG_DIR = E4_DIR / "figures"
STAMP = time.strftime("%Y%m%d")
OWNER = "strict_ab_mainline"
RUN_ID = f"exp_e4_{STAMP}_{OWNER}"

SUMMARY_CSV = TABLE_DIR / f"{RUN_ID}_overhead_summary.csv"
COMPARE_CSV = TABLE_DIR / f"{RUN_ID}_global_comparison.csv"


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _save(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=220, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.pdf", dpi=220, bbox_inches="tight")
    plt.close(fig)


def _soften_axis(ax: plt.Axes) -> None:
    ax.set_facecolor("#F8FAFC")
    ax.grid(axis="y", linestyle=(0, (3, 3)), linewidth=0.8, alpha=0.28, color="#64748B")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")


def _label(row: Dict[str, Any]) -> str:
    return f"{row['trace_label']}:{row['verifier']}"


def main() -> None:
    summary = _read_csv(SUMMARY_CSV)
    comparison = _read_csv(COMPARE_CSV)
    global_rows = [row for row in summary if row["tolerance_mode"] == "global_shared"]

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
        }
    )

    labels = [_label(row) for row in global_rows]
    x = np.arange(len(labels))

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8), constrained_layout=True)
    latency = [float(row["mean_challenge_latency_ms"]) for row in global_rows]
    replay = [float(row["mean_replay_ms"]) for row in global_rows]
    axes[0].bar(x, latency, color="#1D4ED8", label="challenge latency")
    axes[0].plot(x, replay, color="#B45309", marker="o", linewidth=2, label="replay")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=28, ha="right")
    axes[0].set_ylabel("Milliseconds")
    axes[0].set_title("Strict E4 Latency Breakdown (Global)")
    axes[0].legend(loc="upper left")
    _soften_axis(axes[0])

    storage = [float(row["mean_validator_storage_head_bytes"]) / 1024.0 for row in global_rows]
    capture_pair = [float(row["mean_capture_pair_total_bytes"]) / 1024.0 for row in global_rows]
    axes[1].bar(x, capture_pair, color="#0F766E", label="capture pair")
    axes[1].plot(x, storage, color="#7C3AED", marker="o", linewidth=2, label="validator storage head")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=28, ha="right")
    axes[1].set_ylabel("KiB")
    axes[1].set_title("Strict E4 Size / Storage (Global)")
    axes[1].legend(loc="upper left")
    _soften_axis(axes[1])
    _save(fig, f"{RUN_ID}_latency_storage")

    labels = [f"{row['trace_label']}:{row['verifier']}" for row in comparison]
    x = np.arange(len(labels))
    width = 0.36
    baseline = [float(row["baseline_detection_rate"]) for row in comparison]
    global_shared = [float(row["global_detection_rate"]) for row in comparison]

    fig, ax = plt.subplots(figsize=(10.8, 4.8), constrained_layout=True)
    ax.bar(x - width / 2, baseline, width=width, color="#C2410C", label="baseline")
    ax.bar(x + width / 2, global_shared, width=width, color="#1D4ED8", label="global")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=28, ha="right")
    ax.set_ylabel("Detection Rate")
    ax.set_title("Strict E4 Detection Rate: Baseline vs Global")
    ax.legend(loc="upper left")
    _soften_axis(ax)
    _save(fig, f"{RUN_ID}_detection_compare")

    print(FIG_DIR / f"{RUN_ID}_latency_storage.png")
    print(FIG_DIR / f"{RUN_ID}_detection_compare.png")


if __name__ == "__main__":
    main()
