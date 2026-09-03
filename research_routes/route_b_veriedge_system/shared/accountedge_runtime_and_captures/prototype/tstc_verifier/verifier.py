from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChallengeResult:
    accepted: bool
    first_mismatch_checkpoint: str | None
    max_delta: float
    chain_head_a: str
    chain_head_b: str


def _projection_matrix(dim: int, sketch_dim: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(dim, sketch_dim))
    return matrix / np.linalg.norm(matrix, axis=0, keepdims=True)


def sketch_tensor(tensor: np.ndarray, sketch_dim: int = 4, seed: int = 7) -> np.ndarray:
    """Return a small projected-token sketch for a token x hidden tensor."""
    if tensor.ndim != 2:
        raise ValueError("expected a token x hidden tensor")
    projection = _projection_matrix(tensor.shape[1], sketch_dim, seed)
    return tensor @ projection


def digest_chain(sketches: dict[str, np.ndarray]) -> dict[str, str]:
    chain_head = "0" * 64
    digests: dict[str, str] = {}
    for checkpoint in sorted(sketches):
        rounded = np.round(sketches[checkpoint], 6).tolist()
        payload = json.dumps(
            {"prev": chain_head, "checkpoint": checkpoint, "sketch": rounded},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        chain_head = hashlib.sha256(payload).hexdigest()
        digests[checkpoint] = chain_head
    return digests


def compare_digest_chains(
    sketches_a: dict[str, np.ndarray],
    sketches_b: dict[str, np.ndarray],
    tolerance: float,
) -> ChallengeResult:
    chain_a = digest_chain(sketches_a)
    chain_b = digest_chain(sketches_b)
    first_mismatch = None
    max_delta = 0.0
    for checkpoint in sorted(set(sketches_a) & set(sketches_b)):
        delta = float(np.max(np.abs(sketches_a[checkpoint] - sketches_b[checkpoint])))
        max_delta = max(max_delta, delta)
        if first_mismatch is None and delta > tolerance:
            first_mismatch = checkpoint

    accepted = first_mismatch is None
    last_a = chain_a[sorted(chain_a)[-1]]
    last_b = chain_b[sorted(chain_b)[-1]]
    return ChallengeResult(
        accepted=accepted,
        first_mismatch_checkpoint=first_mismatch,
        max_delta=max_delta,
        chain_head_a=last_a,
        chain_head_b=last_b,
    )

