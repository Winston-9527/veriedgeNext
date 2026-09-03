#!/usr/bin/env python3
"""White-box, non-anticipating EOT attack against the PCRA statistic portfolio.

The attacker knows the verifier, thresholds, and coordinate distribution, but
must commit one fixed perturbation before the realized challenge coordinates
are drawn. Optimization, candidate selection, and final evaluation use disjoint
challenge sets.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from pcra_offline import (
    CHECKPOINTS,
    DEFAULT_DATA_ROOT,
    PCRA_DIR,
    Pair,
    calibrate_thresholds,
    load_pairs,
    normalized_residual,
    stable_seed,
)


def challenge_matrix(n: int, q: int, count: int, *seed_parts: object) -> np.ndarray:
    rng = np.random.default_rng(stable_seed(*seed_parts))
    q_eff = min(q, n)
    return np.stack([rng.choice(n, size=q_eff, replace=False) for _ in range(count)])


def exact_rates(
    residual: np.ndarray,
    reference: np.ndarray,
    delta: np.ndarray,
    coordinates: np.ndarray,
    threshold: dict[str, float],
) -> dict[str, float]:
    attacked = residual[coordinates] + delta[coordinates]
    spike = np.max(np.abs(attacked), axis=1)
    energy = np.mean(np.square(attacked), axis=1)
    directional = np.abs(np.mean(np.sign(reference[coordinates]) * attacked, axis=1))
    decisions = {
        "spike": spike > threshold["spike"],
        "energy": energy > threshold["energy"],
        "directional": directional > threshold["directional"],
    }
    decisions["combined"] = decisions["spike"] | decisions["energy"] | decisions["directional"]
    return {name: float(np.mean(value)) for name, value in decisions.items()}


def normalized_delta(
    values: torch.Tensor,
    support: torch.Tensor,
    residual: torch.Tensor,
    n: int,
    budget: float,
) -> torch.Tensor:
    # Remove the component that would cancel (or amplify) the measured honest
    # heterogeneous residual. This makes the final discrepancy satisfy
    # ||r + delta||^2 = ||r||^2 + ||delta||^2, so low detection cannot be bought
    # merely by repairing the honest execution.
    basis = residual[support]
    basis_norm_sq = torch.sum(torch.square(basis))
    projected = values - torch.sum(values * basis) / torch.clamp(basis_norm_sq, min=1e-12) * basis
    amplitudes = budget * projected / torch.clamp(torch.linalg.vector_norm(projected), min=1e-12)
    return torch.zeros(n, dtype=values.dtype).scatter(0, support, amplitudes)


def surrogate_detection(
    residual: torch.Tensor,
    reference_sign: torch.Tensor,
    delta: torch.Tensor,
    coordinates: torch.Tensor,
    threshold: torch.Tensor,
    beta: float,
) -> torch.Tensor:
    attacked = residual[coordinates] + delta[coordinates]
    statistics = torch.stack(
        (
            torch.amax(torch.abs(attacked), dim=1),
            torch.mean(torch.square(attacked), dim=1),
            torch.abs(torch.mean(reference_sign[coordinates] * attacked, dim=1)),
        ),
        dim=1,
    )
    margins = statistics / threshold.unsqueeze(0) - 1.0
    per_stat_probability = torch.sigmoid(beta * margins)
    return 1.0 - torch.prod(1.0 - per_stat_probability, dim=1)


def optimize_candidate(
    pair: Pair,
    residual_np: np.ndarray,
    threshold: dict[str, float],
    q: int,
    rho: float,
    support_size: int,
    restart: int,
    steps: int,
    batch_size: int,
    train_count: int,
    selection_coordinates: np.ndarray,
    beta: float,
    learning_rate: float,
) -> tuple[np.ndarray, dict[str, float]]:
    n = residual_np.size
    rng = np.random.default_rng(
        stable_seed("adaptive-support", pair.prompt_id, pair.checkpoint, q, rho, support_size, restart)
    )
    support_size = min(support_size, n)
    support_np = (
        np.arange(n, dtype=np.int64)
        if support_size == n
        else np.sort(rng.choice(n, size=support_size, replace=False)).astype(np.int64)
    )
    initialization = rng.standard_normal(support_size).astype(np.float32)

    residual = torch.as_tensor(residual_np, dtype=torch.float32)
    reference_sign = torch.sign(torch.as_tensor(pair.reference, dtype=torch.float32))
    support = torch.as_tensor(support_np, dtype=torch.int64)
    threshold_tensor = torch.tensor(
        [threshold["spike"], threshold["energy"], threshold["directional"]], dtype=torch.float32
    ).clamp_min(1e-12)
    train_coordinates = torch.as_tensor(
        challenge_matrix(
            n,
            q,
            train_count,
            "adaptive-train",
            pair.prompt_id,
            pair.checkpoint,
            q,
            rho,
            support_size,
            restart,
        ),
        dtype=torch.int64,
    )
    values = torch.nn.Parameter(torch.as_tensor(initialization))
    optimizer = torch.optim.Adam([values], lr=learning_rate)
    generator = torch.Generator().manual_seed(
        stable_seed("adaptive-minibatch", pair.prompt_id, pair.checkpoint, q, rho, support_size, restart)
    )
    budget = rho * np.sqrt(n)

    with torch.no_grad():
        initial_delta = normalized_delta(values, support, residual, n, budget).cpu().numpy().astype(np.float64)
    best_delta = initial_delta
    best_selection = exact_rates(
        residual_np, pair.reference, best_delta, selection_coordinates, threshold
    )["combined"]

    for step in range(steps):
        batch_rows = torch.randint(0, train_count, (batch_size,), generator=generator)
        coordinates = train_coordinates[batch_rows]
        delta = normalized_delta(values, support, residual, n, budget)
        probability = surrogate_detection(
            residual, reference_sign, delta, coordinates, threshold_tensor, beta
        )
        # A bounded probability objective rewards concentrating energy when that
        # lowers the chance of sampling it, while all three tests are optimized
        # jointly through the same combined decision surrogate.
        loss = torch.mean(probability)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (step + 1) % 10 == 0 or step + 1 == steps:
            with torch.no_grad():
                candidate = normalized_delta(values, support, residual, n, budget).cpu().numpy().astype(np.float64)
            selection_rate = exact_rates(
                residual_np, pair.reference, candidate, selection_coordinates, threshold
            )["combined"]
            if selection_rate < best_selection:
                best_selection = selection_rate
                best_delta = candidate

    metadata = {
        "support_size": int(np.count_nonzero(best_delta)),
        "selection_combined": best_selection,
        "relative_l2": float(np.linalg.norm(best_delta) / np.sqrt(n)),
    }
    return best_delta, metadata


def fixed_baselines(pair: Pair, residual: np.ndarray, rho: float, q: int) -> dict[str, np.ndarray]:
    n = residual.size
    budget = rho * np.sqrt(n)
    rng = np.random.default_rng(stable_seed("fixed-baseline", pair.prompt_id, pair.checkpoint, q, rho))

    def make_harm_preserving(vector: np.ndarray) -> np.ndarray:
        active = vector != 0
        basis = residual * active
        denominator = float(np.dot(basis, basis))
        if denominator > 0:
            vector = vector - float(np.dot(vector, basis)) / denominator * basis
            vector[~active] = 0.0
        return vector * (budget / max(np.linalg.norm(vector), 1e-12))

    diffuse = make_harm_preserving(rng.choice((-1.0, 1.0), size=n).astype(np.float64))

    directional = make_harm_preserving(np.sign(pair.reference).astype(np.float64))

    sparse = np.zeros(n, dtype=np.float64)
    support = rng.choice(n, size=min(16, n), replace=False)
    sparse[support] = rng.choice((-1.0, 1.0), size=support.size)
    sparse = make_harm_preserving(sparse)
    return {"fixed_diffuse": diffuse, "fixed_directional": directional, "fixed_sparse16": sparse}


def cosine_after_attack(pair: Pair, delta_normalized: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(pair.reference))))
    attacked = pair.candidate + rms * delta_normalized
    denominator = np.linalg.norm(pair.reference) * np.linalg.norm(attacked)
    return float(np.dot(pair.reference, attacked) / denominator) if denominator > 0 else float("nan")


def residual_alignment(residual: np.ndarray, delta: np.ndarray) -> float:
    denominator = np.linalg.norm(residual) * np.linalg.norm(delta)
    return float(np.dot(residual, delta) / denominator) if denominator > 0 else 0.0


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> tuple[list[dict[str, object]], dict[str, object]]:
    calibration_pairs = load_pairs(args.data_root, "calib")
    evaluation_pairs = load_pairs(args.data_root, "eval")
    selected_pairs = [
        pair
        for pair in evaluation_pairs
        if pair.prompt_id in set(args.prompts) and pair.checkpoint in set(args.checkpoints)
    ]
    if not selected_pairs:
        raise ValueError("No evaluation pairs matched --prompts/--checkpoints")
    thresholds, _ = calibrate_thresholds(
        calibration_pairs, args.q, args.calibration_challenges, args.alpha
    )

    rows: list[dict[str, object]] = []
    for pair in selected_pairs:
        residual, _ = normalized_residual(pair)
        n = residual.size
        for q in args.q:
            threshold = {
                statistic: thresholds[(pair.checkpoint, q, statistic)]
                for statistic in ("spike", "energy", "directional")
            }
            selection_coordinates = challenge_matrix(
                n, q, args.selection_challenges, "adaptive-selection", pair.prompt_id, pair.checkpoint, q
            )
            test_coordinates = challenge_matrix(
                n, q, args.test_challenges, "adaptive-test", pair.prompt_id, pair.checkpoint, q
            )
            honest = np.zeros(n, dtype=np.float64)
            attacks_at_strength: list[tuple[float, str, np.ndarray, int, float]] = []
            for rho in args.strengths:
                for name, delta in fixed_baselines(pair, residual, rho, q).items():
                    selection_rate = exact_rates(
                        residual, pair.reference, delta, selection_coordinates, threshold
                    )["combined"]
                    attacks_at_strength.append(
                        (rho, name, delta, int(np.count_nonzero(delta)), selection_rate)
                    )

                best: tuple[np.ndarray, dict[str, float]] | None = None
                for support_size in args.support_sizes:
                    actual_support = n if support_size <= 0 else min(support_size, n)
                    for restart in range(args.restarts):
                        candidate = optimize_candidate(
                            pair=pair,
                            residual_np=residual,
                            threshold=threshold,
                            q=q,
                            rho=rho,
                            support_size=actual_support,
                            restart=restart,
                            steps=args.steps,
                            batch_size=args.batch_size,
                            train_count=args.train_challenges,
                            selection_coordinates=selection_coordinates,
                            beta=args.beta,
                            learning_rate=args.learning_rate,
                        )
                        if best is None or candidate[1]["selection_combined"] < best[1]["selection_combined"]:
                            best = candidate
                assert best is not None
                attacks_at_strength.append(
                    (
                        rho,
                        "adaptive_joint",
                        best[0],
                        int(best[1]["support_size"]),
                        float(best[1]["selection_combined"]),
                    )
                )

            honest_rates = exact_rates(residual, pair.reference, honest, test_coordinates, threshold)
            for statistic, rate in honest_rates.items():
                rows.append(
                    {
                        "prompt_id": pair.prompt_id,
                        "checkpoint": pair.checkpoint,
                        "n": n,
                        "q": q,
                        "rho": 0.0,
                        "attack": "honest",
                        "support_size": 0,
                        "selection_combined": "",
                        "statistic": statistic,
                        "test_rate": rate,
                        "relative_l2": 0.0,
                        "final_relative_residual": float(np.linalg.norm(residual) / np.sqrt(n)),
                        "delta_residual_cosine": 0.0,
                        "cosine_after_attack": cosine_after_attack(pair, honest),
                    }
                )
            for rho, name, delta, support_size, selection_rate in attacks_at_strength:
                rates = exact_rates(residual, pair.reference, delta, test_coordinates, threshold)
                for statistic, rate in rates.items():
                    rows.append(
                        {
                            "prompt_id": pair.prompt_id,
                            "checkpoint": pair.checkpoint,
                            "n": n,
                            "q": q,
                            "rho": rho,
                            "attack": name,
                            "support_size": support_size,
                            "selection_combined": selection_rate,
                            "statistic": statistic,
                            "test_rate": rate,
                            "relative_l2": float(np.linalg.norm(delta) / np.sqrt(n)),
                            "final_relative_residual": float(
                                np.linalg.norm(residual + delta) / np.sqrt(n)
                            ),
                            "delta_residual_cosine": residual_alignment(residual, delta),
                            "cosine_after_attack": cosine_after_attack(pair, delta),
                        }
                    )

    combined = [row for row in rows if row["statistic"] == "combined"]
    aggregate: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for row in combined:
        aggregate[(row["q"], row["rho"], row["attack"])].append(float(row["test_rate"]))
    aggregate_rows = [
        {
            "q": key[0],
            "rho": key[1],
            "attack": key[2],
            "mean_test_rate": float(np.mean(values)),
            "min_test_rate": float(np.min(values)),
            "max_test_rate": float(np.max(values)),
            "pair_count": len(values),
        }
        for key, values in sorted(aggregate.items())
    ]
    summary = {
        "scope": (
            "local white-box non-anticipating attack smoke test with delta orthogonal to "
            "honest residual; no semantic harm measurement"
        ),
        "pairs": len(selected_pairs),
        "prompts": args.prompts,
        "checkpoints": args.checkpoints,
        "q_values": args.q,
        "strengths": args.strengths,
        "support_candidates": args.support_sizes,
        "optimizer_steps": args.steps,
        "train_challenges": args.train_challenges,
        "selection_challenges": args.selection_challenges,
        "test_challenges": args.test_challenges,
        "aggregate": aggregate_rows,
    }
    return rows, summary


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
        default=PCRA_DIR / "results" / "adaptive",
    )
    parser.add_argument("--prompts", nargs="+", default=["eval_001", "eval_005"])
    parser.add_argument("--checkpoints", nargs="+", default=list(CHECKPOINTS))
    parser.add_argument("--q", type=int, nargs="+", default=[64, 256])
    parser.add_argument("--strengths", type=float, nargs="+", default=[0.01, 0.02, 0.05])
    parser.add_argument(
        "--support-sizes",
        type=int,
        nargs="+",
        default=[16, 256, 0],
        help="Candidate supports; 0 means dense.",
    )
    parser.add_argument("--restarts", type=int, default=1)
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--train-challenges", type=int, default=512)
    parser.add_argument("--selection-challenges", type=int, default=512)
    parser.add_argument("--test-challenges", type=int, default=2048)
    parser.add_argument("--calibration-challenges", type=int, default=2048)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--beta", type=float, default=12.0)
    parser.add_argument("--learning-rate", type=float, default=0.08)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.smoke:
        args.prompts = ["eval_001"]
        args.checkpoints = ["prefill__C1"]
        args.q = [64]
        args.strengths = [0.02]
        args.support_sizes = [16, 256, 0]
        args.steps = 20
        args.train_challenges = 128
        args.selection_challenges = 128
        args.test_challenges = 512
        args.calibration_challenges = 256
    rows, summary = run(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "adaptive_rates.csv", rows)
    write_csv(args.output_dir / "adaptive_aggregate.csv", summary["aggregate"])
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
