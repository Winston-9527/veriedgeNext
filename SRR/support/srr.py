"""SRR (Sampled Relative Residual Energy) core.

Implements the SRR detector on prefill checkpoint activations shaped
[1, T, D] = [1, 16, 1024]. Coordinates are sampled secretly per request
seed so a malicious provider cannot adapt to the sampled positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Sequence, Tuple

import numpy as np

CHECKPOINTS: Tuple[str, ...] = ("C1", "C2", "C3")
HIDDEN_DIM = 1024
TOKENS = 16


@dataclass
class SRRConfig:
    q: int = 64                  # total sampled coordinates
    n_groups: int = 4            # number of detection groups
    coords_per_group: int = 16   # coordinates per group
    seed_base: int = 2026
    b_min: float = 1e-3          # minimum denominator energy (your pseudocode)
    flat_sampling: bool = True   # True: 64 independent flat coords (your pseudocode);
                                 # False: 8 tokens x 8 contiguous channels (handbook variant)


def _rng_for(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def sample_srr_positions(
    cfg: SRRConfig,
    request_seed: int,
    seq_len: int = TOKENS,
    hidden: int = HIDDEN_DIM,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return flat coordinate indices into [seq_len, hidden], length = q.

    Independent flat coordinates (your pseudocode): each of the q coords is
    sampled uniformly at random without replacement over the flattened
    [T, D] tensor.
    """
    rng = _rng_for(cfg.seed_base + request_seed)
    total = seq_len * hidden
    flat = rng.choice(total, size=cfg.q, replace=False)
    return flat.astype(np.int64), None


def compute_srr(
    cand: np.ndarray,
    ref: np.ndarray,
    cfg: SRRConfig,
    request_seed: int,
    gamma: float,
) -> Tuple[bool, np.ndarray, np.ndarray, np.ndarray]:
    """Compare candidate vs reference checkpoint tensors under SRR.

    Follows the exact pseudocode:
      for each group g: E_g = sum(diff^2); B_g = sum(x^2);
        denom = max(B_g, B_min); flag if E_g > gamma * denom
      alarm if >= 3 groups flag.
    Returns (alarm, group_flags, group_scores, flat_coords).
    """
    c0 = np.asarray(cand, dtype=np.float32)[0]
    r0 = np.asarray(ref, dtype=np.float32)[0]
    seq_len = min(c0.shape[0], r0.shape[0])
    flat, _ = sample_srr_positions(cfg, request_seed, seq_len=seq_len)
    rows, cols = np.unravel_index(flat, (seq_len, c0.shape[1]))

    n_groups = cfg.n_groups
    per_group = cfg.coords_per_group
    group_flags = np.zeros(n_groups, dtype=np.int32)
    group_scores = np.zeros(n_groups, dtype=np.float32)

    for g in range(n_groups):
        sl = slice(g * per_group, (g + 1) * per_group)
        x = r0[rows[sl], cols[sl]].astype(np.float64)
        y = c0[rows[sl], cols[sl]].astype(np.float64)
        diff = y - x
        E_g = float(np.sum(diff * diff))
        B_g = float(np.sum(x * x))
        denom = max(B_g, cfg.b_min)
        group_scores[g] = float(E_g / denom)
        if E_g > gamma * denom:
            group_flags[g] = 1

    alarm = bool(int(np.sum(group_flags)) >= 3)
    return alarm, group_flags, group_scores, flat


def srr_stat(
    cand: np.ndarray,
    ref: np.ndarray,
    cfg: SRRConfig,
    request_seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return per-group (E, B) without thresholding (used for calibration)."""
    c0 = np.asarray(cand, dtype=np.float32)[0]
    r0 = np.asarray(ref, dtype=np.float32)[0]
    seq_len = min(c0.shape[0], r0.shape[0])
    flat, _ = sample_srr_positions(cfg, request_seed, seq_len=seq_len)
    rows, cols = np.unravel_index(flat, (seq_len, c0.shape[1]))

    E = np.zeros(cfg.n_groups, dtype=np.float64)
    B = np.zeros(cfg.n_groups, dtype=np.float64)
    per_group = cfg.coords_per_group
    for g in range(cfg.n_groups):
        sl = slice(g * per_group, (g + 1) * per_group)
        x = r0[rows[sl], cols[sl]].astype(np.float64)
        y = c0[rows[sl], cols[sl]].astype(np.float64)
        diff = y - x
        E[g] += float(np.sum(diff * diff))
        B[g] += float(np.sum(x * x))
    return E, B, flat
