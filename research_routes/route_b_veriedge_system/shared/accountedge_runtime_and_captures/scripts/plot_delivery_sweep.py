#!/usr/bin/env python3
import argparse

import matplotlib.pyplot as plt
import pandas as pd


PDF_METADATA = {
    "Creator": "anonymous artifact",
    "Producer": "anonymous artifact",
    "CreationDate": None,
    "ModDate": None,
    "Title": "Delivery sweep",
}


def main():
    parser = argparse.ArgumentParser(description="Plot selective delivery latency and requester egress.")
    parser.add_argument("--summary", default="data/delivery_summary.csv")
    parser.add_argument("--out", default="figs/fig_delivery_sweep.pdf")
    args = parser.parse_args()

    df = pd.read_csv(args.summary)
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.0), constrained_layout=True)

    for scheme in ["RPD", "PPD"]:
        g = df[(df["scheme"] == scheme) & (df["network"] == "WAN")].sort_values("k")
        axes[0].plot(g["k"], g["median_all_ready_ms"], marker="o", label=scheme)
        axes[0].fill_between(g["k"], g["median_all_ready_ms"], g["p95_all_ready_ms"], alpha=0.16)

    axes[0].set_title("Delivery latency (WAN profile)")
    axes[0].set_xlabel("Selected group size k")
    axes[0].set_ylabel("All-providers-ready latency (ms)")
    axes[0].grid(True, linewidth=0.3)
    axes[0].legend(fontsize=8)

    egress = df[df["network"] == "LAN"].sort_values(["scheme", "k"])
    for scheme in ["RPD", "PPD"]:
        g = egress[egress["scheme"] == scheme]
        axes[1].plot(g["k"], g["requester_egress_mb"], marker="o", label=scheme)
    axes[1].set_title("Requester egress")
    axes[1].set_xlabel("Selected group size k")
    axes[1].set_ylabel("Requester egress (MB)")
    axes[1].grid(True, linewidth=0.3)
    axes[1].legend(fontsize=8)

    fig.savefig(args.out, metadata=PDF_METADATA)
    png_out = args.out.rsplit(".", 1)[0] + ".png"
    fig.savefig(png_out, dpi=180)
    print(f"wrote {args.out} and {png_out}")


if __name__ == "__main__":
    main()
