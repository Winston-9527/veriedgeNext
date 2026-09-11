"""Material-tamper attack families for SRR evaluation.

All attacks operate on the candidate side's captured checkpoint tensors
[1, T, D]. Only C2 (the tamper checkpoint, matching the paper) is perturbed.

Families:
- gaussian: additive iid Gaussian noise at strength*std (paper tamper).
- stale_replay / wrong_prompt: substitute C2 with another prompt's C2.
- scale_perturb: multiply C2 by (1 + epsilon)  -> the projcos blind spot.
- layer_skip_approx: substitute C2 with the SAME prompt's C1 activation
  (an approximation of skipping a layer; we have no per-layer captures).
- null_space: move C2 along a direction orthogonal to the SRR projection.
  Because SRR selects raw coordinates, we implement a projection-null
  subspace by rotating the sampled block coordinates into a near-orthogonal
  direction. Honest TPR is expected to be low here (honest boundary).
"""

from __future__ import annotations

from typing import Dict

import numpy as np

from srr import sample_srr_positions, SRRConfig


def _key(ckpt: str) -> str:
    return f"prefill__{ckpt}"


def inject_gaussian(
    bundle: Dict[str, np.ndarray], strength: float, seed: int, checkpoint: str = "C2"
) -> Dict[str, np.ndarray]:
    out = dict(bundle)
    rng = np.random.default_rng(seed)
    t = out[_key(checkpoint)]
    noise = rng.normal(0.0, strength * float(np.std(t, dtype=np.float64)), size=t.shape).astype(np.float32)
    out[_key(checkpoint)] = t.astype(np.float32) + noise
    return out


def inject_scale(
    bundle: Dict[str, np.ndarray], epsilon: float, seed: int = 0, checkpoint: str = "C2"
) -> Dict[str, np.ndarray]:
    out = dict(bundle)
    out[_key(checkpoint)] = out[_key(checkpoint)].astype(np.float32) * (1.0 + float(epsilon))
    return out


def inject_per_channel_scale(
    bundle: Dict[str, np.ndarray], alpha_up: float, alpha_dn: float, seed: int = 0, checkpoint: str = "C2"
) -> Dict[str, np.ndarray]:
    """Half the hidden channels scaled by alpha_up, half by alpha_dn (balanced).

    For SignRadial this is the hard case: u_i = sign(x_i)(y_i-x_i) gets
    +(|alpha_up|-1)|x| on up-channels and -(|alpha_dn|-1)|x| on down-channels,
    which can cancel in the numerator.
    """
    out = dict(bundle)
    t = out[_key(checkpoint)].astype(np.float32).copy()
    D = t.shape[2]
    rng = np.random.default_rng(seed)
    half = D // 2
    up_idx = rng.choice(D, size=half, replace=False)
    up_mask = np.zeros(D, dtype=bool)
    up_mask[up_idx] = True
    t[..., up_mask] *= float(alpha_up)
    t[..., ~up_mask] *= float(alpha_dn)
    out[_key(checkpoint)] = t
    return out


def inject_per_token_scale(
    bundle: Dict[str, np.ndarray], alphas, checkpoint: str = "C2"
) -> Dict[str, np.ndarray]:
    """Scale each token t by alphas[t] (per-token scaling)."""
    out = dict(bundle)
    t = out[_key(checkpoint)].astype(np.float32).copy()
    T = t.shape[1]
    for tok in range(T):
        a = alphas[tok] if tok < len(alphas) else alphas[-1]
        t[0, tok] *= float(a)
    out[_key(checkpoint)] = t
    return out


def inject_partial_replay(
    bundle: Dict[str, np.ndarray], donor: Dict[str, np.ndarray], p_replay: float, seed: int = 0, checkpoint: str = "C2"
) -> Dict[str, np.ndarray]:
    """Replace p_replay fraction of tokens with donor's (stale) tokens.

    Handles seq-len mismatch: only replace indices valid in BOTH target and donor.
    """
    out = dict(bundle)
    t = out[_key(checkpoint)].astype(np.float32).copy()
    d = donor[_key(checkpoint)].astype(np.float32).copy()
    T = t.shape[1]
    Td = d.shape[1]
    valid = min(T, Td)
    n = max(1, int(round(p_replay * valid)))
    rng = np.random.default_rng(seed)
    idx = rng.choice(valid, size=min(n, valid), replace=False)
    t[0, idx] = d[0, idx]
    out[_key(checkpoint)] = t
    return out


def inject_stale(
    bundle: Dict[str, np.ndarray], donor: Dict[str, np.ndarray], checkpoint: str = "C2"
) -> Dict[str, np.ndarray]:
    out = dict(bundle)
    out[_key(checkpoint)] = donor[_key(checkpoint)].astype(np.float32).copy()
    return out


def inject_layer_skip(
    bundle: Dict[str, np.ndarray], checkpoint: str = "C2", src_checkpoint: str = "C1"
) -> Dict[str, np.ndarray]:
    out = dict(bundle)
    out[_key(checkpoint)] = bundle[_key(src_checkpoint)].astype(np.float32).copy()
    return out


def inject_null_space(
    bundle: Dict[str, np.ndarray],
    cfg: SRRConfig,
    request_seed: int,
    eps: float,
    checkpoint: str = "C2",
) -> Dict[str, np.ndarray]:
    """Move C2 along a direction orthogonal to the sampled reference coords.

    For each sampled flat coordinate we replace the value with a perturbation
    that is orthogonal to the reference activation at that coordinate (i.e.
    keeps the same norm but moves in a direction perpendicular to the reference
    vector formed by the sampled coordinates). SRR's E/B is designed to be
    blind to a direction that preserves the reference energy B but changes the
    residual only along the orthogonal complement.
    """
    out = dict(bundle)
    t = out[_key(checkpoint)].astype(np.float32).copy()
    seq_len = t.shape[1]
    flat, _ = sample_srr_positions(cfg, request_seed, seq_len=seq_len)
    rows, cols = np.unravel_index(flat, (seq_len, t.shape[2]))
    rng = np.random.default_rng(cfg.seed_base + request_seed + 7000)
    # Build a perturbation on the sampled coords that is norm-preserving but
    # direction-orthogonal to the reference values.
    x = t[0, rows, cols].astype(np.float64)  # reference at sampled coords
    # unit direction in the reference vector's space
    norm = np.linalg.norm(x)
    if norm > 1e-12:
        # choose a vector orthogonal to x (same length, in complement of span(x))
        u = rng.standard_normal(x.shape)
        u -= np.dot(u, x) * x / (norm * norm + 1e-12)
        u /= np.linalg.norm(u) + 1e-12
        pert = eps * norm * u
    else:
        pert = rng.standard_normal(x.shape) * eps
    t[0, rows, cols] = (x + pert).astype(np.float32)
    out[_key(checkpoint)] = t
    return out
