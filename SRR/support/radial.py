"""Sampled Radial Coefficient (S_parallel).

S_parallel = |sum_{i in S} x_i (y_i - x_i)| / sum_{i in S} x_i^2

Measures how much of the residual (y-x) lies ALONG the reference activation x
(the radial / scale component), instead of total energy (SRR). For a scale
attack y = alpha x: S_parallel = |alpha - 1| (exactly). For incoherent
heterogeneous noise with mixed signs: the radial projection cancels.

This is the interpretable alternative to both SRR (energy) and 1D random
projection (seed-lottery). Detection: |P| > gamma * B  (no division needed).
"""

from __future__ import annotations

import numpy as np


def sampled_radial(
    cand: np.ndarray,
    ref: np.ndarray,
    seed: int,
    n: int = 64,
    n_groups: int = 4,
    b_min: float = 1e-3,
    gamma: float = 0.0,
) -> tuple[bool, np.ndarray, np.ndarray]:
    """Return (alarm, group_scores, group_flags) for sampled radial detection.

    alarm: >= 3 of n_groups groups have |P_g| > gamma * max(B_g, b_min).
    """
    c0 = np.asarray(cand, dtype=np.float32)[0]
    r0 = np.asarray(ref, dtype=np.float32)[0]
    T, D = c0.shape
    rng = np.random.default_rng(seed)
    flat = rng.choice(T * D, size=n, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))

    per_group = n // n_groups
    scores = np.zeros(n_groups, dtype=np.float32)
    flags = np.zeros(n_groups, dtype=np.int32)
    for g in range(n_groups):
        sl = slice(g * per_group, (g + 1) * per_group)
        x = r0[rows[sl], cols[sl]].astype(np.float64)
        y = c0[rows[sl], cols[sl]].astype(np.float64)
        diff = y - x
        P_g = float(np.sum(x * diff))
        B_g = float(np.sum(x * x))
        denom = max(B_g, b_min)
        scores[g] = float(abs(P_g) / denom)
        if abs(P_g) > gamma * denom:
            flags[g] = 1
    return bool(int(flags.sum()) >= 3), scores, flags


def sampled_radial_stat(
    cand: np.ndarray,
    ref: np.ndarray,
    seed: int,
    n: int = 64,
    n_groups: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Return per-group (P, B) without thresholding (for calibration)."""
    c0 = np.asarray(cand, dtype=np.float32)[0]
    r0 = np.asarray(ref, dtype=np.float32)[0]
    T, D = c0.shape
    rng = np.random.default_rng(seed)
    flat = rng.choice(T * D, size=n, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))
    per_group = n // n_groups
    P = np.zeros(n_groups, dtype=np.float64)
    B = np.zeros(n_groups, dtype=np.float64)
    for g in range(n_groups):
        sl = slice(g * per_group, (g + 1) * per_group)
        x = r0[rows[sl], cols[sl]].astype(np.float64)
        y = c0[rows[sl], cols[sl]].astype(np.float64)
        diff = y - x
        P[g] += float(np.sum(x * diff))
        B[g] += float(np.sum(x * x))
    return P, B


def sign_radial(
    cand: np.ndarray,
    ref: np.ndarray,
    seed: int,
    n: int = 64,
    gamma: float = 0.0,
    eps: float = 1e-12,
) -> tuple[bool, float, float, float]:
    """SignRadial S1 = |sum sign(x_i) (y_i - x_i)| / sum |x_i|.

    Single signed accumulator over ALL n coordinates (no grouping / voting):
    cancellation of honest noise happens best at full n. For a scale attack
    y = alpha x, S1 = |alpha - 1| exactly, with NO random projection seed.

    Returns (alarm, score, P, B): alarm if score > gamma.
    """
    c0 = np.asarray(cand, dtype=np.float32)[0]
    r0 = np.asarray(ref, dtype=np.float32)[0]
    # guard against seq-len mismatch (stale/wrong-prompt donors can differ)
    T = min(c0.shape[0], r0.shape[0])
    D = c0.shape[1]
    rng = np.random.default_rng(seed)
    flat = rng.choice(T * D, size=n, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))

    x = r0[rows, cols].astype(np.float64)
    y = c0[rows, cols].astype(np.float64)
    diff = y - x

    # signed accumulator: sign(x_i) * (y_i - x_i)
    P = float(np.sum(np.sign(x) * diff))
    B = float(np.sum(np.abs(x)))
    score = abs(P) / (B + eps)
    return score > gamma, score, P, B


def sign_radial_stat(
    cand: np.ndarray,
    ref: np.ndarray,
    seed: int,
    n: int = 64,
) -> tuple[float, float]:
    """Return (P, B) for SignRadial without thresholding (for calibration)."""
    c0 = np.asarray(cand, dtype=np.float32)[0]
    r0 = np.asarray(ref, dtype=np.float32)[0]
    T = min(c0.shape[0], r0.shape[0])
    D = c0.shape[1]
    rng = np.random.default_rng(seed)
    flat = rng.choice(T * D, size=n, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))
    x = r0[rows, cols].astype(np.float64)
    y = c0[rows, cols].astype(np.float64)
    diff = y - x
    P = float(np.sum(np.sign(x) * diff))
    B = float(np.sum(np.abs(x)))
    return P, B
