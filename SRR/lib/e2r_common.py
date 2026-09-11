"""E2-R shared: data loading, per-boundary scores, thresholds, seeds.

Everything here is pure numpy / stdlib — runs anywhere (local Mac for testing,
RTX6000 for the CUDA phase). Mirrors run_p0_main_table_720.py score semantics
but returns PER-BOUNDARY scores (needed for localization + tol_hug targets),
plus the §6.4 trace-max protocol for detection.

Coordinate policy (locked by design §3.2, mentor V0-2(a)/A1.3 alignment frame):
  - verifier checks coords/projection from VERIFIER_SEED = 2026
  - TM-2 attack aligns to VERIFIER_SEED; TM-1 attack aligns to a GUESS seed
  - thresholds calibrated on VERIFIER_SEED honest distribution
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Sequence, Tuple

import numpy as np

VERIFIER_SEED = 2026
PRIMARY_GUESS_SEED = 2027
GUESS_SEEDS = [2027, 12345, 777]

BOUNDARIES: Tuple[str, ...] = ("C1", "C2", "C3")
DETECTORS: Tuple[str, ...] = ("SignRadial", "ProjCos4", "Combined")
FAMILIES: Tuple[str, ...] = (
    "sign_balanced_sr", "null_space_projcos", "joint_null",
    "tol_hug_sr", "tol_hug_projcos", "tol_hug_combined",
)
RHOS = (0.002, 0.005, 0.01, 0.02, 0.05, 0.10)
ALPHA = 0.01
DELTA = 0.05
SR_Q = 64
PROJ_K = 4
BLIND_RHO = 0.01  # fixed strength for the blindspot table

DEFAULT_ROOT = Path("/Users/siyuan/Developer/ndss2027/workspace/captures_720")
DEFAULT_PROMPTS = Path(
    "/Users/siyuan/Developer/ndss2027/workspace/AdversarialEvaluation/data/qwen_prompt_splits_stratified_v2_200_500.jsonl"
)


def _ck(c: str) -> str:
    return f"prefill__{c}"


# ------------------------------------------------------------- data loading

def load_stack(root: Path, stack: str) -> Dict[str, Dict[str, np.ndarray]]:
    cap_dir = root / stack / "captures"
    out = {}
    for npz in sorted(cap_dir.glob("*.npz")):
        with np.load(npz) as d:
            out[npz.stem] = {k: d[k].astype(np.float32)
                             for k in (_ck("C1"), _ck("C2"), _ck("C3"))}
    return out


def load_splits(prompts_path: Path) -> Dict[str, str]:
    pid2split = {}
    for line in open(prompts_path):
        p = json.loads(line)
        pid2split[p["prompt_id"]] = p["split"]
    return pid2split


def load_ids(prompts_path: Path) -> Dict[str, list]:
    pid2ids = {}
    for line in open(prompts_path):
        p = json.loads(line)
        pid2ids[p["prompt_id"]] = p["input_ids"]
    return pid2ids


def data_fingerprint(root: Path, prompts_path: Path) -> Dict[str, object]:
    """Manifest data fingerprint (stack counts + prompt file sha + token stats)."""
    lens = []
    for line in open(prompts_path):
        lens.append(len(json.loads(line)["input_ids"]))
    lens = np.array(lens)
    return {
        "captures_root": str(root),
        "n_stack_a": len(list((root / "stack_a_720" / "captures").glob("*.npz"))),
        "n_stack_b": len(list((root / "stack_b_720" / "captures").glob("*.npz"))),
        "prompts_file": str(prompts_path),
        "prompts_sha256": hashlib.sha256(prompts_path.read_bytes()).hexdigest(),
        "n_prompts": int(len(lens)),
        "token_len_min": int(lens.min()), "token_len_max": int(lens.max()),
        "token_len_median": float(np.median(lens)),
    }


# ------------------------------------------------------- detector scores (per-boundary)

def sr_score(cand: np.ndarray, ref: np.ndarray, q: int, seed: int) -> float:
    """SignRadial S1 on one boundary. cand/ref shape [1, T, D]."""
    c0 = np.asarray(cand, dtype=np.float32)[0].astype(np.float64)
    r0 = np.asarray(ref, dtype=np.float32)[0].astype(np.float64)
    seq = min(c0.shape[0], r0.shape[0])
    flat = np.random.default_rng(seed).choice(seq * c0.shape[1], size=q, replace=False)
    x = r0.reshape(-1)[flat]
    y = c0.reshape(-1)[flat]
    P = float(np.sum(np.sign(x) * (y - x)))
    B = float(np.sum(np.abs(x)))
    return abs(P) / (B + 1e-12)


def projcos_score(cand: np.ndarray, ref: np.ndarray, k: int, seed: int) -> float:
    """ProjCos on one boundary. cand/ref shape [1, T, D]."""
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


def boundary_scores(cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
                    seed: int) -> Dict[str, Dict[str, float]]:
    """Per-boundary scores for all detectors. Used for localization + tol_hug targets."""
    out = {}
    for b in BOUNDARIES:
        sr = sr_score(cand[_ck(b)], ref[_ck(b)], SR_Q, seed)
        pc = projcos_score(cand[_ck(b)], ref[_ck(b)], PROJ_K, seed)
        out[b] = {"SignRadial": sr, "ProjCos4": pc}
    return out


def trace_scores(cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
                 seed: int) -> Dict[str, float]:
    """Trace-max score per detector (the §6.4 detection quantity)."""
    bs = boundary_scores(cand, ref, seed)
    return {d: max(bs[b][d] for b in BOUNDARIES) for d in ("SignRadial", "ProjCos4")}


# ------------------------------------------------------ Combined ECDF fusion

def smoothed_ecdf(xs: np.ndarray):
    xs = np.sort(np.asarray(xs, dtype=np.float64))
    n = len(xs)
    return lambda v: float(np.searchsorted(xs, v, side="right")) / (n + 1)


def combo_score_factory(calib_sr: Dict[str, np.ndarray], calib_pc: Dict[str, np.ndarray]):
    """Per-boundary ECDF-normalized max-fusion (for localization + tol_hug).

    Returns (u_sr, u_pc, combo) where u_sr/u_pc map (boundary, raw score) -> [0,1)
    ECDF rank on that boundary's calibration honest scores, and combo(cand, ref,
    seed, boundary) = max(u_sr, u_pc).
    """
    u_sr = {b: smoothed_ecdf(calib_sr[b]) for b in BOUNDARIES}
    u_pc = {b: smoothed_ecdf(calib_pc[b]) for b in BOUNDARIES}

    def combo(cand, ref, seed, boundary: str) -> float:
        sr = sr_score(cand[_ck(boundary)], ref[_ck(boundary)], SR_Q, seed)
        pc = projcos_score(cand[_ck(boundary)], ref[_ck(boundary)], PROJ_K, seed)
        return max(u_sr[boundary](sr), u_pc[boundary](pc))
    return u_sr, u_pc, combo


def combo_trace_factory(cal_trace_sr: np.ndarray, cal_trace_pc: np.ndarray):
    """§6.4 trace-max Combined (run_p0 semantics): ECDFs calibrated on trace-max
    scores, fusion = max(u_sr, u_pc) of the trace scores. Used for detection."""
    u_sr = smoothed_ecdf(cal_trace_sr)
    u_pc = smoothed_ecdf(cal_trace_pc)

    def combo_trace(cand, ref, seed) -> float:
        sr = max(sr_score(cand[_ck(b)], ref[_ck(b)], SR_Q, seed) for b in BOUNDARIES)
        pc = max(projcos_score(cand[_ck(b)], ref[_ck(b)], PROJ_K, seed) for b in BOUNDARIES)
        return max(u_sr(sr), u_pc(pc))
    return u_sr, u_pc, combo_trace


# ------------------------------------------------------------- thresholds

def calibrate(calib_ids, stack_a, stack_b, seed: int) -> Dict[str, object]:
    """Calibrate per-boundary Gamma, trace-max tau, and Combined fusion on calib.

    calib_ids: list of prompt ids; stack_a = ref (H_A), stack_b = cand (H_B).
    Returns dict with keys:
      tau_trace: {detector: scalar}           (trace-max Q_{0.99}, detection)
      gamma:     {detector: {boundary: scalar}} (per-boundary Q_{0.99}, localization + tol_hug)
      calib_honest: {detector: {boundary: array}}  (raw calib scores, for manifest)
    """
    cal_sr = {b: [] for b in BOUNDARIES}
    cal_pc = {b: [] for b in BOUNDARIES}
    cal_trace_sr, cal_trace_pc = [], []
    for pid in calib_ids:
        bs = boundary_scores(stack_b[pid], stack_a[pid], seed)
        for b in BOUNDARIES:
            cal_sr[b].append(bs[b]["SignRadial"])
            cal_pc[b].append(bs[b]["ProjCos4"])
        cal_trace_sr.append(max(bs[b]["SignRadial"] for b in BOUNDARIES))
        cal_trace_pc.append(max(bs[b]["ProjCos4"] for b in BOUNDARIES))
    cal_sr = {b: np.array(v) for b, v in cal_sr.items()}
    cal_pc = {b: np.array(v) for b, v in cal_pc.items()}
    cal_trace_sr = np.array(cal_trace_sr)
    cal_trace_pc = np.array(cal_trace_pc)

    u_sr, u_pc, combo = combo_score_factory(cal_sr, cal_pc)
    _, _, combo_trace = combo_trace_factory(cal_trace_sr, cal_trace_pc)

    # per-boundary combined (localization + tol_hug targets)
    cal_combo = {b: np.array([combo(stack_b[p], stack_a[p], seed, b)
                              for p in calib_ids]) for b in BOUNDARIES}
    # trace-max combined (detection, §6.4 run_p0 semantics)
    cal_trace_combo = np.array([combo_trace(stack_b[p], stack_a[p], seed)
                                for p in calib_ids])

    gamma = {
        "SignRadial": {b: float(np.quantile(cal_sr[b], 1 - ALPHA)) for b in BOUNDARIES},
        "ProjCos4": {b: float(np.quantile(cal_pc[b], 1 - ALPHA)) for b in BOUNDARIES},
        "Combined": {b: float(np.quantile(cal_combo[b], 1 - ALPHA)) for b in BOUNDARIES},
    }
    tau_trace = {
        "SignRadial": float(np.quantile(cal_trace_sr, 1 - ALPHA)),
        "ProjCos4": float(np.quantile(cal_trace_pc, 1 - ALPHA)),
        "Combined": float(np.quantile(cal_trace_combo, 1 - ALPHA)),
    }
    calib_honest = {
        "SignRadial": {b: cal_sr[b].tolist() for b in BOUNDARIES},
        "ProjCos4": {b: cal_pc[b].tolist() for b in BOUNDARIES},
        "Combined": {b: cal_combo[b].tolist() for b in BOUNDARIES},
    }
    return {
        "tau_trace": tau_trace, "gamma": gamma,
        "calib_honest": calib_honest, "combo": (u_sr, u_pc, combo),
        "combo_trace": combo_trace,
        "cal_trace_combo": cal_trace_combo.tolist(),
    }


def detect_trace(bs: Dict[str, Dict[str, float]], combo_trace_fn, cand, ref, seed,
                 tau: Dict[str, float]) -> Dict[str, bool]:
    """§6.4 trace-max detection per detector."""
    sr = max(bs[b]["SignRadial"] for b in BOUNDARIES)
    pc = max(bs[b]["ProjCos4"] for b in BOUNDARIES)
    det = {
        "SignRadial": bool(sr > tau["SignRadial"]),
        "ProjCos4": bool(pc > tau["ProjCos4"]),
    }
    combo = combo_trace_fn(cand, ref, seed)
    det["Combined"] = bool(combo > tau["Combined"])
    return det


def wilson95(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    z = 1.959963984540054
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)
