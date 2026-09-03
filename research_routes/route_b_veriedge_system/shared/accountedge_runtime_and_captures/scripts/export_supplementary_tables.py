#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def write_table(df: pd.DataFrame, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / f"{stem}.csv", index=False)
    (out_dir / f"{stem}.md").write_text(to_markdown(df))


def to_markdown(df: pd.DataFrame) -> str:
    headers = [str(col) for col in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for _, row in df.iterrows():
        values = [str(row[col]) if pd.notna(row[col]) else "" for col in df.columns]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    return "\n".join(lines) + "\n"


def table_1_profiles(data: Path) -> pd.DataFrame:
    cols = [
        "profile_id",
        "pair",
        "sketch",
        "alpha",
        "fpr",
        "tpr",
        "sketch_bytes",
        "verify_ms",
        "risk_class",
        "feasible",
    ]
    return pd.read_csv(data / "verifier_profiles.csv")[cols]


def table_2_replay_inputs(data: Path) -> pd.DataFrame:
    candidates = pd.read_csv(data / "placement_candidates.csv")
    workload = pd.read_csv(data / "placement_workload.csv")
    return pd.DataFrame(
        [
            {
                "input_table": "placement_candidates.csv",
                "rows": len(candidates),
                "candidate_count": candidates["candidate_id"].nunique(),
                "workload_count": "",
                "description": "candidate groups, shard maps, network/service estimates, and profile keys",
            },
            {
                "input_table": "placement_workload.csv",
                "rows": len(workload),
                "candidate_count": "",
                "workload_count": workload["task_id"].nunique(),
                "description": "controlled task workload used by deterministic placement replay",
            },
        ]
    )


def table_3_queued_replay(data: Path) -> pd.DataFrame:
    df = pd.read_csv(data / "placement_summary.csv")
    focus = df[(df["workload"] == "queued-8") & (df["alpha"].round(3) == 0.10)].copy()
    cols = [
        "policy",
        "n_tasks",
        "median_latency_s",
        "p95_latency_s",
        "goodput",
        "infeasible_usage",
        "false_risk",
        "verify_ms",
    ]
    return focus[cols].sort_values(["infeasible_usage", "false_risk", "policy"], ascending=[True, True, True])


def table_4_delivery_sweep(data: Path) -> pd.DataFrame:
    cols = [
        "scheme",
        "network",
        "k",
        "payload_mb",
        "n_runs",
        "median_all_ready_ms",
        "p95_all_ready_ms",
        "requester_egress_mb",
        "reduction_vs_rpd_pct",
        "egress_reduction_vs_rpd_pct",
    ]
    return pd.read_csv(data / "delivery_summary.csv")[cols].sort_values(["network", "k", "scheme"])


def table_5_live_store(data: Path) -> pd.DataFrame:
    cols = [
        "mode",
        "payload_mb",
        "group_size",
        "n",
        "median_ms",
        "p95_ms",
        "requester_egress_mb_mean",
        "store_egress_mb_mean",
        "access_pkg_bytes_mean",
        "egress_reduction_vs_rpd",
    ]
    return pd.read_csv(data / "delivery_live_store_summary.csv")[cols].sort_values(["group_size", "mode"])


def table_6_material_tamper(ext: Path) -> pd.DataFrame:
    df = pd.read_csv(ext / "material_tamper_attack_summary.csv")
    attacks = ["gaussian", "cross_prompt_stale_substitution", "wrong_shard_output", "layer_skip", "scale_perturbation"]
    variants = ["scalar16", "projcos4", "projcos16"]
    focus = df[df["attack_family"].isin(attacks) & df["variant"].isin(variants)].copy()
    grouped = (
        focus.groupby(["attack_family", "variant"], as_index=False)
        .agg(
            mean_tpr=("detection_rate", "mean"),
            min_tpr=("detection_rate", "min"),
            mean_localization=("localization_acc", "mean"),
            signature_bytes=("signature_bytes_per_checkpoint_fp32", "first"),
        )
        .sort_values(["attack_family", "variant"])
    )
    return grouped


def table_7_output_affecting(ext: Path) -> pd.DataFrame:
    df = pd.read_csv(ext / "material_tamper_attack_summary.csv")
    grouped = (
        df.groupby(["pair_id", "pair_label"], as_index=False)
        .agg(
            output_affecting_available=("output_affecting_available", "max"),
            output_affecting_prompt_count=("output_affecting_prompt_count", "max"),
            reason=("output_affecting_reason", "first"),
        )
        .sort_values("pair_id")
    )
    grouped["interpretation"] = grouped["output_affecting_available"].map(
        {0: "not available in included checkpoint-only captures", 1: "available"}
    )
    return grouped


def main() -> None:
    parser = argparse.ArgumentParser(description="Export supplementary tables from included CSVs.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--extended-dir", default="data/extended")
    parser.add_argument("--out-dir", default="tables")
    args = parser.parse_args()

    data = Path(args.data_dir)
    ext = Path(args.extended_dir)
    out = Path(args.out_dir)
    write_table(table_1_profiles(data), out, "table_1_verifier_profiles")
    write_table(table_2_replay_inputs(data), out, "table_2_replay_inputs")
    write_table(table_3_queued_replay(data), out, "table_3_queued8_placement_replay")
    write_table(table_4_delivery_sweep(data), out, "table_4_delivery_sweep")
    write_table(table_5_live_store(data), out, "table_5_live_store_validation")
    write_table(table_6_material_tamper(ext), out, "table_6_material_tamper_tpr")
    write_table(table_7_output_affecting(ext), out, "table_7_output_affecting_subset")
    print(f"wrote supplementary tables to {out}")


if __name__ == "__main__":
    main()
