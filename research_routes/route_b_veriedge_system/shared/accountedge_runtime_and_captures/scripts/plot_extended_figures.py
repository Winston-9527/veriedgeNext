#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PDF_METADATA = {
    "Creator": "anonymous artifact",
    "Producer": "anonymous artifact",
    "CreationDate": None,
    "ModDate": None,
}


POLICY_LABELS = {
    "adaptive_verifier": "adaptive",
    "cost_only_scalar": "cost only",
    "homogeneous_only": "homogeneous",
    "network_aware_adaptive": "network adaptive",
    "network_aware_projcos4": "network projcos4",
    "network_aware_scalar": "network scalar",
    "queue_aware_adaptive": "queue adaptive",
    "queue_aware_network": "queue network",
    "queue_aware_verif_constrained": "queue verif.",
    "random": "random",
    "risk_weighted_scalar": "risk weighted",
    "verif_constrained_projcos4": "verif. projcos4",
}


def first_existing(df: pd.DataFrame, candidates: list[str]) -> str:
    for name in candidates:
        if name in df.columns:
            return name
    raise KeyError(f"missing expected column; tried {candidates}")


def save(fig, out_dir: Path, name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.pdf", metadata={**PDF_METADATA, "Title": name}, bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def label_policy(value: str) -> str:
    return POLICY_LABELS.get(value, value.replace("_", " "))


def plot_placement_replay(root: Path, out: Path):
    df = pd.read_csv(root / "placement_summary.csv")
    focus = df[(df["workload"] == "queued-8") & (df["alpha"].round(3) == 0.10)].copy()
    if focus.empty:
        focus = df.copy()
    focus["label"] = focus["policy"].map(label_policy)
    focus = focus.sort_values(["infeasible_usage", "false_risk", "policy"], ascending=[False, False, True])

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.6), constrained_layout=True)
    axes[0].barh(focus["label"], focus["infeasible_usage"], color="#d59a3a")
    axes[0].axvline(0.05, color="#333333", linestyle="--", linewidth=1.0, label="5% reference")
    axes[0].invert_yaxis()
    axes[0].set_title("Admission before disclosure")
    axes[0].set_xlabel("Infeasible placement usage")
    axes[0].grid(axis="x", linewidth=0.3)
    axes[0].legend(fontsize=8, loc="lower right")

    axes[1].barh(focus["label"], focus["false_risk"], color="#63aa9c")
    axes[1].invert_yaxis()
    axes[1].set_title("Risk after policy filtering")
    axes[1].set_xlabel("Expected false-dispute risk")
    axes[1].tick_params(axis="y", labelleft=False)
    axes[1].grid(axis="x", linewidth=0.3)
    fig.suptitle("Placement replay under verifier constraints", fontsize=14)
    save(fig, out, "fig_placement_replay")


def plot_risk_class_composition(root: Path, out: Path):
    df = pd.read_csv(root / "verifier_profiles.csv")
    table = pd.crosstab(df["sketch"], df["risk_class"])
    order = [c for c in ["low-risk", "medium-risk", "high-risk", "inadjudicable"] if c in table.columns]
    table = table[order] if order else table
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    colors = ["#5aa469", "#e0a33a", "#cf5c57", "#8a8a8a"]
    table.plot(kind="bar", stacked=True, ax=ax, color=colors[: len(table.columns)])
    ax.set_title("Verifier profile risk-class composition")
    ax.set_xlabel("Sketch variant")
    ax.set_ylabel("Profile count")
    ax.grid(axis="y", linewidth=0.3)
    ax.legend(title="Risk class", fontsize=8)
    fig.tight_layout()
    save(fig, out, "fig_risk_class_composition")


def plot_delivery_sweep(root: Path, out: Path):
    df = pd.read_csv(root / "delivery_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.0), constrained_layout=True)
    for scheme, color in [("RPD", "#3b6ea8"), ("PPD", "#e07a2d")]:
        g = df[(df["scheme"] == scheme) & (df["network"] == "WAN")].sort_values("k")
        axes[0].plot(g["k"], g["median_all_ready_ms"] / 1000, marker="o", label=scheme, color=color)
        axes[0].fill_between(g["k"], g["median_all_ready_ms"] / 1000, g["p95_all_ready_ms"] / 1000, alpha=0.14, color=color)
    axes[0].set_title("WAN delivery latency")
    axes[0].set_xlabel("Selected group size k")
    axes[0].set_ylabel("All-ready latency (s)")
    axes[0].grid(True, linewidth=0.3)
    axes[0].legend(fontsize=8)

    for scheme, color in [("RPD", "#3b6ea8"), ("PPD", "#e07a2d")]:
        g = df[(df["scheme"] == scheme) & (df["network"] == "LAN")].sort_values("k")
        axes[1].plot(g["k"], g["requester_egress_mb"], marker="o", label=scheme, color=color)
    axes[1].set_title("Requester egress")
    axes[1].set_xlabel("Selected group size k")
    axes[1].set_ylabel("Requester egress (MB)")
    axes[1].grid(True, linewidth=0.3)
    axes[1].legend(fontsize=8)
    save(fig, out, "fig_delivery_sweep")


def plot_delivery_scaling(root: Path, out: Path):
    df = pd.read_csv(root / "delivery_summary.csv")
    ppd = df[df["scheme"] == "PPD"].sort_values(["network", "k"])
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    for network, g in ppd.groupby("network"):
        ax.plot(g["k"], g["egress_reduction_vs_rpd_pct"], marker="o", label=f"{network} egress")
        ax.plot(g["k"], g["reduction_vs_rpd_pct"], marker="s", linestyle="--", label=f"{network} latency")
    ax.set_title("PPD benefit grows with group width")
    ax.set_xlabel("Selected group size k")
    ax.set_ylabel("Reduction vs RPD (%)")
    ax.grid(True, linewidth=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, out, "fig_delivery_scaling")


def plot_delivery_live_store(root: Path, out: Path):
    df = pd.read_csv(root / "delivery_live_store_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), constrained_layout=True)
    for mode, color in [("RPD", "#3b6ea8"), ("PPD", "#e07a2d")]:
        g = df[df["mode"] == mode].sort_values("group_size")
        axes[0].plot(g["group_size"], g["median_ms"], marker="o", label=mode, color=color)
        axes[1].plot(g["group_size"], g["requester_egress_mb_mean"], marker="o", label=mode, color=color)
    axes[0].set_title("Live local-store latency")
    axes[0].set_xlabel("Selected group size k")
    axes[0].set_ylabel("All-ready latency (ms)")
    axes[0].grid(True, linewidth=0.3)
    axes[1].set_title("Live local-store requester egress")
    axes[1].set_xlabel("Selected group size k")
    axes[1].set_ylabel("Requester egress (MB)")
    axes[1].grid(True, linewidth=0.3)
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8)
    save(fig, out, "fig_delivery_live_store")


def plot_material_tamper_focus(ext: Path, out: Path):
    df = pd.read_csv(ext / "material_tamper_attack_summary.csv")
    attacks = ["gaussian", "cross_prompt_stale_substitution", "wrong_shard_output", "layer_skip", "scale_perturbation"]
    variants = ["scalar16", "projcos4", "projcos16"]
    focus = df[df["attack_family"].isin(attacks) & df["variant"].isin(variants)].copy()
    pivot = focus.groupby(["attack_family", "variant"])["detection_rate"].mean().unstack("variant").reindex(attacks)
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    pivot.plot(kind="bar", ax=ax)
    ax.set_title("Material tamper detection by attack family")
    ax.set_xlabel("Attack family")
    ax.set_ylabel("Mean TPR")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", linewidth=0.3)
    ax.legend(title="Verifier", fontsize=8)
    ax.set_xticklabels([x.replace("_", "\n") for x in pivot.index], rotation=0)
    fig.tight_layout()
    save(fig, out, "fig_material_tamper_focus")


def plot_material_strength(ext: Path, out: Path):
    df = pd.read_csv(ext / "material_tamper_strength_sweep.csv")
    focus = df[df["attack_family"].isin(["gaussian", "scale_perturbation"]) & df["variant"].isin(["scalar16", "projcos4"])].copy()
    grouped = focus.groupby(["attack_family", "variant", "attack_strength"])["detection_rate"].mean().reset_index()
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), constrained_layout=True, sharey=True)
    for ax, attack in zip(axes, ["gaussian", "scale_perturbation"]):
        sub = grouped[grouped["attack_family"] == attack]
        for variant, g in sub.groupby("variant"):
            ax.plot(g["attack_strength"], g["detection_rate"], marker="o", label=variant)
        ax.set_title(attack.replace("_", " "))
        ax.set_xlabel("Attack strength")
        ax.grid(True, linewidth=0.3)
    axes[0].set_ylabel("Mean TPR")
    axes[1].legend(fontsize=8)
    save(fig, out, "fig_material_tamper_strength_sweep")


def plot_projscalar_attack(ext: Path, out: Path):
    attack = pd.read_csv(ext / "projscalar_attack_summary.csv")
    sweep = pd.read_csv(ext / "projscalar_strength_sweep_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.0), constrained_layout=True)
    axes[0].barh(attack["attack_family"].str.replace("_", " "), attack["mean_detection_rate"], color="#4b9c8e")
    axes[0].set_title("projscalar1_abs attack focus")
    axes[0].set_xlabel("Mean TPR")
    axes[0].set_xlim(0, 1.05)
    axes[0].grid(axis="x", linewidth=0.3)
    for family, g in sweep.groupby("attack_family"):
        axes[1].plot(g["attack_strength"], g["mean_detection_rate"], marker="o", label=family.replace("_", " "))
    axes[1].set_title("Strength sweep")
    axes[1].set_xlabel("Attack strength")
    axes[1].set_ylabel("Mean TPR")
    axes[1].set_ylim(0, 1.05)
    axes[1].grid(True, linewidth=0.3)
    axes[1].legend(fontsize=8)
    save(fig, out, "fig_projscalar_attack_sweep")


def plot_projscalar_stability(ext: Path, out: Path):
    pair = pd.read_csv(ext / "projscalar_multiseed_pair_summary.csv")
    labels = [f"P{i+1}" for i in range(len(pair))]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.bar(labels, pair["max_eval_fpr"], label="max FPR", color="#d59a3a")
    ax.plot(labels, pair["min_eval_tpr"], marker="o", color="#2f6f9f", label="min TPR")
    ax.set_title("projscalar1_abs multi-seed stability")
    ax.set_xlabel("Anonymous pair")
    ax.set_ylabel("Rate")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", linewidth=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, out, "fig_projscalar_multiseed_stability")


def plot_verifier_payload_latency(ext: Path, out: Path):
    df = pd.read_csv(ext / "verifier_payload_latency.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0), constrained_layout=True)
    axes[0].bar(df["variant"], df["signature_bytes_per_checkpoint_fp32"], color="#5c7ea8")
    axes[0].set_title("Signature payload")
    axes[0].set_ylabel("Bytes per checkpoint")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].grid(axis="y", linewidth=0.3)
    axes[1].bar(df["variant"], df["tamper_challenge_latency_ms"], color="#c57f42")
    axes[1].set_title("Challenge latency")
    axes[1].set_ylabel("Tamper challenge latency (ms)")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].grid(axis="y", linewidth=0.3)
    save(fig, out, "fig_verifier_payload_latency")


def plot_e5_policy(ext: Path, out: Path):
    df = pd.read_csv(ext / "e5_policy_compare.csv")
    focus = df[df["workload_id"] == "queued_8"].copy()
    focus["label"] = focus["policy"].map(label_policy)
    focus = focus.sort_values("risk_adjusted_goodput", ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), constrained_layout=True)
    axes[0].barh(focus["label"], focus["risk_adjusted_goodput"], color="#4b9c8e")
    axes[0].invert_yaxis()
    axes[0].set_title("Risk-adjusted goodput")
    axes[0].set_xlabel("Goodput")
    axes[0].grid(axis="x", linewidth=0.3)
    axes[1].barh(focus["label"], focus["expected_challenge_workload_ms_per_task"], color="#d59a3a")
    axes[1].invert_yaxis()
    axes[1].set_title("Expected challenge workload")
    axes[1].set_xlabel("ms/task")
    axes[1].tick_params(axis="y", labelleft=False)
    axes[1].grid(axis="x", linewidth=0.3)
    save(fig, out, "fig_e5_policy_compare")


def plot_placement_frontiers(root: Path, out: Path):
    df = pd.read_csv(root / "placement_summary.csv")
    latency_col = first_existing(df, ["median_latency_s", "latency_median_s"])
    risk_col = first_existing(df, ["false_risk", "false_risk_mean"])
    for workload, name in [("single", "fig_placement_frontier_a1"), ("queued-8", "fig_placement_frontier_a3_queue")]:
        focus = df[(df["workload"] == workload) & (df["alpha"].round(3) == 0.10)].copy()
        if focus.empty:
            continue
        focus["label"] = focus["policy"].map(label_policy)
        fig, ax = plt.subplots(figsize=(6.8, 4.2))
        ax.scatter(focus[latency_col], focus[risk_col], s=64, color="#5c7ea8")
        for _, row in focus.iterrows():
            ax.annotate(row["label"], (row[latency_col], row[risk_col]), xytext=(4, 4), textcoords="offset points", fontsize=7)
        ax.set_title(f"Placement frontier ({workload})")
        ax.set_xlabel("Median latency (s)")
        ax.set_ylabel("False-dispute risk")
        ax.grid(True, linewidth=0.3)
        fig.tight_layout()
        save(fig, out, name)


def plot_alpha_sensitivity(root: Path, out: Path):
    df = pd.read_csv(root / "placement_summary.csv")
    infeasible_col = first_existing(df, ["infeasible_usage", "infeasible_rate"])
    focus = df[df["policy"].isin(["adaptive_verifier", "queue_aware_verif_constrained", "network_aware_projcos4", "random"])].copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    for policy, g in focus.groupby("policy"):
        h = g.groupby("alpha")[infeasible_col].mean().reset_index()
        ax.plot(h["alpha"], h[infeasible_col], marker="o", label=label_policy(policy))
    ax.set_title("Alpha sensitivity")
    ax.set_xlabel("FPR threshold alpha")
    ax.set_ylabel("Infeasible usage")
    ax.grid(True, linewidth=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    save(fig, out, "fig_alpha_sensitivity_infeasible")


def main():
    parser = argparse.ArgumentParser(description="Regenerate extended artifact figures from included CSV files.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--extended-dir", default="data/extended")
    parser.add_argument("--out-dir", default="figs")
    args = parser.parse_args()
    root = Path(args.data_dir)
    ext = Path(args.extended_dir)
    out = Path(args.out_dir)

    plot_placement_replay(root, out)
    plot_risk_class_composition(root, out)
    plot_delivery_sweep(root, out)
    plot_delivery_scaling(root, out)
    plot_delivery_live_store(root, out)
    plot_material_tamper_focus(ext, out)
    plot_material_strength(ext, out)
    plot_projscalar_attack(ext, out)
    plot_projscalar_stability(ext, out)
    plot_verifier_payload_latency(ext, out)
    plot_e5_policy(ext, out)
    plot_placement_frontiers(root, out)
    plot_alpha_sensitivity(root, out)
    print(f"wrote extended figures to {out}")


if __name__ == "__main__":
    main()
