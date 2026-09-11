#!/usr/bin/env python3
"""Prompt-level calibration audit for PACT.

This deliberately removes random-projection error by inspecting exact full
residual energy.  If a threshold fails here, increasing K cannot repair it.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROUTE_ROOT = HERE.parents[1]
PCRA_DIR = HERE.parent / "pcra_offline_retired"
DEFAULT_DATA_ROOT = (
    ROUTE_ROOT
    / "shared"
    / "accountedge_runtime_and_captures"
    / "raw_captures"
    / "e2_live_subset"
)
sys.path.insert(0, str(PCRA_DIR))

from pcra_offline import CHECKPOINTS, Pair, normalized_residual, resolve_stack_dir  # noqa: E402


def capture_files(root: Path, stack: str, prefix: str) -> list[Path]:
    stack_dir = resolve_stack_dir(root, stack)
    files = sorted((root / stack_dir / "captures").glob(f"{prefix}_*.npz"))
    if not files:
        raise FileNotFoundError(root / stack_dir / "captures" / f"{prefix}_*.npz")
    return files


def load_stack_pair(root: Path, reference_stack: str, candidate_stack: str, prefix: str) -> list[Pair]:
    references = capture_files(root, reference_stack, prefix)
    candidates = capture_files(root, candidate_stack, prefix)
    if [path.name for path in references] != [path.name for path in candidates]:
        raise ValueError(f"Unmatched files for {reference_stack} and {candidate_stack}")
    output: list[Pair] = []
    for reference_path, candidate_path in zip(references, candidates):
        with np.load(reference_path) as reference, np.load(candidate_path) as candidate:
            for checkpoint in CHECKPOINTS:
                output.append(
                    Pair(
                        reference_path.stem,
                        checkpoint,
                        np.asarray(reference[checkpoint], dtype=np.float64).reshape(-1),
                        np.asarray(candidate[checkpoint], dtype=np.float64).reshape(-1),
                    )
                )
    return output


def energy_rows(pairs: list[Pair], split: str, candidate_run: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pair in pairs:
        residual, reference_rms = normalized_residual(pair)
        rows.append(
            {
                "split": split,
                "candidate_run": candidate_run,
                "prompt_id": pair.prompt_id,
                "checkpoint": pair.checkpoint,
                "N": residual.size,
                "reference_rms": reference_rms,
                "full_residual_energy": float(np.mean(np.square(residual))),
                "full_residual_rms": float(np.sqrt(np.mean(np.square(residual)))),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit(
    rows: list[dict[str, object]], rhos: list[float], alpha: float
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summary: list[dict[str, object]] = []
    oracle: list[dict[str, object]] = []
    for checkpoint in CHECKPOINTS:
        calibration = np.asarray(
            [
                float(row["full_residual_energy"])
                for row in rows
                if row["split"] == "calibration" and row["checkpoint"] == checkpoint
            ]
        )
        evaluation = np.asarray(
            [
                float(row["full_residual_energy"])
                for row in rows
                if row["split"] == "evaluation"
                and row["candidate_run"] == "original"
                and row["checkpoint"] == checkpoint
            ]
        )
        rerun = np.asarray(
            [
                float(row["full_residual_energy"])
                for row in rows
                if row["split"] == "evaluation"
                and row["candidate_run"] == "rerun"
                and row["checkpoint"] == checkpoint
            ]
        )
        threshold = float(np.max(calibration))
        summary.append(
            {
                "checkpoint": checkpoint,
                "calibration_prompts": calibration.size,
                "evaluation_prompts": evaluation.size,
                "max_calibration_energy": threshold,
                "median_calibration_energy": float(np.median(calibration)),
                "median_evaluation_energy": float(np.median(evaluation)),
                "max_evaluation_energy": float(np.max(evaluation)),
                "evaluation_exceedance_rate_at_max_calibration": float(np.mean(evaluation > threshold)),
                "rerun_exceedance_rate_at_max_calibration": (
                    float(np.mean(rerun > threshold)) if rerun.size else None
                ),
                "median_abs_original_rerun_energy_difference": (
                    float(np.median(np.abs(evaluation - rerun)))
                    if rerun.size and rerun.size == evaluation.size
                    else None
                ),
                "nominal_alpha": alpha,
                "smallest_distribution_free_alpha_with_n_calibration": 1.0
                / (calibration.size + 1),
                "minimum_calibration_prompts_for_nontrivial_alpha": int(np.ceil(1.0 / alpha) - 1),
            }
        )
        for rho in rhos:
            # Orthogonal harm-preserving attack: exact energy rises by rho^2.
            attacked = evaluation + rho * rho
            oracle.append(
                {
                    "checkpoint": checkpoint,
                    "rho": rho,
                    "threshold": threshold,
                    "honest_exceedance_rate": float(np.mean(evaluation > threshold)),
                    "ideal_infinite_K_attack_detection_rate": float(np.mean(attacked > threshold)),
                    "median_honest_energy": float(np.median(evaluation)),
                    "median_attacked_energy": float(np.median(attacked)),
                }
            )
    return summary, oracle


def plot(rows: list[dict[str, object]], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.2), sharey=False)
    splits = (("calibration", "original", "calibration"), ("evaluation", "original", "evaluation"))
    for axis, checkpoint in zip(axes, CHECKPOINTS):
        for x, (split, run, label) in enumerate(splits):
            values = np.asarray(
                [
                    float(row["full_residual_energy"])
                    for row in rows
                    if row["split"] == split
                    and row["candidate_run"] == run
                    and row["checkpoint"] == checkpoint
                ]
            )
            jitter = np.linspace(-0.12, 0.12, values.size)
            axis.scatter(
                np.full(values.size, x) + jitter,
                values,
                color="#666666" if x == 0 else "#aaaaaa",
                edgecolors="#333333",
                linewidths=0.4,
                s=22,
                label=label,
            )
        calibration = [
            float(row["full_residual_energy"])
            for row in rows
            if row["split"] == "calibration" and row["checkpoint"] == checkpoint
        ]
        axis.axhline(max(calibration), color="#222222", linestyle="--", linewidth=1.0)
        axis.set_xticks([0, 1], ["calib (6)", "eval (12)"])
        axis.set_title(checkpoint.replace("prefill__", ""))
        axis.grid(True, axis="y", color="#dddddd", linewidth=0.6)
        axis.set_ylabel("Exact normalized residual energy")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "calibration_audit")
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument(
        "--skip-rerun",
        action="store_true",
        help="skip the same-stack rerun comparison (no stack_02_rerun_eval captures present)",
    )
    args = parser.parse_args()

    calibration = load_stack_pair(
        args.data_root, "stack_01_calib", "stack_02_calib", "calib"
    )
    evaluation = load_stack_pair(
        args.data_root, "stack_01_eval", "stack_02_eval", "eval"
    )
    rows = energy_rows(calibration, "calibration", "original") + energy_rows(
        evaluation, "evaluation", "original"
    )
    if args.skip_rerun:
        rerun_identical = None
    else:
        rerun = load_stack_pair(
            args.data_root, "stack_01_eval", "stack_02_rerun_eval", "eval"
        )
        rerun_identical = all(
            original.prompt_id == repeated.prompt_id
            and original.checkpoint == repeated.checkpoint
            and np.array_equal(original.candidate, repeated.candidate)
            for original, repeated in zip(evaluation, rerun)
        )
        rows = rows + energy_rows(rerun, "evaluation", "rerun")
    summary, oracle = audit(rows, [0.01, 0.02, 0.05], args.alpha)

    n_calib = len({pair.prompt_id for pair in calibration})
    n_eval = len({pair.prompt_id for pair in evaluation})
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "energy_by_prompt.csv", rows)
    write_csv(args.output / "calibration_summary.csv", summary)
    write_csv(args.output / "infinite_k_oracle.csv", oracle)
    plot(rows, args.output / "prompt_energy.png")
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "prompt-level exact-energy audit; no projection Monte Carlo error",
                "alpha": args.alpha,
                "independent_calibration_prompts": n_calib,
                "independent_evaluation_prompts": n_eval,
                "minimum_calibration_prompts_for_nontrivial_distribution_free_1pct": 99,
                "rerun_is_correlated_with_evaluation_and_not_counted_as_new_prompts": True,
                "rerun_candidate_tensors_value_identical_to_original": rerun_identical,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
