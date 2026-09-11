"""P0: fair fixed-FPR main table for TSTC detectors (v3 protocol).

Compares exactly 4 detectors at a UNIFIED nominal FPR:
    Scalar16, ProjCos4, SignRadial, Combined (ProjCos4 OR SignRadial)

Protocol (handbook v3):
  - x = H_A (reference), y0 = H_B (honest candidate); H_B carries benign A/B
    heterogeneity. ALL attacks are built from H_B:  H_attack = A(H_B), and the
    detector ALWAYS compares D(H_A, H_attack).
  - Thresholds: each detector's continuous score is evaluated on the
    CALIBRATION benign set; tau_D = Q_{1-alpha}(S_D^honest), alpha = 0.01 (1% FPR).
  - Combined: benign-percentile OR-fusion. u_P = F_P(S_P), u_R = F_R(S_R) (F =
    empirical CDF on calibration benign scores); S_Combo = max(u_P, u_R);
    tau_Combo = Q_{1-alpha}(S_Combo^benign) on the same calibration set.
  - Test: untouched held-out set. Honest -> observed FPR + Wilson CI; each
    attack -> TPR@1%FPR + Wilson CI.

Attacks (all from H_B):
    gaussian     H_B + lambda*RMS(H_B)*N(0,1),  lambda = 0.03
    scale        alpha*H_B,                      alpha = 1.10
    stale        replace C2 with another prompt's C2 (donor = neighbor)
    layer_skip   replace C2 with same prompt's C1
    low_prec     simulate low-precision forward on C2 (INT8 / FP8 / INT4)

Only Scalar16 / ProjCos4 / SignRadial enter this table (Scalar64, ProjCos16
are intentionally excluded to keep the story clean).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, Sequence, Tuple

import numpy as np

from srr import SRRConfig, sample_srr_positions
from radial import sign_radial_stat
from attacks import inject_gaussian, inject_scale, inject_stale, inject_layer_skip

MAIN = Path("/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace")
S28 = MAIN / "sanity_20260728_m4_m4_rtx3090" / "captures"
S27 = MAIN / "sanity_20260727" / "captures"

CHECKPOINTS = ("C1", "C2", "C3")
ALPHA = 0.01          # unified nominal FPR = 1%
GAUSS_LAMBDA = 0.03   # RMS-normalized gaussian strength (sweep later in P2)
SCALE_ALPHA = 1.10
LOW_PREC_BITS = (8, 4)  # INT8, INT4 (FP8 via quantize_fp8 if needed)

SRR_CFG = SRRConfig(q=64, n_groups=4, coords_per_group=16)

PAIRS: Dict[str, Dict[str, str]] = {
    "A/B": {"left_calib": "stack_a_calib", "left_eval": "stack_a_eval",
            "right_calib": "stack_b_calib", "right_eval": "stack_b_eval",
            "base": S28},
    "B/D": {"left_calib": "bprime_calib", "left_eval": "bprime_eval",
            "right_calib": "dprime_calib", "right_eval": "dprime_eval",
            "base": S27},
}

DETECTORS = ("scalar16", "projcos4", "signradial", "combined")
ATTACKS = ("gaussian", "scale", "stale", "layer_skip", "low_prec_int8", "low_prec_int4")


# ---------------------------------------------------------------- loading

def _seed(_pid: str) -> int:
    return 2026  # fixed seed_base (mirrors frozen baselines); fresh-secret variant separate


def load_split(base: Path, split: str) -> Dict[str, Dict[str, np.ndarray]]:
    cap_dir = base / split / "captures"
    out = {}
    for npz in sorted(cap_dir.glob("*.npz")):
        with np.load(npz) as d:
            out[npz.stem] = {k: d[k].astype(np.float32)
                             for k in ("prefill__C1", "prefill__C2", "prefill__C3")}
    return out


def bundles_for(pair: str, kind: str):
    cfg = PAIRS[pair]
    left = load_split(cfg["base"], cfg[f"left_{kind}"])
    right = load_split(cfg["base"], cfg[f"right_{kind}"])
    return left, right


def _ck(c: str) -> str:
    return f"prefill__{c}"


# ------------------------------------------------------- detector scores

def scalar_score(cand: np.ndarray, ref: np.ndarray, q: int, seed: int) -> float:
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    flat = np.random.default_rng(seed).choice(seq * c0.shape[1], size=q, replace=False)
    return float(np.abs(c0.reshape(-1)[flat] - r0.reshape(-1)[flat]).max())


def projcos_score(cand: np.ndarray, ref: np.ndarray, k: int, seed: int) -> float:
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    rng = np.random.default_rng(seed)
    rows = rng.choice(seq, size=seq, replace=False)
    rng2 = np.random.default_rng(seed + 911)
    P = rng2.normal(0.0, 1.0, (c0.shape[1], k)) / np.sqrt(c0.shape[1])
    with np.errstate(all="ignore"):
        rp = r0[rows] @ P
        cp = c0[rows] @ P
    rn = rp / (np.linalg.norm(rp, axis=1, keepdims=True) + 1e-12)
    cn = cp / (np.linalg.norm(cp, axis=1, keepdims=True) + 1e-12)
    cos = np.clip(np.sum(rn * cn, axis=1), -1.0, 1.0)
    return float(np.mean(1.0 - cos))


def signradial_score(cand: np.ndarray, ref: np.ndarray, q: int, seed: int) -> float:
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    flat = np.random.default_rng(seed).choice(seq * c0.shape[1], size=q, replace=False)
    x = r0.reshape(-1)[flat]
    y = c0.reshape(-1)[flat]
    P = float(np.sum(np.sign(x) * (y - x)))
    B = float(np.sum(np.abs(x)))
    return abs(P) / (B + 1e-12)


def _trace(fn, cand, ref, seed):
    return max(fn(cand[_ck(c)], ref[_ck(c)], seed) for c in CHECKPOINTS)


def score_of(det: str, cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray], seed: int) -> float:
    if det == "scalar16":
        return _trace(lambda c, r, s: scalar_score(c, r, 16, s), cand, ref, seed)
    if det == "projcos4":
        return _trace(lambda c, r, s: projcos_score(c, r, 4, s), cand, ref, seed)
    if det == "signradial":
        return _trace(lambda c, r, s: signradial_score(c, r, 64, s), cand, ref, seed)
    raise ValueError(det)


# ------------------------------------------------------------- attacks

def apply_attack(aname: str, y0: Dict[str, np.ndarray], seed: int,
                 eval_ids: Sequence[str], right_eval: Dict, idx: int) -> Dict[str, np.ndarray]:
    if aname == "gaussian":
        return inject_gaussian(y0, GAUSS_LAMBDA, seed)
    if aname == "scale":
        return inject_scale(y0, SCALE_ALPHA - 1.0, seed)
    if aname == "stale":
        donor = right_eval[eval_ids[(idx + 1) % len(eval_ids)]]
        return inject_stale(y0, donor)
    if aname == "layer_skip":
        return inject_layer_skip(y0)
    if aname == "low_prec_int8":
        return _quantize_activation(y0, bits=8)
    if aname == "low_prec_int4":
        return _quantize_activation(y0, bits=4)
    raise ValueError(aname)


def _quantize_activation(bundle: Dict[str, np.ndarray], bits: int,
                         checkpoint: str = "C2") -> Dict[str, np.ndarray]:
    """Simulate low-precision activation error on C2 (per-tensor symmetric int)."""
    out = dict(bundle)
    t = out[_ck(checkpoint)].astype(np.float32)
    qmin, qmax = -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    scale = np.abs(t).max() / qmax + 1e-12
    tq = np.clip(np.rint(t / scale), qmin, qmax) * scale
    out[_ck(checkpoint)] = tq.astype(np.float32)
    return out


# ------------------------------------------------------------- statistics

def wilson95(k: int, n: int) -> Tuple[float, float]:
    """Wilson score 95% CI for a proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    z = 1.959963984540054
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


# ------------------------------------------------------------- main

def main() -> None:
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for pair, _ in PAIRS.items():
        print(f"\n=== pair {pair} ===")
        left_calib, right_calib = bundles_for(pair, "calib")
        left_eval, right_eval = bundles_for(pair, "eval")
        calib_ids = sorted(set(left_calib) & set(right_calib))
        eval_ids = sorted(set(left_eval) & set(right_eval))
        print(f"  calib={len(calib_ids)} eval={len(eval_ids)}")
        seed = _seed("x")

        # ---- honest calibration scores (per detector) ----
        calib_honest: Dict[str, np.ndarray] = {}
        for det in ("scalar16", "projcos4", "signradial"):
            sc = np.array([score_of(det, right_calib[p], left_calib[p], seed) for p in calib_ids])
            calib_honest[det] = sc

        # ---- combined: OR-fusion (binary), each component at its own 1% tau ----
        # alarm = (S_P > tau_P) OR (S_R > tau_R). tau_P/tau_R are Q_{0.99} of the
        # calibration benign distributions. NOTE: on N_calib=40 the combined
        # detector's true FPR is the union (approx. 2% + drift), not exactly 1%;
        # it is reported as observed, and the sample-size limitation is stated
        # in the memo (reviewer point 8).
        tau_P = float(np.quantile(calib_honest["projcos4"], 1.0 - ALPHA))
        tau_R = float(np.quantile(calib_honest["signradial"], 1.0 - ALPHA))

        def combo_score(cand, ref):
            sP = score_of("projcos4", cand, ref, seed)
            sR = score_of("signradial", cand, ref, seed)
            return max(1.0 if sP > tau_P else 0.0, 1.0 if sR > tau_R else 0.0)

        calib_combo = np.array([combo_score(right_calib[p], left_calib[p]) for p in calib_ids])
        calib_honest["combined"] = calib_combo

        # ---- thresholds at nominal 1% FPR from calibration ----
        tau = {det: float(np.quantile(calib_honest[det], 1.0 - ALPHA)) for det in DETECTORS}

        # ---- eval honest ----
        eval_honest = {det: np.array([score_of(det, right_eval[p], left_eval[p], seed) for p in eval_ids])
                       for det in ("scalar16", "projcos4", "signradial")}
        eval_honest["combined"] = np.array([combo_score(right_eval[p], left_eval[p]) for p in eval_ids])

        # ---- eval attack scores ----
        attack_scores: Dict[str, Dict[str, np.ndarray]] = {a: {} for a in ATTACKS}
        for aname in ATTACKS:
            for det in DETECTORS:
                sc = []
                for idx, p in enumerate(eval_ids):
                    cand = apply_attack(aname, right_eval[p], seed, eval_ids, right_eval, idx)
                    if det == "combined":
                        sc.append(combo_score(cand, left_eval[p]))
                    else:
                        sc.append(score_of(det, cand, left_eval[p], seed))
                attack_scores[aname][det] = np.array(sc, dtype=np.float64)

        # ---- assemble rows ----
        # combined is a binary OR-alarm (0/1); the other detectors are
        # continuous scores with detected = score > tau.
        for det in DETECTORS:
            if det == "combined":
                def _det(s): return bool(s >= 0.5)
                tau_val = float("nan")
            else:
                def _det(s): return bool(s > tau[det])
                tau_val = tau[det]
            n_hon = len(eval_honest[det])
            k_fpr = int(sum(_det(s) for s in eval_honest[det]))
            fpr = k_fpr / n_hon
            lo, hi = wilson95(k_fpr, n_hon)
            k_cal = int(sum(_det(s) for s in calib_honest[det]))
            row = {"pair": pair, "detector": det, "alpha": ALPHA, "tau": tau_val,
                   "calib_fpr": k_cal / max(1, len(calib_honest[det])),
                   "eval_fpr_observed": fpr, "eval_fpr_ci": f"[{lo:.4f},{hi:.4f}]"}
            for aname in ATTACKS:
                sc = attack_scores[aname][det]
                k = int(sum(_det(s) for s in sc))
                n = len(sc)
                tpr = k / n
                tlo, thi = wilson95(k, n)
                row[f"tpr_{aname}"] = tpr
                row[f"tpr_{aname}_ci"] = f"[{tlo:.4f},{thi:.4f}]"
            rows.append(row)
            print(f"  {det:12s} evalFPR={fpr:.4f} gauss={row['tpr_gaussian']:.3f} "
                  f"scale={row['tpr_scale']:.3f} stale={row['tpr_stale']:.3f} "
                  f"skip={row['tpr_layer_skip']:.3f} lp8={row['tpr_low_prec_int8']:.3f} "
                  f"lp4={row['tpr_low_prec_int4']:.3f}")

    # ---- write CSV ----
    cols = list(rows[0].keys())
    with (out / "p0_main_table.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nwrote results/p0_main_table.csv ({len(rows)} rows)")


if __name__ == "__main__":
    raise SystemExit(main())
