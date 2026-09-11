from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = REPO_ROOT / "paper1_veriedge" / "E1" / "tables" / "table4_results.csv"

ROWS = [
    {
        "draft_label": "Current mixed stack (M4/int8, BF16, RTX/FP32)",
        "actual_label": "Apple/Metal-int8 -> Apple/BF16 -> RTX/FP32 vs Apple/BF16 -> Apple/BF16 -> RTX/FP32",
        "scope": "C1-C3",
        "summary_csv": REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4_final_current_mixed_40_200" / "exp_e1_20260502_t4_final_current_mixed_40_200_summary.csv",
        "note": "Final 40/200 rerun with Apple MPS bfloat16 on the non-Metal shard and RTX FP32 on the final shard.",
    },
    {
        "draft_label": "M4/Metal vs. M4/BF16",
        "actual_label": "Apple/Metal-int8 vs Apple/BF16",
        "scope": "C1-C3",
        "summary_csv": REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4_final_applemetal_vs_applebf16_40_200" / "exp_e1_20260502_t4_final_applemetal_vs_applebf16_40_200_summary.csv",
        "note": "Final 40/200 paired capture with Apple Metal int8 on one side and Apple MPS bfloat16 on the other.",
    },
    {
        "draft_label": "M4/Metal vs. RTX/BF16",
        "actual_label": "Apple/Metal-int8 vs RTX/BF16",
        "scope": "C1-C3",
        "summary_csv": REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4_final_applemetal_vs_rtxbf16_40_200" / "exp_e1_20260502_t4_final_applemetal_vs_rtxbf16_40_200_summary.csv",
        "note": "Final 40/200 paired capture with Apple Metal int8 on one side and RTX 3090 CUDA bfloat16 on the other.",
    },
    {
        "draft_label": "M4/BF16 vs. RTX/FP32",
        "actual_label": "Apple/BF16 vs RTX/FP32",
        "scope": "C1-C3",
        "summary_csv": REPO_ROOT / "paper1_veriedge" / "E1" / "logs" / "t4_final_applebf16_vs_rtxfp32_40_200" / "exp_e1_20260502_t4_final_applebf16_vs_rtxfp32_40_200_summary.csv",
        "note": "Final 40/200 paired capture with Apple MPS bfloat16 on one side and RTX 3090 CUDA fp32 on the other.",
    },
]


def _read_summary_row(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"empty summary csv: {path}")
    return rows[0]


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "draft_label",
        "actual_label",
        "scope",
        "thc_fpr",
        "tstc_fpr",
        "thc_detect_count",
        "tstc_detect_count",
        "thc_dominant_mismatch_checkpoint",
        "tstc_dominant_mismatch_checkpoint",
        "note",
    ]
    out_rows: List[Dict[str, str]] = []
    for spec in ROWS:
        summary_path = Path(spec["summary_csv"])
        if not summary_path.exists():
            continue
        summary = _read_summary_row(summary_path)
        out_rows.append(
            {
                "draft_label": str(spec["draft_label"]),
                "actual_label": str(spec["actual_label"]),
                "scope": str(spec["scope"]),
                "thc_fpr": str(summary["thc_fpr"]),
                "tstc_fpr": str(summary["tstc_fpr"]),
                "thc_detect_count": str(summary["thc_detect_count"]),
                "tstc_detect_count": str(summary["tstc_detect_count"]),
                "thc_dominant_mismatch_checkpoint": str(summary["thc_dominant_mismatch_checkpoint"]),
                "tstc_dominant_mismatch_checkpoint": str(summary["tstc_dominant_mismatch_checkpoint"]),
                "note": str(spec["note"]),
            }
        )

    if not out_rows:
        raise ValueError("no available Table 4 summary CSVs were found")

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote Table 4 results to {OUT_CSV}")


if __name__ == "__main__":
    main()
