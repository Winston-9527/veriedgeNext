#!/usr/bin/env python3
import argparse

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Summarize selective delivery runs.")
    parser.add_argument("--runs", default="data/delivery_runs.csv")
    parser.add_argument("--out", default="data/delivery_summary.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.runs)
    grouped = (
        df.groupby(["scheme", "network", "k", "payload_mb"], dropna=False)
        .agg(
            n_runs=("run_id", "count"),
            median_all_ready_ms=("all_ready_ms", "median"),
            p95_all_ready_ms=("all_ready_ms", lambda x: x.quantile(0.95)),
            requester_egress_mb=("requester_egress_mb", "mean"),
        )
        .reset_index()
    )

    rows = []
    for (network, k), sub in grouped.groupby(["network", "k"]):
        rpd = sub[sub["scheme"] == "RPD"]
        base_latency = float(rpd.iloc[0]["median_all_ready_ms"]) if len(rpd) else float("nan")
        base_egress = float(rpd.iloc[0]["requester_egress_mb"]) if len(rpd) else float("nan")
        for _, row in sub.iterrows():
            out = row.to_dict()
            out["reduction_vs_rpd_pct"] = 100.0 * (base_latency - float(row["median_all_ready_ms"])) / base_latency
            out["egress_reduction_vs_rpd_pct"] = 100.0 * (base_egress - float(row["requester_egress_mb"])) / base_egress
            rows.append(out)

    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
