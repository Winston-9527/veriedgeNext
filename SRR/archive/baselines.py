"""Baselines that delegate to the frozen ground-truth hash_chain.py.

The frozen module (`frozen_snapshot/artifacts/thc/src/hash_chain.py`) is the
exact implementation that produced the paper's Table 3/4 numbers. Using it
directly guarantees protocol fidelity (token sampling, delta quantization,
projection, chain, first-mismatch semantics).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import numpy as np

FROZEN = Path("/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace/sanity_20260727/frozen_snapshot/artifacts/thc/src")
if str(FROZEN) not in sys.path:
    sys.path.insert(0, str(FROZEN))

import hash_chain as hc  # noqa: E402

CHECKPOINTS = ("C1", "C2", "C3")


def _ckpts(bundle: Mapping[str, np.ndarray]) -> Dict[str, np.ndarray]:
    return {c: bundle[f"prefill__{c}"] for c in CHECKPOINTS}


def scalar_detect(
    cand: Mapping[str, np.ndarray], ref: Mapping[str, np.ndarray],
    seed: int, delta_map: Mapping[str, Mapping[str, float]],
    token_samples: int, channel_samples: int,
) -> Tuple[bool, str]:
    cfg = hc.HashConfig(
        mode="tstc", seed_base=seed, delta_map=dict(delta_map),
        prefill_token_samples=token_samples, prefill_channel_samples=channel_samples,
        decode_channel_samples=1,
    )
    c = hc.compute_hash_chain(_ckpts(cand), list(CHECKPOINTS), "prefill", cfg)
    r = hc.compute_hash_chain(_ckpts(ref), list(CHECKPOINTS), "prefill", cfg)
    mm = hc.first_mismatch_index(r, c)
    if mm is None:
        return False, ""
    return True, CHECKPOINTS[mm] if mm < len(CHECKPOINTS) else ""


def proj_detect(
    cand: Mapping[str, np.ndarray], ref: Mapping[str, np.ndarray],
    seed: int, delta_map: Mapping[str, Mapping[str, float]],
    token_samples: int, proj_dim: int, proj_seed: int, mode: str,
) -> Tuple[bool, str]:
    cfg = hc.HashConfig(
        mode=mode, seed_base=seed, delta_map=dict(delta_map),
        prefill_token_samples=token_samples, prefill_projection_dim=proj_dim,
        decode_channel_samples=1, projection_seed=proj_seed,
    )
    c = hc.compute_hash_chain(_ckpts(cand), list(CHECKPOINTS), "prefill", cfg)
    r = hc.compute_hash_chain(_ckpts(ref), list(CHECKPOINTS), "prefill", cfg)
    mm = hc.first_mismatch_index(r, c)
    if mm is None:
        return False, ""
    return True, CHECKPOINTS[mm] if mm < len(CHECKPOINTS) else ""


def baseline_detect(
    method: str, cand: Mapping[str, np.ndarray], ref: Mapping[str, np.ndarray],
    seed: int, delta_map: Mapping[str, Mapping[str, float]],
    token_samples: int, channel_samples: int, proj_dim: int, proj_seed: int, mode: str,
) -> Tuple[bool, str]:
    if method.startswith("scalar"):
        return scalar_detect(cand, ref, seed, delta_map, token_samples, channel_samples)
    return proj_detect(cand, ref, seed, delta_map, token_samples, proj_dim, proj_seed, mode or "tstc_projcos")


def calibrate_scalar_delta(
    left_calib: Mapping[str, Mapping[str, np.ndarray]],
    right_calib: Mapping[str, Mapping[str, np.ndarray]],
    percentile: float, token_samples: int, channel_samples: int, seed: int,
) -> Dict[str, Mapping[str, float]]:
    """delta_map[prefill][ckpt] = percentile of FULL flattened abs-diff over all
    calibration pairs (matches the paper's _calibrate_percentile). The delta is
    a per-coordinate drift scale; sampled coordinates are quantized by it."""
    shared = sorted(set(left_calib) & set(right_calib))
    gaps: Dict[str, list] = {c: [] for c in CHECKPOINTS}
    for pid in shared:
        for ckpt in CHECKPOINTS:
            l = left_calib[pid][f"prefill__{ckpt}"].reshape(-1).astype(np.float32)
            r = right_calib[pid][f"prefill__{ckpt}"].reshape(-1).astype(np.float32)
            diff = np.abs(l - r)
            gaps[ckpt].append(diff)
    concat = {c: np.concatenate([np.asarray(g, dtype=np.float32).reshape(-1) for g in gaps[c]]) if gaps[c] else np.array([], dtype=np.float32) for c in CHECKPOINTS}
    return {"prefill": {c: float(np.percentile(concat[c], percentile)) if concat[c].size else 0.0 for c in CHECKPOINTS}}


def calibrate_proj_delta(
    left_calib: Mapping[str, Mapping[str, np.ndarray]],
    right_calib: Mapping[str, Mapping[str, np.ndarray]],
    percentile: float, token_samples: int, proj_dim: int, proj_seed: int, seed: int, mode: str,
) -> Dict[str, Mapping[str, float]]:
    """delta_map[prefill][ckpt] = percentile of mean gap on calib pairs."""
    shared = sorted(set(left_calib) & set(right_calib))
    gaps: Dict[str, list] = {c: [] for c in CHECKPOINTS}
    empty = {"prefill": {}}
    for pid in shared:
        for ckpt in CHECKPOINTS:
            lc = hc.compute_hash_chain(_ckpts(left_calib[pid]), list(CHECKPOINTS), "prefill",
                hc.HashConfig(mode=mode, seed_base=seed, delta_map=dict(empty), prefill_token_samples=token_samples,
                              prefill_projection_dim=proj_dim, decode_channel_samples=1, projection_seed=proj_seed))
            rc = hc.compute_hash_chain(_ckpts(right_calib[pid]), list(CHECKPOINTS), "prefill",
                hc.HashConfig(mode=mode, seed_base=seed, delta_map=dict(empty), prefill_token_samples=token_samples,
                              prefill_projection_dim=proj_dim, decode_channel_samples=1, projection_seed=proj_seed))
            li = lc[list(CHECKPOINTS).index(ckpt)]["token_idx"]
            ri = rc[list(CHECKPOINTS).index(ckpt)]["token_idx"]
            ls = lc[list(CHECKPOINTS).index(ckpt)]["summary"]
            rs = rc[list(CHECKPOINTS).index(ckpt)]["summary"]
            if li.shape == ri.shape and np.array_equal(li, ri) and ls.shape == rs.shape:
                if mode == "tstc_projcos":
                    denom = np.maximum(np.linalg.norm(ls, axis=1) * np.linalg.norm(rs, axis=1), 1e-12)
                    g = float(np.mean(1.0 - np.sum(ls * rs, axis=1) / denom))
                else:
                    g = float(np.mean(np.abs(ls - rs)))
            else:
                g = 1.0
            gaps[ckpt].append(g)
    return {"prefill": {c: float(np.percentile(np.asarray(gaps[c], dtype=np.float32), percentile)) if gaps[c] else 0.0 for c in CHECKPOINTS}}
