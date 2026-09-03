#!/usr/bin/env python3
import argparse

import matplotlib.pyplot as plt
import pandas as pd


PDF_METADATA = {
    "Creator": "anonymous artifact",
    "Producer": "anonymous artifact",
    "CreationDate": None,
    "ModDate": None,
    "Title": "Placement replay",
}


def clean_policy_name(name: str) -> str:
    return (
        name.replace("_", " ")
        .replace("verif constrained", "verif.")
        .replace("network aware", "network")
        .replace("queue aware", "queue")
        .replace("adaptive verifier", "adaptive")
    )


def main():
    parser = argparse.ArgumentParser(description="Plot placement replay summary without overlapping labels.")
    parser.add_argument("--summary", default="data/placement_summary.csv")
    parser.add_argument("--out", default="figs/fig_placement_replay.pdf")
    args = parser.parse_args()

    df = pd.read_csv(args.summary)
    focus = df[df["alpha"].astype(float).round(3) == 0.10].copy() if "alpha" in df.columns else df.copy()
    if "workload" in focus.columns and "queued-8" in set(focus["workload"]):
        focus = focus[focus["workload"] == "queued-8"].copy()

    # Aggregate once more in case the summary contains multiple seeds or workloads.
    plot_df = (
        focus.groupby("policy", as_index=False)
        .agg(
            infeasible_usage=("infeasible_usage", "mean"),
            false_risk=("false_risk", "mean"),
            goodput=("goodput", "mean"),
            median_latency_s=("median_latency_s", "mean"),
        )
        .sort_values(["infeasible_usage", "false_risk", "policy"])
    )
    plot_df["label"] = plot_df["policy"].map(clean_policy_name)

    colors = ["#315c9c" if row["infeasible_usage"] <= 0.05 else "#d08b2c" for _, row in plot_df.iterrows()]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4), constrained_layout=True)

    axes[0].barh(plot_df["label"], plot_df["infeasible_usage"], color=colors, alpha=0.88)
    axes[0].axvline(0.05, color="#333333", linestyle="--", linewidth=1.0, label="5% reference")
    axes[0].set_xlabel("Infeasible placement usage")
    axes[0].set_title("Admission before disclosure")
    axes[0].grid(axis="x", linewidth=0.3)
    axes[0].legend(fontsize=8, loc="lower right")

    axes[1].barh(plot_df["label"], plot_df["false_risk"], color="#4b9c8e", alpha=0.88)
    axes[1].set_xlabel("Expected false-dispute risk")
    axes[1].set_title("Risk after policy filtering")
    axes[1].grid(axis="x", linewidth=0.3)
    axes[1].tick_params(axis="y", labelleft=False)

    fig.suptitle("Placement replay under verifier constraints", fontsize=14)
    fig.savefig(args.out, metadata=PDF_METADATA)
    png_out = args.out.rsplit(".", 1)[0] + ".png"
    fig.savefig(png_out, dpi=180)
    print(f"wrote {args.out} and {png_out}")


if __name__ == "__main__":
    main()
