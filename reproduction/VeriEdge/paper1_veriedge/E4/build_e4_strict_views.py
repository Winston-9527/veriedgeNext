from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[2]
E4_DIR = REPO_ROOT / "paper1_veriedge" / "E4"
TABLE_DIR = E4_DIR / "tables"
STAMP = time.strftime("%Y%m%d")
OWNER = "strict_ab_mainline"
RUN_ID = f"exp_e4_{STAMP}_{OWNER}"
LOG_ROOT = E4_DIR / "logs" / RUN_ID


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fields)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _find(root: Path, suffix: str) -> Path:
    return next(root.glob(f"*_{suffix}.csv"))


def main() -> None:
    baseline_dir = LOG_ROOT / "baseline_checkpoint_specific"
    global_dir = LOG_ROOT / "global_shared"
    baseline_summary = _read_csv(_find(baseline_dir, "summary"))
    global_summary = _read_csv(_find(global_dir, "summary"))

    baseline_index = {(r["trace_label"], r["scenario"], r["verifier"]): r for r in baseline_summary}
    global_index = {(r["trace_label"], r["scenario"], r["verifier"]): r for r in global_summary}

    combined_rows: List[Dict[str, Any]] = []
    for mode_name, rows in (
        ("baseline_checkpoint_specific", baseline_summary),
        ("global_shared", global_summary),
    ):
        for row in rows:
            combined_rows.append(
                {
                    "tolerance_mode": mode_name,
                    **row,
                }
            )

    comparison_rows: List[Dict[str, Any]] = []
    for key in sorted(baseline_index.keys()):
        b = baseline_index[key]
        g = global_index[key]
        comparison_rows.append(
            {
                "trace_label": key[0],
                "scenario": key[1],
                "verifier": key[2],
                "baseline_detection_rate": b["detection_rate"],
                "global_detection_rate": g["detection_rate"],
                "baseline_mean_challenge_latency_ms": b["mean_challenge_latency_ms"],
                "global_mean_challenge_latency_ms": g["mean_challenge_latency_ms"],
                "baseline_mean_replay_ms": b["mean_replay_ms"],
                "global_mean_replay_ms": g["mean_replay_ms"],
                "baseline_mean_commitment_head_bytes": b["mean_commitment_head_bytes"],
                "global_mean_commitment_head_bytes": g["mean_commitment_head_bytes"],
                "baseline_mean_commitment_chain_bytes": b["mean_commitment_chain_bytes"],
                "global_mean_commitment_chain_bytes": g["mean_commitment_chain_bytes"],
                "baseline_mean_validator_storage_head_bytes": b["mean_validator_storage_head_bytes"],
                "global_mean_validator_storage_head_bytes": g["mean_validator_storage_head_bytes"],
                "baseline_mean_validator_storage_full_chain_bytes": b["mean_validator_storage_full_chain_bytes"],
                "global_mean_validator_storage_full_chain_bytes": g["mean_validator_storage_full_chain_bytes"],
            }
        )

    manuscript_rows: List[Dict[str, Any]] = []
    for row in global_summary:
        manuscript_rows.append(
            {
                "trace_label": row["trace_label"],
                "scenario": row["scenario"],
                "verifier": row["verifier"],
                "sample_count": row["sample_count"],
                "reference_capture_kib": round(float(row["mean_reference_capture_file_bytes"]) / 1024.0, 3),
                "candidate_capture_kib": round(float(row["mean_candidate_capture_file_bytes"]) / 1024.0, 3),
                "capture_pair_total_kib": round(float(row["mean_capture_pair_total_bytes"]) / 1024.0, 3),
                "commitment_head_bytes": row["mean_commitment_head_bytes"],
                "commitment_chain_bytes": row["mean_commitment_chain_bytes"],
                "validator_storage_head_kib": round(float(row["mean_validator_storage_head_bytes"]) / 1024.0, 3),
                "validator_storage_full_chain_kib": round(float(row["mean_validator_storage_full_chain_bytes"]) / 1024.0, 3),
                "replay_ms": row["mean_replay_ms"],
                "compare_ms": row["mean_compare_ms"],
                "verdict_emission_ms": row["mean_verdict_emission_ms"],
                "challenge_latency_ms": row["mean_challenge_latency_ms"],
                "detection_rate": row["detection_rate"],
            }
        )

    _write_csv(
        TABLE_DIR / f"{RUN_ID}_overhead_summary.csv",
        combined_rows,
        [
            "tolerance_mode",
            "trace_label",
            "scenario",
            "verifier",
            "sample_count",
            "mean_reference_capture_file_bytes",
            "mean_candidate_capture_file_bytes",
            "mean_capture_pair_total_bytes",
            "mean_commitment_head_bytes",
            "mean_commitment_chain_bytes",
            "mean_validator_storage_head_bytes",
            "mean_validator_storage_full_chain_bytes",
            "mean_replay_ms",
            "mean_compare_ms",
            "mean_verdict_emission_ms",
            "mean_challenge_latency_ms",
            "detection_rate",
        ],
    )
    _write_csv(
        TABLE_DIR / f"{RUN_ID}_global_comparison.csv",
        comparison_rows,
        list(comparison_rows[0].keys()),
    )
    _write_csv(
        TABLE_DIR / f"{RUN_ID}_main_table.csv",
        manuscript_rows,
        list(manuscript_rows[0].keys()),
    )
    print(TABLE_DIR / f"{RUN_ID}_overhead_summary.csv")
    print(TABLE_DIR / f"{RUN_ID}_global_comparison.csv")
    print(TABLE_DIR / f"{RUN_ID}_main_table.csv")


if __name__ == "__main__":
    main()
