#!/usr/bin/env python3
"""Offline smoke experiment for the PCRA check protocol.

This script uses the anonymized real heterogeneous checkpoint captures shipped
with the repository.  It calibrates boundary-specific thresholds on six prompt
pairs and evaluates honest and synthetically attacked residuals on twelve held-
out prompt pairs.  The synthetic attacks are applied after the real measured
heterogeneous residual, so the false-positive pressure comes from the deployed
stacks rather than an artificial noise model.

The experiment is intentionally a protocol/statistic smoke test.  It is not a
replacement for the full E2-R corpus or an end-to-end malicious-provider run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


PCRA_DIR = Path(__file__).resolve().parent
ROUTE_B_DIR = PCRA_DIR.parents[1]
DEFAULT_DATA_ROOT = (
    ROUTE_B_DIR
    / "shared"
    / "accountedge_runtime_and_captures"
    / "raw_captures"
    / "e2_live_subset"
)
CHECKPOINTS = ("prefill__C1", "prefill__C2", "prefill__C3")
STATISTICS = ("spike", "energy", "directional")
ATTACK_SETTINGS = (
    ("spike_1", "post_commit"),
    ("sparse_16", "post_commit"),
    ("diffuse_balanced", "post_commit"),
    ("directional", "post_commit"),
    ("sample_null", "known_coordinates"),
    ("sample_null", "post_commit"),
)


@dataclass(frozen=True)
class Pair:
    prompt_id: str
    checkpoint: str
    reference: np.ndarray
    candidate: np.ndarray


def stable_seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def resolve_stack_dir(root: Path, base: str) -> str:
    """Resolve a stack directory name, tolerant of legacy sample-count suffixes.

    ``base="stack_01_calib"`` matches the honest naming ``stack_01_calib`` or the
    legacy ``stack_01_calib_6``; likewise ``stack_01_eval`` / ``stack_02_rerun_eval``.
    This keeps the shipped ``e2_live_subset`` (sample count embedded in dir names)
    working alongside the re-organized 720-pool layout that drops it.
    """
    if (root / base).is_dir():
        return base
    matches = sorted(p.name for p in root.glob(f"{base}_*") if p.is_dir())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"No stack dir {base!r} or {base}_* under {root}")
    raise ValueError(f"Ambiguous stack dirs for {base!r}: {matches}")


def capture_files(root: Path, stack: str, split: str) -> list[Path]:
    pattern = "calib_*.npz" if split == "calib" else "eval_*.npz"
    stack_dir = resolve_stack_dir(root, stack)
    files = sorted((root / stack_dir / "captures").glob(pattern))
    if not files:
        raise FileNotFoundError(f"No {pattern} files under {root / stack_dir / 'captures'}")
    return files


def load_pairs(root: Path, split: str) -> list[Pair]:
    suffix = "calib" if split == "calib" else "eval"
    ref_files = capture_files(root, f"stack_01_{suffix}", split)
    cand_files = capture_files(root, f"stack_02_{suffix}", split)
    if [path.name for path in ref_files] != [path.name for path in cand_files]:
        raise ValueError(f"Unmatched {split} capture filenames")

    pairs: list[Pair] = []
    for ref_path, cand_path in zip(ref_files, cand_files):
        with np.load(ref_path) as ref_capture, np.load(cand_path) as cand_capture:
            if set(ref_capture.files) != set(CHECKPOINTS):
                raise ValueError(f"Unexpected keys in {ref_path}: {ref_capture.files}")
            for checkpoint in CHECKPOINTS:
                reference = np.asarray(ref_capture[checkpoint], dtype=np.float64).reshape(-1)
                candidate = np.asarray(cand_capture[checkpoint], dtype=np.float64).reshape(-1)
                if reference.shape != candidate.shape:
                    raise ValueError(f"Shape mismatch for {ref_path.name}:{checkpoint}")
                pairs.append(
                    Pair(
                        prompt_id=ref_path.stem,
                        checkpoint=checkpoint,
                        reference=reference,
                        candidate=candidate,
                    )
                )
    return pairs


def normalized_residual(pair: Pair) -> tuple[np.ndarray, float]:
    rms = float(np.sqrt(np.mean(np.square(pair.reference))))
    if not np.isfinite(rms) or rms <= 0:
        raise ValueError(f"Invalid reference RMS for {pair.prompt_id}:{pair.checkpoint}")
    return (pair.candidate - pair.reference) / rms, rms


def statistic_values(residual_q: np.ndarray, reference_q: np.ndarray) -> dict[str, float]:
    return {
        "spike": float(np.max(np.abs(residual_q))),
        "energy": float(np.mean(np.square(residual_q))),
        "directional": float(np.abs(np.mean(np.sign(reference_q) * residual_q))),
    }


def higher_quantile(values: Iterable[float], probability: float) -> float:
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0:
        raise ValueError("Cannot calibrate an empty statistic")
    try:
        return float(np.quantile(array, probability, method="higher"))
    except TypeError:  # NumPy < 1.22
        return float(np.quantile(array, probability, interpolation="higher"))


def calibrate_thresholds(
    pairs: list[Pair],
    q_values: list[int],
    challenges: int,
    alpha: float,
) -> tuple[dict[tuple[str, int, str], float], list[dict[str, object]]]:
    samples: dict[tuple[str, int, str], list[float]] = defaultdict(list)
    for pair in pairs:
        residual, _ = normalized_residual(pair)
        n = residual.size
        for q in q_values:
            q_eff = min(q, n)
            for repeat in range(challenges):
                rng = np.random.default_rng(
                    stable_seed("calibration", pair.prompt_id, pair.checkpoint, q, repeat)
                )
                coordinates = rng.choice(n, size=q_eff, replace=False)
                values = statistic_values(residual[coordinates], pair.reference[coordinates])
                for statistic, value in values.items():
                    samples[(pair.checkpoint, q, statistic)].append(value)

    # Bonferroni allocation makes the combined three-statistic check target alpha.
    probability = 1.0 - alpha / len(STATISTICS)
    thresholds: dict[tuple[str, int, str], float] = {}
    rows: list[dict[str, object]] = []
    for key, values in sorted(samples.items()):
        threshold = higher_quantile(values, probability)
        thresholds[key] = threshold
        checkpoint, q, statistic = key
        rows.append(
            {
                "checkpoint": checkpoint,
                "q": q,
                "statistic": statistic,
                "threshold": threshold,
                "calibration_draws": len(values),
                "target_alpha_combined": alpha,
                "target_alpha_statistic": alpha / len(STATISTICS),
            }
        )
    return thresholds, rows


def rademacher(rng: np.random.Generator, size: int) -> np.ndarray:
    return rng.integers(0, 2, size=size, dtype=np.int8).astype(np.float64) * 2.0 - 1.0


def attack_on_challenge(
    attack: str,
    timing: str,
    rho: float,
    n: int,
    coordinates: np.ndarray,
    reference_q: np.ndarray,
    q_nominal: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return delta/RMS(reference) only at challenged coordinates.

    Every construction has full-vector L2 norm rho * ||reference||.  Computing
    only challenged entries avoids materializing a full attacked tensor.
    """
    q_eff = coordinates.size
    delta_q = np.zeros(q_eff, dtype=np.float64)

    if attack == "spike_1":
        support = int(rng.integers(0, n))
        hits = np.flatnonzero(coordinates == support)
        if hits.size:
            delta_q[hits[0]] = rho * np.sqrt(n) * (1.0 if rng.integers(0, 2) else -1.0)
        return delta_q

    if attack == "sparse_16":
        support_size = min(16, n)
        support = rng.choice(n, size=support_size, replace=False)
        signs = rademacher(rng, support_size)
        lookup = {int(index): float(sign) for index, sign in zip(support, signs)}
        amplitude = rho * np.sqrt(n / support_size)
        for position, index in enumerate(coordinates):
            if int(index) in lookup:
                delta_q[position] = amplitude * lookup[int(index)]
        return delta_q

    if attack == "diffuse_balanced":
        # The attack is committed before the challenge; its signs do not depend
        # on the challenged set. Conditional on an independently drawn set Q,
        # its entries on Q remain independent Rademacher variables, so sampling
        # only those entries is distribution-equivalent and much cheaper.
        return rho * rademacher(rng, q_eff)

    if attack == "directional":
        # A representation-aligned dense displacement stresses the directional
        # statistic while keeping the same relative L2 budget.
        normed = np.sign(reference_q)
        norm = float(np.linalg.norm(normed))
        if norm == 0:
            return delta_q
        # sign(reference) over all coordinates has norm sqrt(n); zeros are rare.
        return rho * normed

    if attack == "sample_null":
        if timing == "known_coordinates":
            # The attacker sees the exact challenge before committing and puts
            # all perturbation energy outside it: an explicit blind subspace.
            return delta_q
        if timing != "post_commit":
            raise ValueError(f"Unknown sample_null timing: {timing}")
        guessed = rng.choice(n, size=min(q_nominal, n), replace=False)
        allowed = n - guessed.size
        if allowed <= 0:
            return delta_q
        signs = rademacher(rng, q_eff)
        amplitude = rho * np.sqrt(n / allowed)
        visible = ~np.isin(coordinates, guessed, assume_unique=True)
        delta_q[visible] = amplitude * signs[visible]
        return delta_q

    raise ValueError(f"Unknown attack: {attack}")


def evaluate(
    pairs: list[Pair],
    thresholds: dict[tuple[str, int, str], float],
    q_values: list[int],
    strengths: list[float],
    challenges: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    counts: dict[tuple[object, ...], list[int]] = defaultdict(lambda: [0, 0])
    case_rows: list[dict[str, object]] = []

    def record(
        pair: Pair,
        q: int,
        attack: str,
        timing: str,
        rho: float,
        values: dict[str, float],
    ) -> None:
        decisions = {
            statistic: values[statistic] > thresholds[(pair.checkpoint, q, statistic)]
            for statistic in STATISTICS
        }
        decisions["combined"] = any(decisions.values())
        for statistic, detected in decisions.items():
            key = (pair.checkpoint, q, attack, timing, rho, statistic)
            counts[key][0] += int(detected)
            counts[key][1] += 1

    for pair in pairs:
        residual, _ = normalized_residual(pair)
        n = residual.size
        for q in q_values:
            q_eff = min(q, n)
            for repeat in range(challenges):
                challenge_rng = np.random.default_rng(
                    stable_seed("evaluation-challenge", pair.prompt_id, pair.checkpoint, q, repeat)
                )
                coordinates = challenge_rng.choice(n, size=q_eff, replace=False)
                honest_q = residual[coordinates]
                reference_q = pair.reference[coordinates]
                honest_values = statistic_values(honest_q, reference_q)
                record(pair, q, "honest", "none", 0.0, honest_values)

                for attack, timing in ATTACK_SETTINGS:
                    for rho in strengths:
                        attack_rng = np.random.default_rng(
                            stable_seed(
                                "attack",
                                pair.prompt_id,
                                pair.checkpoint,
                                q,
                                repeat,
                                attack,
                                timing,
                                rho,
                            )
                        )
                        delta_q = attack_on_challenge(
                            attack=attack,
                            timing=timing,
                            rho=rho,
                            n=n,
                            coordinates=coordinates,
                            reference_q=reference_q,
                            q_nominal=q,
                            rng=attack_rng,
                        )
                        values = statistic_values(honest_q + delta_q, reference_q)
                        record(pair, q, attack, timing, rho, values)

                case_rows.append(
                    {
                        "prompt_id": pair.prompt_id,
                        "checkpoint": pair.checkpoint,
                        "q": q,
                        "repeat": repeat,
                        "n": n,
                    }
                )

    rows: list[dict[str, object]] = []
    for key, (detected, trials) in sorted(counts.items()):
        checkpoint, q, attack, timing, rho, statistic = key
        rows.append(
            {
                "checkpoint": checkpoint,
                "q": q,
                "attack": attack,
                "timing": timing,
                "rho": rho,
                "statistic": statistic,
                "detected": detected,
                "trials": trials,
                "rate": detected / trials,
            }
        )
    return rows, case_rows


def aggregate_checkpoints(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    totals: dict[tuple[object, ...], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        key = (row["q"], row["attack"], row["timing"], row["rho"], row["statistic"])
        totals[key][0] += int(row["detected"])
        totals[key][1] += int(row["trials"])
    output: list[dict[str, object]] = []
    for key, (detected, trials) in sorted(totals.items()):
        q, attack, timing, rho, statistic = key
        output.append(
            {
                "checkpoint": "all",
                "q": q,
                "attack": attack,
                "timing": timing,
                "rho": rho,
                "statistic": statistic,
                "detected": detected,
                "trials": trials,
                "rate": detected / trials,
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_plot(path: Path, aggregate_rows: list[dict[str, object]], q_values: list[int]) -> bool:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    combined = [row for row in aggregate_rows if row["statistic"] == "combined"]
    attacks = (
        ("spike_1", "post_commit"),
        ("sparse_16", "post_commit"),
        ("diffuse_balanced", "post_commit"),
        ("directional", "post_commit"),
        ("sample_null", "known_coordinates"),
        ("sample_null", "post_commit"),
    )
    labels = {
        ("spike_1", "post_commit"): "1-sparse, post-commit",
        ("sparse_16", "post_commit"): "16-sparse, post-commit",
        ("diffuse_balanced", "post_commit"): "diffuse, post-commit",
        ("directional", "post_commit"): "directional, post-commit",
        ("sample_null", "known_coordinates"): "sample-null, coordinates known",
        ("sample_null", "post_commit"): "sample-null, post-commit",
    }
    colors = ("#555555", "#888888", "#2F6B5F", "#78A890", "#B0B0B0", "#1F4E46")
    fig, axes = plt.subplots(1, len(q_values), figsize=(4.0 * len(q_values), 4.3), sharey=True)
    if len(q_values) == 1:
        axes = [axes]
    for axis, q in zip(axes, q_values):
        honest = next(
            row["rate"]
            for row in combined
            if row["q"] == q and row["attack"] == "honest"
        )
        axis.axhline(honest, color="#A6A6A6", linestyle="--", linewidth=1.0, label="honest FPR")
        for (attack, timing), color in zip(attacks, colors):
            selected = sorted(
                (
                    row
                    for row in combined
                    if row["q"] == q and row["attack"] == attack and row["timing"] == timing
                ),
                key=lambda row: float(row["rho"]),
            )
            axis.plot(
                [float(row["rho"]) for row in selected],
                [float(row["rate"]) for row in selected],
                marker="o",
                markersize=3.2,
                linewidth=1.3,
                color=color,
                label=labels[(attack, timing)],
            )
        axis.set_xscale("log")
        axis.set_ylim(-0.02, 1.02)
        axis.grid(True, alpha=0.25, linewidth=0.6)
        axis.set_title(f"q = {q}")
        axis.set_xlabel("relative L2 strength rho")
    axes[0].set_ylabel("detection rate / honest FPR")
    handles, legend_labels = axes[-1].get_legend_handles_labels()
    fig.legend(
        handles,
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=4,
        frameon=False,
        fontsize=8,
    )
    fig.suptitle("PCRA offline smoke test on measured heterogeneous residuals", y=0.98)
    fig.tight_layout(rect=(0.0, 0.14, 1.0, 0.92))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def build_summary(
    aggregate_rows: list[dict[str, object]],
    q_values: list[int],
    strengths: list[float],
    args: argparse.Namespace,
) -> dict[str, object]:
    combined = [row for row in aggregate_rows if row["statistic"] == "combined"]

    def lookup(q: int, attack: str, timing: str, rho: float) -> float:
        return float(
            next(
                row["rate"]
                for row in combined
                if row["q"] == q
                and row["attack"] == attack
                and row["timing"] == timing
                and float(row["rho"]) == rho
            )
        )

    max_rho = max(strengths)
    timing_contrast = []
    for q in q_values:
        known = lookup(q, "sample_null", "known_coordinates", max_rho)
        post = lookup(q, "sample_null", "post_commit", max_rho)
        honest = lookup(q, "honest", "none", 0.0)
        timing_contrast.append(
            {
                "q": q,
                "rho": max_rho,
                "honest_fpr": honest,
                "known_coordinates_detection": known,
                "post_commit_detection": post,
                "post_commit_gain": post - known,
            }
        )
    return {
        "scope": "offline protocol/statistic smoke test; not a paper-level E2-R result",
        "calibration_prompts": 6,
        "evaluation_prompts": 12,
        "checkpoints": list(CHECKPOINTS),
        "q_values": q_values,
        "strengths": strengths,
        "calibration_challenges_per_prompt_checkpoint": args.calibration_challenges,
        "evaluation_challenges_per_prompt_checkpoint": args.evaluation_challenges,
        "target_combined_alpha": args.alpha,
        "timing_contrast_at_max_strength": timing_contrast,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PCRA_DIR / "results" / "default",
    )
    parser.add_argument("--q", type=int, nargs="+", default=[64, 128, 256, 512])
    parser.add_argument(
        "--strengths",
        type=float,
        nargs="+",
        default=[0.002, 0.005, 0.01, 0.02, 0.05, 0.10],
    )
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--calibration-challenges", type=int, default=2048)
    parser.add_argument("--evaluation-challenges", type=int, default=64)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a fast two-q, two-strength validation before the default experiment.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.smoke:
        args.q = [64, 256]
        args.strengths = [0.01, 0.10]
        args.calibration_challenges = 16
        args.evaluation_challenges = 4
    if not 0.0 < args.alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    if any(q <= 0 for q in args.q):
        raise ValueError("q must be positive")
    if any(rho <= 0 for rho in args.strengths):
        raise ValueError("attack strengths must be positive")

    calibration_pairs = load_pairs(args.data_root, "calib")
    evaluation_pairs = load_pairs(args.data_root, "eval")
    thresholds, threshold_rows = calibrate_thresholds(
        calibration_pairs,
        q_values=args.q,
        challenges=args.calibration_challenges,
        alpha=args.alpha,
    )
    checkpoint_rows, case_rows = evaluate(
        evaluation_pairs,
        thresholds=thresholds,
        q_values=args.q,
        strengths=args.strengths,
        challenges=args.evaluation_challenges,
    )
    aggregate_rows = aggregate_checkpoints(checkpoint_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "thresholds.csv", threshold_rows)
    write_csv(args.output_dir / "rates_by_checkpoint.csv", checkpoint_rows)
    write_csv(args.output_dir / "rates_aggregate.csv", aggregate_rows)
    write_csv(args.output_dir / "evaluation_cases.csv", case_rows)
    summary = build_summary(aggregate_rows, args.q, args.strengths, args)
    plotted = make_plot(args.output_dir / "detection_curves.png", aggregate_rows, args.q)
    summary["plot_written"] = plotted
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
