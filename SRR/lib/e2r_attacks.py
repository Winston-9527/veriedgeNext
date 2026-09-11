"""E2-R adaptive attack constructions (pure numpy).

All constructions take the 2D ref x = H_A[k*], honest cand b = H_B[k*],
harm direction g, and attacker-assumed seed, and return the tamper e with
||e||_F = rho * ||b||_F. Homogeneous null-space family (design §4.1 Philosophy 2):
the tamper residual is projected into the target detector's null space, rho is a
free knob, honest drift leaks at honest level (TPR -> FPR).

Threat-model semantics (§4.2 alignment frame):
  - TM-2: seed = VERIFIER_SEED (2026)  -> construction aligned to checked coords.
  - TM-1: seed = a GUESS seed          -> construction misaligned; verifier still
         scores on 2026 coords, leaving an overlap residue.
"""

from __future__ import annotations

import numpy as np

from e2r_common import SR_Q, PROJ_K, DELTA


def get_proj(D: int, seed: int, k: int = PROJ_K) -> np.ndarray:
    rng2 = np.random.default_rng(seed + 911)
    return rng2.normal(0.0, 1.0, (D, k)) / np.sqrt(D)


def _sr_omega(x: np.ndarray, q: int, seed: int) -> np.ndarray:
    """Dense [T,D] array: sign(x) on the q sampled coords, 0 elsewhere."""
    T, D = x.shape
    flat = np.random.default_rng(seed).choice(T * D, size=q, replace=False)
    rows, cols = np.unravel_index(flat, (T, D))
    s = np.zeros_like(x, dtype=np.float64)
    s[rows, cols] = np.sign(x[rows, cols])
    return s


def _rescale(e: np.ndarray, rho: float, bnorm: float) -> np.ndarray:
    n = np.linalg.norm(e)
    if n < 1e-12:
        return e
    return rho * bnorm * e / n


def sign_balanced(g: np.ndarray, x: np.ndarray, b: np.ndarray,
                  seed: int, rho: float, bnorm: float) -> np.ndarray:
    """e with sum_Omega sign(x) e = 0 (SignRadial numerator nulled)."""
    s = _sr_omega(x, SR_Q, seed)
    s2 = float(np.sum(s * s))
    proj = float(np.sum(s * g)) / (s2 + 1e-12)
    e = g - proj * s
    return _rescale(e, rho, bnorm)


def _null_proj(g: np.ndarray, x: np.ndarray, seed: int) -> np.ndarray:
    """Per-row projection of g onto null(P): e[i] = g[i] - P (P^T P)^{-1} P^T g[i].

    Uses the cheap [D,k]@[k,T] path instead of materializing the DxD projector
    (D=1024, k=4 -> ~100k flops vs ~1G flops per prompt).
    """
    D = x.shape[1]
    P = get_proj(D, seed)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        Pinv = np.linalg.solve(P.T @ P, P.T)      # [k, D] = (P^T P)^{-1} P^T
        coef = Pinv @ g.T                          # [k, T]
        e = g - (P @ coef).T
    return e


def null_space_projcos(g: np.ndarray, x: np.ndarray, b: np.ndarray,
                       seed: int, rho: float, bnorm: float, p_seed: int | None = None) -> np.ndarray:
    """e with e[i]^T P = 0 for every row (ProjCos projection nulled).

    p_seed: seed for the projection matrix P. None -> use `seed` (default).
    Audit arm TM1b_knownP: p_seed = verifier seed (P public), seed = guessed
    (coordinate secrecy only on SignRadial's sampled coords).
    """
    e = _null_proj(g, x, p_seed if p_seed is not None else seed)
    return _rescale(e, rho, bnorm)


def joint_null(g: np.ndarray, x: np.ndarray, b: np.ndarray,
               seed: int, rho: float, bnorm: float, p_seed: int | None = None) -> np.ndarray:
    """e in null(P per-row) AND sum_Omega sign(x) e = 0.

    Fast construction: project g into null(P) (e0), then fix the sign-balance by
    adding lam*v where v = per-row-null(s_Omega) and lam chosen so the Omega sum
    is zero. v in null(P) and s_Omega^T v != 0 generically -> exact.
    Degenerate case (s_Omega^T v ~ 0) falls back to a full C-matrix solve.
    p_seed: projection seed (None -> `seed`). Audit: p_seed = verifier seed.
    """
    ps = p_seed if p_seed is not None else seed
    e0 = _null_proj(g, x, ps)
    s = _sr_omega(x, SR_Q, seed)               # Omega from `seed` (guessed for TM-1)
    v = _null_proj(s, x, ps)
    num = float(np.sum(s * e0))
    den = float(np.sum(s * v))
    if abs(den) > 1e-10:
        e = e0 - (num / den) * v
    else:
        e = _joint_null_full(g, x, seed, ps)
    return _rescale(e, rho, bnorm)


def _joint_null_full(g: np.ndarray, x: np.ndarray, seed: int, p_seed: int | None = None) -> np.ndarray:
    """Full equality-constrained least squares: e = g - C^T (C C^T)^{-1} C g.

    C rows: per-row P constraints (T*4) + the SR sign constraint (1). Returns e
    in the exact intersection. Used as the degenerate fallback AND for the
    constraint-rank/dimension report.
    """
    T, D = x.shape
    ps = p_seed if p_seed is not None else seed
    P = get_proj(D, ps)
    s = _sr_omega(x, SR_Q, seed)
    # C: [T*4 + 1, T*D]
    C = np.zeros((T * PROJ_K + 1, T * D), dtype=np.float64)
    for i in range(T):
        base = i * D
        for j in range(PROJ_K):
            C[i * PROJ_K + j, base:base + D] = P[:, j]
    C[T * PROJ_K, :] = s.reshape(-1)
    gv = g.reshape(-1)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        rhs = C @ gv                       # [T*4+1]
        lhs = C @ C.T                      # [T*4+1, T*4+1]
        lam = np.linalg.solve(lhs, rhs)
        e = gv - C.T @ lam
    return e.reshape(T, D)


def joint_null_report(g: np.ndarray, x: np.ndarray, seed: int) -> dict:
    """Constraint matrix rank and null-space dimension (Q2 requirement)."""
    T, D = x.shape
    P = get_proj(D, seed)
    s = _sr_omega(x, SR_Q, seed)
    C = np.zeros((T * PROJ_K + 1, T * D), dtype=np.float64)
    for i in range(T):
        base = i * D
        for j in range(PROJ_K):
            C[i * PROJ_K + j, base:base + D] = P[:, j]
    C[T * PROJ_K, :] = s.reshape(-1)
    rank = int(np.linalg.matrix_rank(C, tol=1e-9))
    return {"T": T, "D": D, "n_constraints": T * PROJ_K + 1,
            "rank": rank, "dim_null": T * D - rank,
            "independent": bool(rank == T * PROJ_K + 1)}


# ------------------------------------------------------------ tolerance-hug

def _grid_bisect(b, e_raw, x, score_fn, target, lo=0.0, hi=1.0, n_grid=60):
    """Largest lam in [lo,hi] with score(b + lam*e_raw) <= target, robust to
    non-monotone (V-shaped) scores. Sample grid, take last below-target point,
    bisect refine on the following interval."""
    grid = np.linspace(lo, hi, n_grid)
    below = None
    for lam in grid:
        if score_fn((b + lam * e_raw)[None]) <= target:
            below = lam
    if below is None:
        return 0.0
    a = below
    bnd = hi if below == grid[-1] else float(grid[list(grid).index(below) + 1])
    # bisect in [a, bnd] for the crossing (score just below target)
    lo_, hi_ = a, bnd
    for _ in range(30):
        mid = 0.5 * (lo_ + hi_)
        if score_fn((b + mid * e_raw)[None]) <= target:
            lo_ = mid
        else:
            hi_ = mid
    return lo_


def tol_hug(g: np.ndarray, x: np.ndarray, b: np.ndarray,
            seed: int, rho: float, bnorm: float, target: float,
            score_fn) -> tuple[np.ndarray, float]:
    """Hug the detector threshold: max harm direction g, clamped so the
    attacker-assumed score stays at <= (1-delta)*target. Returns (e, rho_eff).

    score_fn: (cand [1,T,D]) -> score at this boundary under the attacker's
    assumed seed (VERIFIER seed for TM-2, GUESS seed for TM-1).
    """
    u = g / (np.linalg.norm(g) + 1e-12)
    e_raw = rho * bnorm * u
    thr = (1 - DELTA) * target
    if score_fn((b + e_raw)[None]) <= thr:
        return e_raw, rho
    lam = _grid_bisect(b, e_raw, x, score_fn, thr)
    e = lam * e_raw
    return e, rho * lam


# ------------------------------------------------------------ dispatch

def construct(family: str, g: np.ndarray, x: np.ndarray, b: np.ndarray,
              seed: int, rho: float, bnorm: float,
              score_fn=None, target=None, p_seed: int | None = None) -> tuple[np.ndarray, float]:
    """Return (e, rho_eff). score_fn/target needed only for tol_hug families.
    p_seed: projection-matrix seed (None -> seed). Audit arm TM1b_knownP."""
    if family == "sign_balanced_sr":
        return sign_balanced(g, x, b, seed, rho, bnorm), rho
    if family == "null_space_projcos":
        return null_space_projcos(g, x, b, seed, rho, bnorm, p_seed=p_seed), rho
    if family == "joint_null":
        return joint_null(g, x, b, seed, rho, bnorm, p_seed=p_seed), rho
    if family in ("tol_hug_sr", "tol_hug_projcos", "tol_hug_combined"):
        assert score_fn is not None and target is not None
        return tol_hug(g, x, b, seed, rho, bnorm, target, score_fn)
    raise ValueError(family)
