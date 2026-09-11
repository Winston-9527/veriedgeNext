"""Fixed-FPR comparison of TSTC detectors (fair TPR@FPR + AUROC).

Replaces the grid-searched per-method thresholds in run_srr_offline.py with a
fixed-FPR protocol, per reviewer feedback:

  For each detector D, compute its CONTINUOUS score S_D(ref, cand) on the
  independent calibration set's honest pairs, then set
      tau_D(alpha) = Q_{1-alpha}( {S_D honest calibration scores} )
  so every detector runs at the SAME nominal FPR = alpha.

  Report, on the held-out evaluation set:
    - FPR (should be ~alpha) and TPR at alpha in {0.1%, 1%, 5%}
    - AUROC per detector (area under the honest-vs-attacked score ranking)

Detectors (continuous scores over C1..C3, combined as trace = max over C1/C2/C3):
  - Scalar16 / Scalar64 : max |ref - cand| over sampled coords
  - ProjCos4 / ProjCos16: mean over sampled token-rows of 1 - cos(proj_ref, proj_cand)
  - SignRadial (SRR-64): max over groups of E_g / max(B_g, b_min)

Protocol mirrors run_srr_offline.py:
  - honest-hetero FPR : ref = left stack, cand = right stack (same prompt)
  - attacks on C2 only, ref = same prompt's clean right stack
  - calibration = 40 prompts, evaluation = 200 prompts
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from srr import SRRConfig, sample_srr_positions
from radial import sign_radial_stat
from attacks import inject_gaussian, inject_scale, inject_stale, inject_layer_skip, inject_null_space

MAIN = Path("/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace")
S28 = MAIN / "sanity_20260728_m4_m4_rtx3090" / "captures"
S27 = MAIN / "sanity_20260727" / "captures"

CHECKPOINTS = ("C1", "C2", "C3")
HIDDEN = 1024
TAMPER_CKPT = "C2"

PAIRS: Dict[str, Dict[str, str]] = {
    "A/B": {"left_calib": "stack_a_calib", "left_eval": "stack_a_eval",
            "right_calib": "stack_b_calib", "right_eval": "stack_b_eval",
            "right_rerun": "stack_b_eval_rerun", "base": S28},
    "B/D": {"left_calib": "bprime_calib", "left_eval": "bprime_eval",
            "right_calib": "dprime_calib", "right_eval": "dprime_eval",
            "right_rerun": "", "base": S27},
}

FPR_ALPHAS = (0.001, 0.01, 0.05)
ATTACK_NAMES = ("gaussian", "stale", "wrong_prompt", "scale", "layer_skip", "null_space")
TAMPER_STRENGTH = 0.15   # gaussian std multiplier
SCALE_EPS = 0.10
NULL_EPS = 0.30

SRR_CFG = SRRConfig(q=64, n_groups=4, coords_per_group=16)


# ------------------------------------------------------------------ loading

def _prompt_seed(_pid: str) -> int:
    return 2026  # fixed seed_base, mirrors frozen baselines


def load_split(base: Path, split: str) -> Dict[str, Dict[str, np.ndarray]]:
    cap_dir = base / split / "captures"
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for npz in sorted(cap_dir.glob("*.npz")):
        with np.load(npz) as d:
            out[npz.stem] = {k: d[k].astype(np.float32)
                             for k in ("prefill__C1", "prefill__C2", "prefill__C3")}
    return out


def bundles_for(pair: str, split_kind: str) -> Tuple[Dict, Dict]:
    cfg = PAIRS[pair]
    left = load_split(cfg["base"], cfg[f"left_{split_kind}"])
    right = load_split(cfg["base"], cfg[f"right_{split_kind}"])
    return left, right


def _ck(ckpt: str) -> str:
    return f"prefill__{ckpt}"


# ------------------------------------------------------- continuous scores

def _sample_flat(cfg, seed, seq_len):
    flat, _ = sample_srr_positions(cfg, seed, seq_len=seq_len)
    return flat


def scalar_score(cand: np.ndarray, ref: np.ndarray, q: int, seed: int) -> float:
    """max |ref-cand| over q sampled flat coords (mirrors hash_chain scalar)."""
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    total = seq * c0.shape[1]
    rng = np.random.default_rng(seed)
    flat = rng.choice(total, size=q, replace=False)
    c = c0.reshape(-1)[flat]
    r = r0.reshape(-1)[flat]
    return float(np.abs(c - r).max())


def projcos_score(cand: np.ndarray, ref: np.ndarray, proj_dim: int, seed: int) -> float:
    """mean over sampled token rows of (1 - cos(projected ref, projected cand)).

    Computed in float64 to avoid overflow (activations are ~1e3, hidden 1024).
    """
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    rng = np.random.default_rng(seed)
    rows = rng.choice(seq, size=seq, replace=False)
    rng2 = np.random.default_rng(seed + 911)
    P = rng2.normal(0.0, 1.0, (c0.shape[1], proj_dim)).astype(np.float64) / np.sqrt(c0.shape[1])
    with np.errstate(all="ignore"):  # numpy 2.x BLAS warns on 0-saturated inputs; harmless
        rp = r0[rows] @ P
        cp = c0[rows] @ P
    rn = rp / (np.linalg.norm(rp, axis=1, keepdims=True) + 1e-12)
    cn = cp / (np.linalg.norm(cp, axis=1, keepdims=True) + 1e-12)
    cos = np.clip(np.sum(rn * cn, axis=1), -1.0, 1.0)
    return float(np.mean(1.0 - cos))


def srr_score(cand: np.ndarray, ref: np.ndarray, cfg: SRRConfig, seed: int) -> float:
    """SignRadial continuous score: |sum sign(x)(y-x)| / sum|x| (sampled coords)."""
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    total = seq * c0.shape[1]
    rng = np.random.default_rng(seed)
    flat = rng.choice(total, size=cfg.q, replace=False)
    c = c0.reshape(-1)[flat]
    r = r0.reshape(-1)[flat]
    P = float(np.sum(np.sign(r) * (c - r)))
    B = float(np.sum(np.abs(r)))
    return abs(P) / (B + 1e-12)


def detector_scores(cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
                    name: str, seed: int) -> float:
    """Continuous trace score = max over C1/C2/C3 of per-checkpoint score."""
    best = -np.inf
    for ckpt in CHECKPOINTS:
        c = cand[_ck(ckpt)]
        r = ref[_ck(ckpt)]
        if name == "scalar16":
            s = scalar_score(c, r, 16, seed)
        elif name == "scalar64":
            s = scalar_score(c, r, 64, seed)
        elif name == "projcos4":
            s = projcos_score(c, r, 4, seed)
        elif name == "projcos16":
            s = projcos_score(c, r, 16, seed)
        elif name == "signradial":
            s = srr_score(c, r, SRR_CFG, seed)
        else:
            raise ValueError(name)
        best = max(best, s)
    return best


DETECTORS = ("scalar16", "scalar64", "projcos4", "projcos16", "signradial")


# ------------------------------------------------------------------ attacks

def apply_attack(aname: str, clean: Dict[str, np.ndarray], seed: int,
                 eval_ids: Sequence[str], right_eval: Dict, idx: int) -> Dict[str, np.ndarray]:
    if aname == "gaussian":
        return inject_gaussian(clean, TAMPER_STRENGTH, seed)
    if aname == "scale":
        return inject_scale(clean, SCALE_EPS, seed)
    if aname == "layer_skip":
        return inject_layer_skip(clean)
    if aname in ("stale", "wrong_prompt"):
        donor_pid = eval_ids[(idx + 1) % len(eval_ids)]
        return inject_stale(clean, right_eval[donor_pid])
    if aname == "null_space":
        return inject_null_space(clean, SRR_CFG, seed, NULL_EPS)
    raise ValueError(aname)


# ------------------------------------------------------------------ main

def main() -> None:
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)

    rows: List[Dict] = []
    auroc_rows: List[Dict] = []

    for pair, pcfg in PAIRS.items():
        t0 = time.time()
        print(f"\n=== pair {pair} ===")
        left_calib, right_calib = bundles_for(pair, "calib")
        left_eval, right_eval = bundles_for(pair, "eval")
        calib_ids = sorted(set(left_calib) & set(right_calib))
        eval_ids = sorted(set(left_eval) & set(right_eval))
        print(f"  calib={len(calib_ids)} eval={len(eval_ids)}")

        for det in DETECTORS:
            seed = _prompt_seed("x")
            # ---- calibration: honest scores on calib set ----
            honest_calib = []
            for pid in calib_ids:
                s = detector_scores(right_calib[pid], left_calib[pid], det, seed)
                honest_calib.append(s)
            honest_calib = np.asarray(honest_calib, dtype=np.float64)

            # ---- evaluation: honest scores ----
            honest_eval = []
            for pid in eval_ids:
                s = detector_scores(right_eval[pid], left_eval[pid], det, seed)
                honest_eval.append(s)
            honest_eval = np.asarray(honest_eval, dtype=np.float64)

            # ---- attack scores on eval (uniform protocol: D(H_A, y) where
            #      y0 = H_B and attacks start from y0; ref = H_A so attacks
            #      also carry the honest A/B nuisance) ----
            attack_scores: Dict[str, np.ndarray] = {}
            for aname in ATTACK_NAMES:
                sc = []
                for idx, pid in enumerate(eval_ids):
                    ref = left_eval[pid]                  # H_A (reference)
                    y0 = right_eval[pid]                  # H_B (base)
                    cand = apply_attack(aname, y0, seed, eval_ids, right_eval, idx)  # attack on B
                    sc.append(detector_scores(cand, ref, det, seed))  # D(H_A, attack(H_B))
                attack_scores[aname] = np.asarray(sc, dtype=np.float64)

            # ---- AUROC per attack ----
            for aname in ATTACK_NAMES:
                y = np.concatenate([np.zeros(len(honest_eval)), np.ones(len(attack_scores[aname]))])
                x = np.concatenate([honest_eval, attack_scores[aname]])
                auroc = _auc(x, y)
                auroc_rows.append({"pair": pair, "detector": det, "attack": aname,
                                   "auroc": auroc, "n_honest": len(honest_eval),
                                   "n_attack": len(attack_scores[aname])})

            # ---- fixed-FPR thresholds from CALIBRATION honest distribution ----
            for alpha in FPR_ALPHAS:
                tau = float(np.quantile(honest_calib, 1.0 - alpha))
                fpr = float(np.mean(honest_eval > tau))
                row = {"pair": pair, "detector": det, "alpha": alpha, "tau": tau,
                       "calib_fpr": float(np.mean(honest_calib > tau)),
                       "eval_fpr": fpr}
                for aname in ATTACK_NAMES:
                    row[f"tpr_{aname}"] = float(np.mean(attack_scores[aname] > tau))
                rows.append(row)

            print(f"  {det}: calib honest mean={honest_calib.mean():.3e} "
                  f"med={np.median(honest_calib):.3e} max={honest_calib.max():.3e}")
            for alpha in FPR_ALPHAS:
                tau = float(np.quantile(honest_calib, 1.0 - alpha))
                print(f"    alpha={alpha}: tau={tau:.3e} eval_fpr={np.mean(honest_eval>tau):.3f} "
                      f"gauss_TPR={np.mean(attack_scores['gaussian']>tau):.3f} "
                      f"scale_TPR={np.mean(attack_scores['scale']>tau):.3f}")

        print(f"  ({time.time()-t0:.1f}s)")

    # ---- write CSV ----
    with (out / "fixed_fpr_comparison.csv").open("w", newline="") as f:
        cols = ["pair", "detector", "alpha", "tau", "calib_fpr", "eval_fpr"] + \
               [f"tpr_{a}" for a in ATTACK_NAMES]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with (out / "fixed_fpr_auroc.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pair", "detector", "attack", "auroc", "n_honest", "n_attack"])
        w.writeheader()
        for r in auroc_rows:
            w.writerow(r)

    print(f"\nwrote results/fixed_fpr_comparison.csv and fixed_fpr_auroc.csv")


def _auc(x: np.ndarray, y: np.ndarray) -> float:
    """Area under ROC via rank statistic (Mann-Whitney). Handles ties."""
    order = np.argsort(x, kind="mergesort")
    x = x[order]
    y = y[order]
    n1 = int(np.sum(y == 1))
    n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return float("nan")
    # rank with ties = average rank
    ranks = np.empty(len(x), dtype=np.float64)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[j + 1] == x[i]:
            j += 1
        ranks[i : j + 1] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n0 * n1))


if __name__ == "__main__":
    raise SystemExit(main())
