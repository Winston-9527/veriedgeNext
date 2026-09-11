from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List, Sequence

import matplotlib.pyplot as plt


POLICY_ORDER = [
    "random",
    "cost_only",
    "reputation_aware",
    "network_aware",
    "risk_constrained",
    "adaptive_verifier",
]

POLICY_LABELS = {
    "random": "Random",
    "cost_only": "Cost only",
    "reputation_aware": "Reputation",
    "network_aware": "Network",
    "risk_constrained": "Risk constrained",
    "adaptive_verifier": "Adaptive verifier",
}

POLICY_COLORS = {
    "random": "#6b7280",
    "cost_only": "#c2410c",
    "reputation_aware": "#2563eb",
    "network_aware": "#0f766e",
    "risk_constrained": "#7c3aed",
    "adaptive_verifier": "#15803d",
}

RISK_COLORS = {
    "low_risk_placement_rate": "#15803d",
    "medium_risk_placement_rate": "#ca8a04",
    "high_risk_placement_rate": "#ea580c",
    "unverifiable_placement_rate": "#b91c1c",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot measured-profile E5 policy replay results")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--per-task", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prefix", required=True)
    return parser.parse_args()


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _ordered_workload_rows(rows: Sequence[Dict[str, Any]], workload_id: str) -> List[Dict[str, Any]]:
    filtered = [row for row in rows if str(row["workload_id"]) == workload_id]
    return sorted(filtered, key=lambda row: POLICY_ORDER.index(str(row["policy"])) if str(row["policy"]) in POLICY_ORDER else 99)


def _labels(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [POLICY_LABELS.get(str(row["policy"]), str(row["policy"])) for row in rows]


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def _plot_policy_compare(rows: Sequence[Dict[str, Any]], workload_id: str, output: Path) -> None:
    labels = _labels(rows)
    x = list(range(len(rows)))
    latency = [float(row["mean_task_latency_s"]) for row in rows]
    goodput = [float(row["goodput_success_per_s"]) for row in rows]
    false_risk = [float(row["false_dispute_risk"]) for row in rows]
    infeasible = [float(row["infeasible_under_alpha_beta_rate"]) for row in rows]
    risk_goodput = [float(row["risk_adjusted_goodput"]) for row in rows]
    workload = [float(row["mean_verifier_workload_ms_per_task"]) for row in rows]
    colors = [POLICY_COLORS.get(str(row["policy"]), "#475569") for row in rows]

    fig, axes = plt.subplots(2, 3, figsize=(15.5, 7.4), constrained_layout=True)
    panels = [
        (axes[0][0], latency, "Latency", "Mean task latency (s)", None),
        (axes[0][1], goodput, "Goodput", "Successful tasks / s", None),
        (axes[0][2], risk_goodput, "Risk-adjusted goodput", "Adjusted successful tasks / s", None),
        (axes[1][0], false_risk, "False dispute risk", "Mean selected FPR", (0.0, max(false_risk + [0.001]) * 1.25)),
        (axes[1][1], infeasible, "Infeasible placements", "Placement rate", (0.0, 1.0)),
        (axes[1][2], workload, "Verifier workload", "ms / task", None),
    ]
    for ax, values, title, ylabel, ylim in panels:
        ax.bar(x, values, color=colors, width=0.72)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x, labels, rotation=24, ha="right")
        ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
        if ylim is not None:
            ax.set_ylim(*ylim)

    fig.suptitle(f"Measured-profile E5 policy replay: {workload_id}", fontsize=14)
    _save(fig, output)


def _plot_pareto(rows: Sequence[Dict[str, Any]], workload_id: str, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.8), constrained_layout=True)

    for row in rows:
        policy = str(row["policy"])
        color = POLICY_COLORS.get(policy, "#475569")
        label = POLICY_LABELS.get(policy, policy)
        axes[0].scatter(float(row["goodput_success_per_s"]), float(row["false_dispute_risk"]), s=95, color=color, zorder=3)
        axes[0].annotate(label, (float(row["goodput_success_per_s"]), float(row["false_dispute_risk"])), xytext=(6, 6), textcoords="offset points", fontsize=8)
        axes[1].scatter(float(row["mean_task_latency_s"]), float(row["mean_verifier_workload_ms_per_task"]), s=95, color=color, zorder=3)
        axes[1].annotate(label, (float(row["mean_task_latency_s"]), float(row["mean_verifier_workload_ms_per_task"])), xytext=(6, 6), textcoords="offset points", fontsize=8)

    axes[0].set_title("Goodput vs verification risk")
    axes[0].set_xlabel("Goodput (successful tasks / s)")
    axes[0].set_ylabel("False dispute risk")
    axes[0].grid(True, linestyle="--", linewidth=0.6, alpha=0.35)

    axes[1].set_title("Latency vs verifier workload")
    axes[1].set_xlabel("Mean task latency (s)")
    axes[1].set_ylabel("Verifier workload (ms / task)")
    axes[1].grid(True, linestyle="--", linewidth=0.6, alpha=0.35)

    fig.suptitle(f"Measured-profile E5 Pareto view: {workload_id}", fontsize=14)
    _save(fig, output)


def _plot_risk_stack(rows: Sequence[Dict[str, Any]], workload_id: str, output: Path) -> None:
    labels = _labels(rows)
    x = list(range(len(rows)))
    bottoms = [0.0] * len(rows)
    fig, ax = plt.subplots(figsize=(11.5, 4.8), constrained_layout=True)
    risk_fields = [
        ("low_risk_placement_rate", "Low-risk"),
        ("medium_risk_placement_rate", "Medium-risk"),
        ("high_risk_placement_rate", "High-risk"),
        ("unverifiable_placement_rate", "Unverifiable"),
    ]
    for field, label in risk_fields:
        vals = [float(row[field]) for row in rows]
        ax.bar(x, vals, bottom=bottoms, color=RISK_COLORS[field], label=label, width=0.72)
        bottoms = [bottom + val for bottom, val in zip(bottoms, vals)]
    ax.set_ylim(0.0, 1.0)
    ax.set_title(f"Risk-class usage: {workload_id}")
    ax.set_ylabel("Placement rate")
    ax.set_xticks(x, labels, rotation=24, ha="right")
    ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.17))
    _save(fig, output)


def _placement_mix(per_task_rows: Sequence[Dict[str, Any]], workload_id: str, policy: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in per_task_rows:
        if str(row["workload_id"]) != workload_id or str(row["policy"]) != policy:
            continue
        key = f"{row['pair_id']} / {row['variant']}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _write_mix_table(per_task_rows: Sequence[Dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    workloads = sorted({str(row["workload_id"]) for row in per_task_rows})
    fields = ["workload_id", "policy", "placement_key", "count", "rate"]
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for workload_id in workloads:
            for policy in POLICY_ORDER:
                counts = _placement_mix(per_task_rows, workload_id, policy)
                total = sum(counts.values())
                for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                    writer.writerow(
                        {
                            "workload_id": workload_id,
                            "policy": policy,
                            "placement_key": key,
                            "count": count,
                            "rate": round(count / total, 6) if total else 0.0,
                        }
                    )


def main() -> None:
    args = _parse_args()
    summary_rows = _read_csv(Path(args.summary))
    per_task_rows = _read_csv(Path(args.per_task))
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    workloads = sorted({str(row["workload_id"]) for row in summary_rows})
    for workload_id in workloads:
        rows = _ordered_workload_rows(summary_rows, workload_id)
        _plot_policy_compare(rows, workload_id, output_dir / f"{args.prefix}_{workload_id}_policy_compare.png")
        _plot_pareto(rows, workload_id, output_dir / f"{args.prefix}_{workload_id}_pareto.png")
        _plot_risk_stack(rows, workload_id, output_dir / f"{args.prefix}_{workload_id}_risk_stack.png")

    mix_table = output_dir.parent / "tables" / f"{args.prefix}_placement_mix.csv"
    _write_mix_table(per_task_rows, mix_table)

    print(mix_table)
    for workload_id in workloads:
        print(output_dir / f"{args.prefix}_{workload_id}_policy_compare.png")
        print(output_dir / f"{args.prefix}_{workload_id}_pareto.png")
        print(output_dir / f"{args.prefix}_{workload_id}_risk_stack.png")


if __name__ == "__main__":
    main()
