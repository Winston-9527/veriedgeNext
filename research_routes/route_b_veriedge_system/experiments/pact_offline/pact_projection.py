#!/usr/bin/env python3
"""PACT P0: exact post-commit full-tensor projection experiment.

This experiment asks one deliberately narrow question: at equal full-vector
L2 strength, does detection still collapse as attack support shrinks from 256
coordinates to one coordinate?  It uses the repository's real heterogeneous
checkpoint residuals and exact dense Rademacher projections.

This is a geometry/protocol smoke test, not a paper-level false-positive claim.
Only six calibration prompts are available in this local capture subset.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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

from pcra_offline import (  # noqa: E402
    CHECKPOINTS,
    Pair,
    higher_quantile,
    load_pairs,
    normalized_residual,
    stable_seed,
)
from quantized_gaussian import (  # noqa: E402
    coefficients as implementation_coefficients,
    lut_table,
    lut8_table,
)


@dataclass(frozen=True)
class SparseAttack:
    candidate_id: int
    support_size: int
    indices: np.ndarray
    values: np.ndarray
    relative_l2: float
    residual_dot: float
    residual_cosine: float


def parse_numbers(raw: str, cast) -> list:
    return [cast(item.strip()) for item in raw.split(",") if item.strip()]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def projection_statistics(
    residual: np.ndarray,
    attacks: list[SparseAttack],
    k_values: list[int],
    draws: int,
    domain: str,
    pair_key: str,
    batch_size: int,
    family: str,
) -> np.ndarray:
    """Return [honest + attacks, draw, K] projection-energy estimates.

    Rademacher mode materializes the exact signed projection matrix. Gaussian
    mode samples the exact joint distribution from the vectors' Gram matrix;
    this is statistically identical to materializing an iid N(0,1) matrix and
    is far cheaper for an offline experiment.
    """
    n = residual.size
    k_max = max(k_values)
    out = np.empty((1 + len(attacks), draws, len(k_values)), dtype=np.float64)
    rng = np.random.default_rng(stable_seed("PACT", domain, pair_key))
    residual32 = np.asarray(residual, dtype=np.float32)

    if family == "gaussian":
        vector_count = 1 + len(attacks)
        covariance = np.empty((vector_count, vector_count), dtype=np.float64)
        covariance[0, 0] = float(np.dot(residual, residual))
        for i, attack in enumerate(attacks, 1):
            covariance[0, i] = covariance[i, 0] = attack.residual_dot
            covariance[i, i] = float(np.dot(attack.values, attack.values))
        for i, left in enumerate(attacks, 1):
            for j, right in enumerate(attacks[: i - 1], 1):
                _, left_pos, right_pos = np.intersect1d(
                    left.indices, right.indices, assume_unique=True, return_indices=True
                )
                value = float(np.dot(left.values[left_pos], right.values[right_pos]))
                covariance[i, j] = covariance[j, i] = value

        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        tolerance = max(1.0, float(np.max(eigenvalues))) * 1e-10
        if float(np.min(eigenvalues)) < -tolerance:
            raise AssertionError(f"Gaussian Gram matrix is not PSD: {np.min(eigenvalues)}")
        root = eigenvectors @ np.diag(np.sqrt(np.clip(eigenvalues, 0.0, None)))
        raw = rng.standard_normal((draws * k_max, vector_count)) @ root.T
        raw = raw.reshape(draws, k_max, vector_count).transpose(2, 0, 1)
        prefix_energy = np.cumsum(np.square(raw), axis=2)
        for k_id, k in enumerate(k_values):
            out[:, :, k_id] = prefix_energy[:, :, k - 1] / (k * n)
        return out

    if family not in {"rademacher", "lut8", "lut16"}:
        raise ValueError(f"Unknown projection family: {family}")

    for start in range(0, draws, batch_size):
        stop = min(start + batch_size, draws)
        count = stop - start
        if family == "rademacher":
            bits = rng.integers(0, 2, size=(count * k_max, n), dtype=np.int8)
            signs = bits.astype(np.float32)
            signs *= 2.0
            signs -= 1.0
        else:
            signs = implementation_coefficients(rng, family, (count * k_max, n))

        base = (signs @ residual32).reshape(count, k_max)
        projections = [base]
        for attack in attacks:
            delta = signs[:, attack.indices] @ np.asarray(attack.values, dtype=np.float32)
            projections.append(base + delta.reshape(count, k_max))

        for vector_id, projected in enumerate(projections):
            prefix_energy = np.cumsum(np.square(projected, dtype=np.float64), axis=1)
            for k_id, k in enumerate(k_values):
                out[vector_id, start:stop, k_id] = prefix_energy[:, k - 1] / (k * n)

    return out


def calibrate(
    pairs: list[Pair],
    k_values: list[int],
    draws: int,
    alpha: float,
    batch_size: int,
    family: str,
) -> tuple[dict[tuple[str, int], float], list[dict[str, object]]]:
    samples: dict[tuple[str, int], list[float]] = {
        (checkpoint, k): [] for checkpoint in CHECKPOINTS for k in k_values
    }
    for pair in pairs:
        residual, _ = normalized_residual(pair)
        statistics = projection_statistics(
            residual,
            [],
            k_values,
            draws,
            "calibration",
            f"{pair.prompt_id}:{pair.checkpoint}",
            batch_size,
            family,
        )[0]
        for k_id, k in enumerate(k_values):
            samples[(pair.checkpoint, k)].extend(statistics[:, k_id].tolist())

    thresholds: dict[tuple[str, int], float] = {}
    rows: list[dict[str, object]] = []
    for checkpoint in CHECKPOINTS:
        for k in k_values:
            values = samples[(checkpoint, k)]
            threshold = higher_quantile(values, 1.0 - alpha)
            thresholds[(checkpoint, k)] = threshold
            rows.append(
                {
                    "checkpoint": checkpoint,
                    "K": k,
                    "threshold": threshold,
                    "calibration_prompt_seed_draws": len(values),
                    "calibration_prompts": len({p.prompt_id for p in pairs if p.checkpoint == checkpoint}),
                    "target_alpha_smoke_only": alpha,
                    "projection_family": family,
                }
            )
    return thresholds, rows


def make_attacks(
    residual: np.ndarray,
    support_size: int,
    rho: float,
    candidates: int,
    pair_key: str,
) -> list[SparseAttack]:
    """Create fixed, harm-preserving sparse candidates before any challenge seed."""
    n = residual.size
    if not 1 <= support_size <= n:
        raise ValueError(f"Invalid support {support_size} for N={n}")
    target = rho * np.sqrt(n)
    rng = np.random.default_rng(stable_seed("PACT", "candidate", pair_key, support_size, rho))
    attacks: list[SparseAttack] = []

    if support_size == 1:
        # Exact orthogonality is impossible in one dimension.  Restrict the
        # portfolio to the smallest-|r_i| coordinates and choose a nonnegative
        # cross term, making cancellation impossible and negligible.
        pool_size = min(n, max(64, candidates * 16))
        pool = np.argpartition(np.abs(residual), pool_size - 1)[:pool_size]
        chosen = rng.choice(pool, size=candidates, replace=candidates > pool_size)
        for candidate_id, index in enumerate(chosen):
            sign = 1.0 if residual[index] >= 0.0 else -1.0
            values = np.asarray([sign * target], dtype=np.float64)
            indices = np.asarray([index], dtype=np.int64)
            dot = float(residual[index] * values[0])
            cosine = dot / (np.linalg.norm(residual) * target)
            attacks.append(
                SparseAttack(candidate_id, 1, indices, values, rho, dot, float(cosine))
            )
        return attacks

    for candidate_id in range(candidates):
        indices = rng.choice(n, size=support_size, replace=False)
        restricted = residual[indices]
        values = rng.choice(np.asarray([-1.0, 1.0]), size=support_size)
        denom = float(np.dot(restricted, restricted))
        if denom > 0.0:
            values = values - float(np.dot(values, restricted)) / denom * restricted
        norm = float(np.linalg.norm(values))
        if norm <= 1e-12:
            raise RuntimeError("Degenerate orthogonal candidate")
        values = values * (target / norm)
        dot = float(np.dot(restricted, values))
        cosine = dot / (np.linalg.norm(residual) * target)
        attacks.append(
            SparseAttack(
                candidate_id,
                support_size,
                np.asarray(indices, dtype=np.int64),
                np.asarray(values, dtype=np.float64),
                rho,
                dot,
                float(cosine),
            )
        )
    return attacks


def validate_attack(residual: np.ndarray, attack: SparseAttack, rho: float) -> dict[str, float]:
    n = residual.size
    relative_l2 = float(np.linalg.norm(attack.values) / np.sqrt(n))
    if not np.isclose(relative_l2, rho, rtol=1e-6, atol=1e-10):
        raise AssertionError(f"Attack L2 mismatch: {relative_l2} != {rho}")
    if np.unique(attack.indices).size != attack.support_size:
        raise AssertionError("Attack support contains duplicates")
    if attack.support_size >= 2 and abs(attack.residual_cosine) > 1e-6:
        raise AssertionError(f"Residual cancellation constraint failed: {attack.residual_cosine}")
    if attack.support_size == 1 and attack.residual_dot < -1e-12:
        raise AssertionError("One-sparse attack cancels honest residual")

    full_energy = float(np.mean(np.square(residual)))
    attacked_energy = full_energy + (
        2.0 * attack.residual_dot + float(np.dot(attack.values, attack.values))
    ) / n
    return {
        "relative_l2": relative_l2,
        "honest_full_energy": full_energy,
        "attacked_full_energy": attacked_energy,
        "residual_dot": attack.residual_dot,
        "residual_cosine": attack.residual_cosine,
    }


def select_and_test(
    pair: Pair,
    residual: np.ndarray,
    thresholds: dict[tuple[str, int], float],
    k_values: list[int],
    supports: list[int],
    rhos: list[float],
    candidate_count: int,
    selection_draws: int,
    test_draws: int,
    batch_size: int,
    family: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    pair_key = f"{pair.prompt_id}:{pair.checkpoint}"

    # First select candidates using a seed domain that is never used for final
    # reporting.  Store the frozen decisions; do not evaluate them yet.
    settings: list[dict[str, object]] = []
    final_attacks: list[SparseAttack] = []
    final_attack_keys: dict[tuple[float, int, int], int] = {}

    for rho in rhos:
        for support in supports:
            attacks = make_attacks(residual, support, rho, candidate_count, pair_key)
            metadata = [validate_attack(residual, attack, rho) for attack in attacks]
            selection = projection_statistics(
                residual,
                attacks,
                k_values,
                selection_draws,
                f"selection:s={support}:rho={rho}",
                pair_key,
                batch_size,
                family,
            )[1:]

            # Policy K is public.  Select the distribution-aware candidate
            # independently for each K, but freeze it before the final-test seed.
            selected_by_k: dict[int, int] = {}
            for k_id, k in enumerate(k_values):
                threshold = thresholds[(pair.checkpoint, k)]
                rates = np.mean(selection[:, :, k_id] > threshold, axis=1)
                means = np.mean(selection[:, :, k_id], axis=1)
                selected_by_k[k] = int(min(range(len(attacks)), key=lambda i: (rates[i], means[i])))

            for k_id, k in enumerate(k_values):
                selected_id = selected_by_k[k]
                attack = attacks[selected_id]
                attack_key = (rho, support, selected_id)
                if attack_key not in final_attack_keys:
                    final_attack_keys[attack_key] = len(final_attacks)
                    final_attacks.append(attack)
                settings.append(
                    {
                        "rho": rho,
                        "support": support,
                        "k_id": k_id,
                        "K": k,
                        "selected_id": selected_id,
                        "attack_index": final_attack_keys[attack_key],
                        "info": metadata[selected_id],
                        "selection_rate": float(
                            np.mean(selection[selected_id, :, k_id] > thresholds[(pair.checkpoint, k)])
                        ),
                    }
                )

    # All frozen attacks now face exactly the same unseen final-test matrices.
    # This paired design removes seed noise from support-size comparisons while
    # preserving the required commit-before-realized-seed ordering.
    final = projection_statistics(
        residual,
        final_attacks,
        k_values,
        test_draws,
        "final-test",
        pair_key,
        batch_size,
        family,
    )
    honest_test = final[0]
    attacked_test = final[1:]

    for setting in settings:
        k_id = int(setting["k_id"])
        k = int(setting["K"])
        info = setting["info"]
        assert isinstance(info, dict)
        stats = attacked_test[int(setting["attack_index"]), :, k_id]
        threshold = thresholds[(pair.checkpoint, k)]
        true_energy = float(info["attacked_full_energy"])
        rel_error = np.abs(stats - true_energy) / max(true_energy, 1e-30)
        rows.append(
            {
                "prompt_id": pair.prompt_id,
                "checkpoint": pair.checkpoint,
                "N": residual.size,
                "K": k,
                "rho": setting["rho"],
                "support": setting["support"],
                "selected_candidate": setting["selected_id"],
                "candidate_portfolio": candidate_count,
                "threshold": threshold,
                "honest_fpr": float(np.mean(honest_test[:, k_id] > threshold)),
                "adaptive_detection_rate": float(np.mean(stats > threshold)),
                "selection_detection_rate": setting["selection_rate"],
                "honest_full_energy": info["honest_full_energy"],
                "attacked_full_energy": true_energy,
                "relative_l2": info["relative_l2"],
                "residual_dot": info["residual_dot"],
                "residual_cosine": info["residual_cosine"],
                "median_estimator_relative_error": float(np.median(rel_error)),
                "p90_estimator_relative_error": higher_quantile(rel_error, 0.90),
                "selection_draws": selection_draws,
                "test_draws": test_draws,
                "projection_family": family,
            }
        )
    return rows


def aggregate(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[int, float, int], list[dict[str, object]]] = {}
    for row in rows:
        key = (int(row["K"]), float(row["rho"]), int(row["support"]))
        groups.setdefault(key, []).append(row)
    output: list[dict[str, object]] = []
    for (k, rho, support), values in sorted(groups.items()):
        output.append(
            {
                "K": k,
                "rho": rho,
                "support": support,
                "pairs": len(values),
                "mean_honest_fpr": float(np.mean([float(v["honest_fpr"]) for v in values])),
                "mean_adaptive_detection_rate": float(
                    np.mean([float(v["adaptive_detection_rate"]) for v in values])
                ),
                "min_adaptive_detection_rate": float(
                    np.min([float(v["adaptive_detection_rate"]) for v in values])
                ),
                "mean_selection_detection_rate": float(
                    np.mean([float(v["selection_detection_rate"]) for v in values])
                ),
                "median_estimator_relative_error": float(
                    np.median([float(v["median_estimator_relative_error"]) for v in values])
                ),
                "max_abs_residual_cosine": float(
                    np.max(np.abs([float(v["residual_cosine"]) for v in values]))
                ),
            }
        )
    return output


def plot_results(rows: list[dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rhos = sorted({float(row["rho"]) for row in rows})
    supports = sorted({int(row["support"]) for row in rows})
    colors = {1: "#4d4d4d", 16: "#7a7a7a", 256: "#b0b0b0"}
    markers = {1: "o", 16: "s", 256: "^"}
    fig, axes = plt.subplots(1, len(rhos), figsize=(4.2 * len(rhos), 3.4), sharey=True)
    axes = np.atleast_1d(axes)
    for axis, rho in zip(axes, rhos):
        for support in supports:
            subset = [r for r in rows if float(r["rho"]) == rho and int(r["support"]) == support]
            ks = sorted({int(r["K"]) for r in subset})
            rates = [
                np.mean([float(r["adaptive_detection_rate"]) for r in subset if int(r["K"]) == k])
                for k in ks
            ]
            axis.plot(
                ks,
                rates,
                color=colors.get(support, "#555555"),
                marker=markers.get(support, "o"),
                linewidth=1.5,
                label=f"support={support}",
            )
        fpr = [
            np.mean([float(r["honest_fpr"]) for r in rows if int(r["K"]) == k])
            for k in sorted({int(r["K"]) for r in rows})
        ]
        ks_all = sorted({int(r["K"]) for r in rows})
        axis.plot(ks_all, fpr, "--", color="#222222", linewidth=1.0, label="honest FPR")
        axis.set_xscale("log", base=2)
        axis.set_ylim(-0.02, 1.02)
        axis.grid(True, color="#dddddd", linewidth=0.6)
        axis.set_title(rf"$\rho={rho:g}$")
        axis.set_xlabel("Projection rows K")
    axes[0].set_ylabel("Rate")
    axes[-1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def select_eval_pairs(pairs: list[Pair], prompt_names: list[str]) -> list[Pair]:
    if not prompt_names:
        return pairs
    wanted = set(prompt_names)
    selected = [pair for pair in pairs if pair.prompt_id in wanted]
    missing = wanted - {pair.prompt_id for pair in selected}
    if missing:
        raise ValueError(f"Unknown eval prompts: {sorted(missing)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
    )
    parser.add_argument("--output", type=Path, default=HERE / "results" / "p0")
    parser.add_argument("--k", default="1,2,4,8,16,32,64")
    parser.add_argument("--supports", default="1,16,256")
    parser.add_argument("--rhos", default="0.01,0.02,0.05")
    parser.add_argument("--eval-prompts", default="eval_001,eval_005")
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--calibration-draws", type=int, default=64)
    parser.add_argument("--selection-draws", type=int, default=64)
    parser.add_argument("--test-draws", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument(
        "--family",
        choices=("rademacher", "lut8", "lut16", "gaussian"),
        default="rademacher",
    )
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    k_values = parse_numbers(args.k, int)
    supports = parse_numbers(args.supports, int)
    rhos = parse_numbers(args.rhos, float)
    prompt_names = parse_numbers(args.eval_prompts, str)
    if args.smoke:
        k_values = [4, 16]
        supports = [1, 16, 256]
        rhos = [0.02]
        prompt_names = ["eval_001"]
        args.candidates = min(args.candidates, 3)
        args.calibration_draws = min(args.calibration_draws, 4)
        args.selection_draws = min(args.selection_draws, 4)
        args.test_draws = min(args.test_draws, 8)

    if sorted(k_values) != k_values or len(set(k_values)) != len(k_values):
        raise ValueError("K values must be unique and increasing")
    if args.alpha <= 0.0 or args.alpha >= 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if min(args.calibration_draws, args.selection_draws, args.test_draws) <= 0:
        raise ValueError("Draw counts must be positive")

    calibration_pairs = load_pairs(args.data_root, "calib")
    eval_pairs = select_eval_pairs(load_pairs(args.data_root, "eval"), prompt_names)
    print(f"Calibrating {len(calibration_pairs)} pair-checkpoints...")
    thresholds, threshold_rows = calibrate(
        calibration_pairs,
        k_values,
        args.calibration_draws,
        args.alpha,
        args.batch_size,
        args.family,
    )

    rows: list[dict[str, object]] = []
    for index, pair in enumerate(eval_pairs, 1):
        residual, _ = normalized_residual(pair)
        print(
            f"[{index}/{len(eval_pairs)}] {pair.prompt_id}:{pair.checkpoint} "
            f"N={residual.size}"
        )
        rows.extend(
            select_and_test(
                pair,
                residual,
                thresholds,
                k_values,
                supports,
                rhos,
                args.candidates,
                args.selection_draws,
                args.test_draws,
                args.batch_size,
                args.family,
            )
        )

    aggregate_rows = aggregate(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "thresholds.csv", threshold_rows)
    write_csv(args.output / "rates_by_pair.csv", rows)
    write_csv(args.output / "rates_aggregate.csv", aggregate_rows)
    plot_results(rows, args.output / "pact_detection.png")
    summary = {
        "status": "P0 geometry/protocol smoke test; not a paper-level FPR claim",
        "data_root": str(args.data_root.resolve()),
        "calibration_pair_checkpoints": len(calibration_pairs),
        "evaluation_pair_checkpoints": len(eval_pairs),
        "K": k_values,
        "supports": supports,
        "rhos": rhos,
        "candidate_portfolio": args.candidates,
        "calibration_draws_per_prompt_checkpoint": args.calibration_draws,
        "selection_draws": args.selection_draws,
        "test_draws": args.test_draws,
        "target_alpha_smoke_only": args.alpha,
        "projection_family": args.family,
        "gaussian_implementation": (
            "exact joint distribution via Gram matrix" if args.family == "gaussian" else None
        ),
        "lut8_table_sha256_float32_little_endian": (
            hashlib.sha256(lut8_table().astype("<f4").tobytes()).hexdigest()
            if args.family == "lut8"
            else None
        ),
        "lut16_table_sha256_float32_little_endian": (
            hashlib.sha256(lut_table(16).astype("<f4").tobytes()).hexdigest()
            if args.family == "lut16"
            else None
        ),
        "seed_domains": ["calibration", "selection:*", "final-test:*"],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
