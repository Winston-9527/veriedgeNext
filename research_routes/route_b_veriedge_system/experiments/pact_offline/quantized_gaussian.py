#!/usr/bin/env python3
"""Support-geometry experiment for zero-free quantized Gaussian coefficients."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm


HERE = Path(__file__).resolve().parent
FAMILIES = (
    "rademacher",
    "qgauss3",
    "qgauss4",
    "qgauss8",
    "lut8",
    "lut16",
    "gaussian",
)
SUPPORTS = (1, 16, 256)
K_VALUES = (1, 2, 4, 8, 16, 32)
ENERGY_RATIOS = (1.0, 1.4, 2.0, 8.0)


def quantizer_parameters(family: str) -> tuple[int, float]:
    bits = int(family.removeprefix("qgauss"))
    positive_levels = 2 ** (bits - 1)
    # Keep roughly the same +/-4-sigma range at 4 and 8 bits; three bits use
    # coarse half-integer levels +/-0.5,...,+/-3.5.
    scale = positive_levels / 4.0 if bits >= 4 else 1.0
    return positive_levels, scale


@lru_cache(maxsize=None)
def quantized_variance(family: str) -> float:
    levels, scale = quantizer_parameters(family)
    variance = 0.0
    for index in range(levels):
        lower = index / scale
        upper = (index + 1) / scale if index + 1 < levels else np.inf
        probability = 2.0 * (
            norm.sf(lower) if np.isinf(upper) else norm.cdf(upper) - norm.cdf(lower)
        )
        value = (index + 0.5) / scale
        variance += probability * value * value
    return float(variance)


@lru_cache(maxsize=None)
def lut_table(bits: int) -> np.ndarray:
    entries = 2**bits
    probabilities = (np.arange(entries, dtype=np.float64) + 0.5) / entries
    table = norm.ppf(probabilities)
    table /= np.sqrt(np.mean(np.square(table)))
    table = np.asarray(table, dtype=np.float32)
    table.setflags(write=False)
    return table


def lut8_table() -> np.ndarray:
    return lut_table(8)


def coefficients(
    rng: np.random.Generator, family: str, shape: tuple[int, ...]
) -> np.ndarray:
    if family == "rademacher":
        values = rng.integers(0, 2, size=shape, dtype=np.int8).astype(np.float32)
        values *= 2.0
        values -= 1.0
        return values
    if family == "gaussian":
        return rng.standard_normal(shape, dtype=np.float32)
    if family in {"lut8", "lut16"}:
        # A protocol can freeze these 256 float32 values and derive one uniform
        # byte per coefficient from a counter-based PRG. Mid-quantiles avoid
        # both infinities and an exact zero coefficient.
        bits = int(family.removeprefix("lut"))
        dtype = np.uint8 if bits == 8 else np.uint16
        codes = rng.integers(0, 2**bits, size=shape, dtype=dtype)
        return np.asarray(lut_table(bits)[codes], dtype=np.float32)
    levels, scale = quantizer_parameters(family)
    normal = rng.standard_normal(shape, dtype=np.float32)
    signs = np.where(normal < 0.0, -1.0, 1.0).astype(np.float32)
    indices = np.minimum(np.floor(np.abs(normal) * scale), levels - 1)
    values = signs * (indices + 0.5) / scale
    values /= np.sqrt(quantized_variance(family))
    return np.asarray(values, dtype=np.float32)


def estimator_samples(
    family: str,
    support: int,
    draws: int,
    domain: str,
    batch_size: int,
) -> np.ndarray:
    k_max = max(K_VALUES)
    seed_payload = f"PACT-Q|{family}|{support}|{domain}".encode("utf-8")
    rng_seed = int.from_bytes(hashlib.sha256(seed_payload).digest()[:8], "little")
    rng = np.random.default_rng(rng_seed)
    output = np.empty((draws, len(K_VALUES)), dtype=np.float64)
    for start in range(0, draws, batch_size):
        stop = min(start + batch_size, draws)
        count = stop - start
        if family == "gaussian":
            projected = rng.standard_normal((count, k_max), dtype=np.float32)
        else:
            values = coefficients(rng, family, (count, k_max, support))
            projected = np.sum(values, axis=2, dtype=np.float64) / np.sqrt(support)
        prefix = np.cumsum(np.square(projected, dtype=np.float64), axis=1)
        for k_id, k in enumerate(K_VALUES):
            output[start:stop, k_id] = prefix[:, k - 1] / k
    return output


def higher_quantile(values: np.ndarray, probability: float) -> float:
    try:
        return float(np.quantile(values, probability, method="higher"))
    except TypeError:
        return float(np.quantile(values, probability, interpolation="higher"))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results" / "quantized_gaussian")
    parser.add_argument("--calibration-draws", type=int, default=20_000)
    parser.add_argument("--test-draws", type=int, default=20_000)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--alpha", type=float, default=0.01)
    parser.add_argument("--families", default=",".join(FAMILIES))
    args = parser.parse_args()

    selected_families = tuple(item.strip() for item in args.families.split(",") if item.strip())
    unknown = set(selected_families) - set(FAMILIES)
    if unknown:
        raise ValueError(f"Unknown families: {sorted(unknown)}")

    moment_rows: list[dict[str, object]] = []
    result_rows: list[dict[str, object]] = []
    coverage_rows: list[dict[str, object]] = []
    for family in selected_families:
        probe_rng = np.random.default_rng(20260824 + FAMILIES.index(family))
        probe = coefficients(probe_rng, family, (1_000_000,))
        moment_rows.append(
            {
                "family": family,
                "empirical_mean": float(np.mean(probe)),
                "empirical_variance": float(np.var(probe)),
                "empirical_zero_rate": float(np.mean(probe == 0.0)),
                "empirical_excess_kurtosis": float(
                    np.mean(np.power(probe - np.mean(probe), 4)) / np.var(probe) ** 2 - 3.0
                ),
                "analytic_quantized_variance_before_normalization": (
                    quantized_variance(family) if family.startswith("qgauss") else ""
                ),
            }
        )
        calibration = estimator_samples(
            family, 256, args.calibration_draws, "calibration", args.batch_size
        )
        thresholds = [
            higher_quantile(calibration[:, k_id], 1.0 - args.alpha)
            for k_id in range(len(K_VALUES))
        ]
        for support in SUPPORTS:
            test = estimator_samples(family, support, args.test_draws, "test", args.batch_size)
            simultaneous_failure = np.zeros(args.test_draws, dtype=bool)
            for k_id, k in enumerate(K_VALUES):
                marginal_lower = float(chi2.ppf(args.alpha / 2.0, k) / k)
                marginal_upper = float(chi2.ppf(1.0 - args.alpha / 2.0, k) / k)
                marginal_failure = (test[:, k_id] < marginal_lower) | (
                    test[:, k_id] > marginal_upper
                )
                per_tail = args.alpha / (2.0 * len(K_VALUES))
                simultaneous_lower = float(chi2.ppf(per_tail, k) / k)
                simultaneous_upper = float(chi2.ppf(1.0 - per_tail, k) / k)
                simultaneous_failure |= (test[:, k_id] < simultaneous_lower) | (
                    test[:, k_id] > simultaneous_upper
                )
                coverage_rows.append(
                    {
                        "family": family,
                        "support": support,
                        "K": k,
                        "nominal_marginal_coverage": 1.0 - args.alpha,
                        "empirical_marginal_coverage": float(1.0 - np.mean(marginal_failure)),
                    }
                )
                for ratio in ENERGY_RATIOS:
                    result_rows.append(
                        {
                            "family": family,
                            "K": k,
                            "support": support,
                            "energy_ratio": ratio,
                            "threshold_calibrated_on_support_256": thresholds[k_id],
                            "rate": float(np.mean(ratio * test[:, k_id] > thresholds[k_id])),
                            "calibration_draws": args.calibration_draws,
                            "test_draws": args.test_draws,
                        }
                    )
            coverage_rows.append(
                {
                    "family": family,
                    "support": support,
                    "K": "all_Bonferroni",
                    "nominal_marginal_coverage": 1.0 - args.alpha,
                    "empirical_marginal_coverage": float(1.0 - np.mean(simultaneous_failure)),
                }
            )

    spread_rows: list[dict[str, object]] = []
    for family in selected_families:
        for k in K_VALUES:
            for ratio in ENERGY_RATIOS:
                group = [
                    row
                    for row in result_rows
                    if row["family"] == family
                    and int(row["K"]) == k
                    and float(row["energy_ratio"]) == ratio
                ]
                rates = [float(row["rate"]) for row in group]
                spread_rows.append(
                    {
                        "family": family,
                        "K": k,
                        "energy_ratio": ratio,
                        "min_rate": min(rates),
                        "max_rate": max(rates),
                        "support_spread": max(rates) - min(rates),
                    }
                )

    family_rows: list[dict[str, object]] = []
    for family in selected_families:
        attack_spreads = [
            float(row["support_spread"])
            for row in spread_rows
            if row["family"] == family and float(row["energy_ratio"]) > 1.0
        ]
        honest_spreads = [
            float(row["support_spread"])
            for row in spread_rows
            if row["family"] == family and float(row["energy_ratio"]) == 1.0
        ]
        family_rows.append(
            {
                "family": family,
                "max_attack_support_spread": max(attack_spreads),
                "median_attack_support_spread": float(np.median(attack_spreads)),
                "max_honest_support_fpr_spread": max(honest_spreads),
            }
        )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "coefficient_moments.csv", moment_rows)
    write_csv(args.output / "rates.csv", result_rows)
    write_csv(args.output / "support_spreads.csv", spread_rows)
    write_csv(args.output / "family_summary.csv", family_rows)
    write_csv(args.output / "chi_square_coverage.csv", coverage_rows)
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "status": "coefficient-geometry experiment; not real-residual calibration",
                "coefficient_families": list(selected_families),
                "supports": list(SUPPORTS),
                "K": list(K_VALUES),
                "energy_ratios": list(ENERGY_RATIOS),
                "calibration_support": 256,
                "alpha": args.alpha,
                "zero_free_quantizers": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
