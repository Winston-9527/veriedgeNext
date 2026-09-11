from __future__ import annotations

import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE_DIR = REPO_ROOT / "paper1_veriedge" / "E1" / "tables"
BASELINE_CSV = TABLE_DIR / "table4_results.csv"
TUNED_CSV = TABLE_DIR / "table4_results_tuned_current_mixed_p9999.csv"
TUNED_SUMMARY = (
    REPO_ROOT
    / "paper1_veriedge"
    / "E1"
    / "logs"
    / "t4_final_current_mixed_40_200_p9999"
    / "exp_e1_20260502_t4_final_current_mixed_40_200_p9999_summary.csv"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    baseline_rows = _read_csv(BASELINE_CSV)
    if not baseline_rows:
        raise ValueError(f"empty baseline csv: {BASELINE_CSV}")

    tuned_summary_rows = _read_csv(TUNED_SUMMARY)
    if not tuned_summary_rows:
        raise ValueError(f"empty tuned summary csv: {TUNED_SUMMARY}")
    tuned_summary = tuned_summary_rows[0]

    tuned_rows = [dict(row) for row in baseline_rows]
    tuned_rows[0]["tstc_fpr"] = tuned_summary["tstc_fpr"]
    tuned_rows[0]["tstc_detect_count"] = tuned_summary["tstc_detect_count"]
    tuned_rows[0]["tstc_dominant_mismatch_checkpoint"] = tuned_summary[
        "tstc_dominant_mismatch_checkpoint"
    ]
    tuned_rows[0]["note"] = (
        baseline_rows[0]["note"]
        + " Tuned variant: calibration percentile increased from 99.0 to 99.99 on the same 40/200 captures."
    )

    fieldnames = list(tuned_rows[0].keys())
    _write_csv(TUNED_CSV, tuned_rows, fieldnames)
    print(f"Wrote tuned Table 4 results to {TUNED_CSV}")


if __name__ == "__main__":
    main()
