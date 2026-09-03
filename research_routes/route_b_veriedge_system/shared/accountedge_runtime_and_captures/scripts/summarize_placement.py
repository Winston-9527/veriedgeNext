#!/usr/bin/env python3
import argparse

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Summarize placement replay results by workload, policy, and threshold.")
    parser.add_argument("--results", default="data/placement_results.csv")
    parser.add_argument("--out", default="data/placement_summary.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.results)
    selected = df[df["selected"] == 1].copy()
    summary = (
        selected.groupby(["workload", "alpha", "policy"], dropna=False)
        .agg(
            n_tasks=("task_id", "count"),
            median_latency_s=("latency_s", "median"),
            p95_latency_s=("latency_s", lambda x: x.quantile(0.95)),
            goodput=("goodput", "mean"),
            infeasible_usage=("infeasible_usage", "mean"),
            false_risk=("false_risk", "mean"),
            verify_ms=("verify_ms", "mean"),
        )
        .reset_index()
    )
    summary.to_csv(args.out, index=False)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
