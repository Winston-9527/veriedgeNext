"""P0 main table v3.1: expanded 720-prompt pool, dual-device (MPS/CUDA).

Data: workspace/captures_720/stack_a_720 (MPS bf16) vs stack_b_720 (CUDA fp32),
720 prompts (200 calib / 520 eval). Combined uses joint-calibrated max-fusion:
    S_Combo = max(u_P, u_R)  where u = smoothed ECDF rank on calibration benign
    tau_Combo = Q_{1-alpha}(S_Combo^benign)  -> FPR stays ~alpha, NOT the OR union.

All attacks built from H_B, detector compares D(H_A, H_attack).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, Sequence, Tuple

import numpy as np

from srr import SRRConfig
from attacks import inject_gaussian, inject_scale, inject_stale, inject_layer_skip

ROOT = Path("/Users/siyuan/Developer/ndss2027/workspace/captures_720")
STACKS = {"A": "stack_a_720", "B": "stack_b_720"}

CHECKPOINTS = ("C1", "C2", "C3")
ALPHA = 0.01
GAUSS_LAMBDA = 0.03
SCALE_ALPHA = 1.10

SRR_CFG = SRRConfig(q=64, n_groups=4, coords_per_group=16)
DETECTORS = ("scalar16", "projcos4", "signradial", "combined")
ATTACKS = ("gaussian", "scale", "stale", "layer_skip", "low_prec_int8", "low_prec_int4")


def _seed(_pid: str) -> int:
    return 2026


def load_split(stack: str, split: str) -> Dict[str, Dict[str, np.ndarray]]:
    cap_dir = ROOT / STACKS[stack] / "captures"
    out = {}
    for npz in sorted(cap_dir.glob("*.npz")):
        with np.load(npz) as d:
            pid = npz.stem
            split_of = pid.split("_")[0]  # p0e3 or existing ids; infer from pid list below
            out[pid] = {k: d[k].astype(np.float32)
                        for k in ("prefill__C1", "prefill__C2", "prefill__C3")}
    return out


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


def combo_score_factory(calib_honest: Dict[str, np.ndarray], seed: int = 2026):
    """Return (fP, fR, combo_score) for joint-calibrated max-fusion.

    fP/fR = smoothed ECDF of calibration benign scores (rank/(n+1));
    combo_score(cand, ref) = max(u_P, u_R) in [0,1).
    """
    def smoothed_ecdf(scores: np.ndarray):
        xs = np.sort(scores)
        n = len(xs)
        return lambda s: float(np.searchsorted(xs, s, side="right")) / (n + 1)

    fP = smoothed_ecdf(calib_honest["projcos4"])
    fR = smoothed_ecdf(calib_honest["signradial"])

    def combo_score(cand, ref):
        return max(fP(score_of("projcos4", cand, ref, seed)),
                   fR(score_of("signradial", cand, ref, seed)))
    return fP, fR, combo_score


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
        return _quantize_activation(y0, 8)
    if aname == "low_prec_int4":
        return _quantize_activation(y0, 4)
    raise ValueError(aname)


def _quantize_activation(bundle: Dict[str, np.ndarray], bits: int,
                         checkpoint: str = "C2") -> Dict[str, np.ndarray]:
    out = dict(bundle)
    t = out[_ck(checkpoint)].astype(np.float32)
    qmin, qmax = -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    scale = np.abs(t).max() / qmax + 1e-12
    tq = np.clip(np.rint(t / scale), qmin, qmax) * scale
    out[_ck(checkpoint)] = tq.astype(np.float32)
    return out


def wilson95(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    z = 1.959963984540054
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def main() -> None:
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    # load once
    stack_a = load_split("A", "all")
    stack_b = load_split("B", "all")
    # prompt id -> split
    prompts_path = Path("/Users/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/data/qwen_prompt_splits_stratified_v2_200_500.jsonl")
    pid2split = {}
    for line in open(prompts_path):
        p = json.loads(line)
        pid2split[p["prompt_id"]] = p["split"]
    calib_ids = sorted(pid for pid in stack_a if pid2split.get(pid) == "calibration" and pid in stack_b)
    eval_ids = sorted(pid for pid in stack_a if pid2split.get(pid) == "evaluation" and pid in stack_b)
    print(f"calib={len(calib_ids)} eval={len(eval_ids)}")
    seed = _seed("x")

    left_calib = {p: stack_a[p] for p in calib_ids}
    right_calib = {p: stack_b[p] for p in calib_ids}
    left_eval = {p: stack_a[p] for p in eval_ids}
    right_eval = {p: stack_b[p] for p in eval_ids}

    # ---- calibration honest scores ----
    calib_honest = {}
    for det in ("scalar16", "projcos4", "signradial"):
        calib_honest[det] = np.array([score_of(det, right_calib[p], left_calib[p], seed) for p in calib_ids])

    # ---- combined: joint-calibrated max-fusion ----
    fP, fR, combo_score = combo_score_factory(calib_honest, seed)

    calib_combo = np.array([combo_score(right_calib[p], left_calib[p]) for p in calib_ids])
    calib_honest["combined"] = calib_combo

    # ---- thresholds at nominal 1% ----
    tau = {det: float(np.quantile(calib_honest[det], 1.0 - ALPHA)) for det in DETECTORS}

    # ---- eval honest ----
    eval_honest = {}
    for det in ("scalar16", "projcos4", "signradial"):
        eval_honest[det] = np.array([score_of(det, right_eval[p], left_eval[p], seed) for p in eval_ids])
    eval_honest["combined"] = np.array([combo_score(right_eval[p], left_eval[p]) for p in eval_ids])

    # ---- eval attack scores ----
    attack_scores = {a: {} for a in ATTACKS}
    for aname in ATTACKS:
        for det in DETECTORS:
            sc = []
            for idx, p in enumerate(eval_ids):
                cand = apply_attack(aname, right_eval[p], seed, eval_ids, right_eval, idx)
                sc.append(combo_score(cand, left_eval[p]) if det == "combined"
                          else score_of(det, cand, left_eval[p], seed))
            attack_scores[aname][det] = np.array(sc, dtype=np.float64)

    # ---- assemble ----
    for det in DETECTORS:
        n_hon = len(eval_honest[det])
        k_fpr = int(np.sum(eval_honest[det] > tau[det]))
        fpr = k_fpr / n_hon
        lo, hi = wilson95(k_fpr, n_hon)
        k_cal = int(np.sum(calib_honest[det] > tau[det]))
        row = {"pair": "A/B", "detector": det, "alpha": ALPHA, "tau": tau[det],
               "calib_fpr": k_cal / max(1, len(calib_honest[det])),
               "eval_fpr_observed": fpr, "eval_fpr_ci": f"[{lo:.4f},{hi:.4f}]",
               "n_calib": len(calib_ids), "n_eval": n_hon}
        for aname in ATTACKS:
            sc = attack_scores[aname][det]
            k = int(np.sum(sc > tau[det]))
            tpr = k / len(sc)
            tlo, thi = wilson95(k, len(sc))
            row[f"tpr_{aname}"] = tpr
            row[f"tpr_{aname}_ci"] = f"[{tlo:.4f},{thi:.4f}]"
        rows.append(row)
        print(f"  {det:12s} evFPR={fpr:.4f} gauss={row['tpr_gaussian']:.3f} "
              f"scale={row['tpr_scale']:.3f} stale={row['tpr_stale']:.3f} "
              f"skip={row['tpr_layer_skip']:.3f} lp8={row['tpr_low_prec_int8']:.3f} "
              f"lp4={row['tpr_low_prec_int4']:.3f}")

    cols = list(rows[0].keys())
    with (out / "p0_main_table_720.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote results/p0_main_table_720.csv ({len(rows)} rows)")


if __name__ == "__main__":
    raise SystemExit(main())
