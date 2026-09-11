"""Offline SRR-64 vs baseline comparison runner.

Protocol (mirrors the paper / frozen E2 scripts):
- honest-hetero FPR : ref = left stack tensor, cand = right stack tensor
  (same prompt id), per checkpoint C1..C3.
- honest-homo   FPR : cand = right stack eval, ref = right stack rerun
  (bit-identical path; expected ~0). We use right_eval vs right_rerun when
  available, else skip.
- tamper TPR/LocAcc : cand = right stack bundle with an attack on C2,
  ref = right stack clean bundle (self-reference, as in run_qwen_trial).

Each variant's threshold is selected on the 40 calib prompts and evaluated
on the 200 held-out prompts. Everything is loaded once into memory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from baselines import (
    scalar_detect,
    proj_detect,
    baseline_detect,
    calibrate_scalar_delta,
    calibrate_proj_delta,
)
from srr import SRRConfig, sample_srr_positions, compute_srr, srr_stat

MAIN = Path("/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace")
S28 = MAIN / "sanity_20260728_m4_m4_rtx3090" / "captures"
S27 = MAIN / "sanity_20260727" / "captures"

CHECKPOINTS = ("C1", "C2", "C3")

PAIRS: Dict[str, Dict[str, str]] = {
    "A/B": {"left_calib": "stack_a_calib", "left_eval": "stack_a_eval",
            "right_calib": "stack_b_calib", "right_eval": "stack_b_eval",
            "right_rerun": "stack_b_eval_rerun", "base": S28},
    "A/C": {"left_calib": "aprime_calib", "left_eval": "aprime_eval",
            "right_calib": "cprime_calib", "right_eval": "cprime_eval",
            "right_rerun": "", "base": S27},
    "A/D": {"left_calib": "aprime_calib", "left_eval": "aprime_eval",
            "right_calib": "dprime_calib", "right_eval": "dprime_eval",
            "right_rerun": "", "base": S27},
    "B/D": {"left_calib": "bprime_calib", "left_eval": "bprime_eval",
            "right_calib": "dprime_calib", "right_eval": "dprime_eval",
            "right_rerun": "", "base": S27},
}

PERCENTILES = [99.0, 99.5, 99.9, 99.95, 99.99]
SCALES = [0.5, 1.0, 1.5, 2.0]
TARGET_MAX_FPR = 0.10
TAMPER_CHECKPOINT = "C2"
TAMPER_STRENGTH = 0.15  # gaussian std multiplier (paper config)
SCALE_EPS = 0.10        # scale attack magnitude
NULL_EPS = 0.30         # null-space perturbation norm (fraction of block norm)


# ---------------------------------------------------------------- loading

def _prompt_seed(prompt_id: str) -> int:
    """Seed for sampling positions.

    The paper baselines use a FIXED seed_base=2026 for all prompts, so the
    sampled token/channel positions are identical across prompts (this is what
    makes the honest-hetero FPR stable and reproducible). We use the same
    constant for a faithful baseline comparison. (Secret per-request sampling
    is a separate SRR variant tracked in the notes.)
    """
    return 2026


def load_split(base: Path, split: str) -> Dict[str, Dict[str, np.ndarray]]:
    """Load all NPZ in a split dir -> {prompt_id: {C1,C2,C3: [1,16,1024]}}."""
    cap_dir = base / split / "captures"
    out: Dict[str, Dict[str, np.ndarray]] = {}
    for npz in sorted(cap_dir.glob("*.npz")):
        with np.load(npz) as d:
            out[npz.stem] = {k: d[k].astype(np.float32) for k in ("prefill__C1", "prefill__C2", "prefill__C3")}
    return out


def bundles_for(pair: str, split_kind: str) -> Tuple[Dict[str, Dict[str, np.ndarray]], Dict[str, Dict[str, np.ndarray]]]:
    cfg = PAIRS[pair]
    base = cfg["base"]
    left = load_split(base, cfg[f"left_{split_kind}"])
    right = load_split(base, cfg[f"right_{split_kind}"])
    return left, right


def _ckpt_key(ckpt: str) -> str:
    return f"prefill__{ckpt}"


# ---------------------------------------------------------------- SRR

def srr_checkpoint_detects(
    cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
    ckpt: str, cfg: SRRConfig, seed: int, gamma: float,
) -> Tuple[bool, int, np.ndarray]:
    """Return (detected, n_votes, group_scores) for one checkpoint."""
    alarm, flags, scores, _ = compute_srr(cand[_ckpt_key(ckpt)], ref[_ckpt_key(ckpt)], cfg, seed, gamma)
    return alarm, int(flags.sum()), scores


def srr_prompt_detection(
    cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
    cfg: SRRConfig, seed: int, gamma_map: Mapping[str, float],
) -> Tuple[bool, str]:
    """Detect across C1..C3; return (detected, first_mismatch_checkpoint)."""
    for ckpt in CHECKPOINTS:
        detected, nvotes, _ = srr_checkpoint_detects(cand, ref, ckpt, cfg, seed, gamma_map[ckpt])
        if detected:
            return True, ckpt
    return False, ""


def calibrate_srr_gamma(
    left_calib: Dict[str, Dict[str, np.ndarray]], right_calib: Dict[str, Dict[str, np.ndarray]],
    cfg: SRRConfig, percentile: float,
) -> Dict[str, float]:
    """Per-checkpoint gamma = percentile of max-group E/B over calib pairs."""
    shared = sorted(set(left_calib) & set(right_calib))
    ratios: Dict[str, List[float]] = {c: [] for c in CHECKPOINTS}
    for pid in shared:
        seed = _prompt_seed(pid)
        for ckpt in CHECKPOINTS:
            E, B, _ = srr_stat(left_calib[pid][_ckpt_key(ckpt)], right_calib[pid][_ckpt_key(ckpt)], cfg, seed)
            ratios[ckpt].append(float(np.max(E / (B + 1e-12))))
    gamma = {}
    for ckpt in CHECKPOINTS:
        vals = np.asarray(ratios[ckpt], dtype=np.float32)
        gamma[ckpt] = float(np.percentile(vals, percentile)) if vals.size else 0.0
    return gamma


# ---------------------------------------------------------------- baselines

def baseline_prompt_detection(
    method: str, cand: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
    seed: int, scalar_delta: Mapping[str, Mapping[str, float]],
    token_samples: int, channel_samples: int, proj_dim: int, proj_seed: int, mode: str,
) -> Tuple[bool, str]:
    return baseline_detect(method, cand, ref, seed, scalar_delta, token_samples, channel_samples, proj_dim, proj_seed, mode)


# ---------------------------------------------------------------- runner

@dataclass
class ResultRow:
    pair: str
    variant: str
    family: str
    tol_mode: str
    percentile: float
    scale: float
    calib_fpr: float
    eval_hetero_fpr: float
    eval_tamper_tpr: float
    eval_tamper_locacc: float
    tpr_gaussian: float
    tpr_stale: float
    tpr_wrong_prompt: float
    tpr_scale: float
    tpr_layer_skip: float
    tpr_null_space: float
    locacc_scale: float
    locacc_layer_skip: float
    locacc_null_space: float
    ops_per_tensor: float
    reads_per_tensor: float
    ref_bytes_per_ckpt: int


def _fpr_tpr(left: Dict[str, Dict[str, np.ndarray]], right: Dict[str, Dict[str, np.ndarray]]):
    """Return (shared_ids sorted list)."""
    return sorted(set(left) & set(right))


def main() -> None:
    out = Path(__file__).parent / "results"
    out.mkdir(parents=True, exist_ok=True)
    rows: List[ResultRow] = []

    srr_cfgs = {
        "SRR-32": SRRConfig(q=32, n_groups=4, coords_per_group=8),
        "SRR-64": SRRConfig(q=64, n_groups=4, coords_per_group=16),
        "SRR-128": SRRConfig(q=128, n_groups=4, coords_per_group=32),
    }
    # baseline variants: (name, family, token_samples, channel_samples, proj_dim, mode)
    base_variants = [
        ("scalar16", "scalar", 1, 16, 0, ""),
        ("scalar64", "scalar", 1, 64, 0, ""),
        ("projcos4", "projcos", 16, 0, 4, "tstc_projcos"),
        ("projcos8", "projcos", 16, 0, 8, "tstc_projcos"),
        ("projcos16", "projcos", 16, 0, 16, "tstc_projcos"),
        ("projscalar1_abs", "projabs", 16, 0, 1, "tstc_projabs"),
    ]

    for pair, pcfg in PAIRS.items():
        t0 = time.time()
        print(f"\n=== pair {pair} ===")
        left_calib, right_calib = bundles_for(pair, "calib")
        left_eval, right_eval = bundles_for(pair, "eval")
        eval_ids = _fpr_tpr(left_eval, right_eval)

        # ---- baseline variants ----
        for (vname, vfam, tok, chan, pdim, mode) in base_variants:
            seed = 2026
            # full grid selection: percentile x mode(ckpt/global) x scale, prefer calib FPR<=0.10 then lower FPR
            best = None
            for pctl in PERCENTILES:
                if vfam == "scalar":
                    delta = calibrate_scalar_delta(left_calib, right_calib, pctl, tok, chan, seed)
                else:
                    delta = calibrate_proj_delta(left_calib, right_calib, pctl, tok, pdim, 911, seed, mode)
                for use_global in (False, True):
                    for scale in SCALES:
                        if use_global:
                            g = max(delta["prefill"].values())
                            scaled = {"prefill": {c: g * scale for c in CHECKPOINTS}}
                            mode_name = "global_shared"
                        else:
                            scaled = {"prefill": {c: delta["prefill"][c] * scale for c in CHECKPOINTS}}
                            mode_name = "checkpoint_specific"
                        det = 0
                        for pid in _fpr_tpr(left_calib, right_calib):
                            ok, _ = baseline_prompt_detection(
                                vname, right_calib[pid], left_calib[pid], seed,
                                scaled, tok, chan, pdim, 911, mode)
                            if ok:
                                det += 1
                        cfpr = det / max(1, len(_fpr_tpr(left_calib, right_calib)))
                        feasible = 1 if cfpr <= TARGET_MAX_FPR else 0
                        key = (feasible, -cfpr)
                        if best is None or key > best[0]:
                            best = (key, scaled, mode_name, pctl, scale, cfpr)
            scaled = best[1]
            mode_name = best[2]
            pctl = best[3]
            scale = best[4]
            cfpr = best[5]
            # eval hetero FPR
            det = 0
            for pid in eval_ids:
                ok, _ = baseline_prompt_detection(
                    vname, right_eval[pid], left_eval[pid], seed,
                    scaled, tok, chan, pdim, 911, mode)
                if ok:
                    det += 1
            fpr = det / len(eval_ids)
            # tamper TPR (ref = self clean, cand = attack on C2)
            meas = _measure_tamper(
                lambda cand, ref, sd: baseline_prompt_detection(
                    vname, cand, ref, sd, scaled, tok, chan, pdim, 911, mode),
                right_eval, eval_ids,
            )
            rows.append(ResultRow(
                pair=pair, variant=vname, family=vfam,
                tol_mode=mode_name, percentile=pctl,
                scale=scale, calib_fpr=cfpr, eval_hetero_fpr=fpr,
                eval_tamper_tpr=_tpr_from(meas, "gaussian"), eval_tamper_locacc=_locacc_from(meas, "gaussian"),
                tpr_gaussian=_tpr_from(meas, "gaussian"), tpr_stale=_tpr_from(meas, "stale"),
                tpr_wrong_prompt=_tpr_from(meas, "wrong_prompt"),
                tpr_scale=_tpr_from(meas, "scale"), tpr_layer_skip=_tpr_from(meas, "layer_skip"),
                tpr_null_space=_tpr_from(meas, "null_space"),
                locacc_scale=_locacc_from(meas, "scale"), locacc_layer_skip=_locacc_from(meas, "layer_skip"),
                locacc_null_space=_locacc_from(meas, "null_space"),
                ops_per_tensor=_ops_baseline(vname, tok, chan, pdim),
                reads_per_tensor=_reads_baseline(vname, tok, chan, pdim),
                ref_bytes_per_ckpt=_bytes_baseline(vname, tok, chan, pdim),
            ))
            print(f"  {vname}: heteroFPR={fpr:.3f} gaussTPR={_tpr_from(meas,'gaussian'):.2f} scaleTPR={_tpr_from(meas,'scale'):.3f}")

        # ---- SRR variants ----
        for sname, scfg in srr_cfgs.items():
            best = None
            for percentile in PERCENTILES:
                gamma = calibrate_srr_gamma(left_calib, right_calib, scfg, percentile)
                for scale in SCALES:
                    scaled = {c: gamma[c] * scale for c in CHECKPOINTS}
                    det = 0
                    for pid in _fpr_tpr(left_calib, right_calib):
                        ok, _ = srr_prompt_detection(right_calib[pid], left_calib[pid], scfg, _prompt_seed(pid), scaled)
                        if ok:
                            det += 1
                    cfpr = det / max(1, len(_fpr_tpr(left_calib, right_calib)))
                    score = -cfpr if cfpr <= TARGET_MAX_FPR else 1.0 - cfpr
                    if best is None or score > best[0]:
                        best = (score, percentile, scale, scaled, cfpr)
            percentile, scale, scaled, cfpr = best[1], best[2], best[3], best[4]
            det = 0
            for pid in eval_ids:
                ok, _ = srr_prompt_detection(right_eval[pid], left_eval[pid], scfg, _prompt_seed(pid), scaled)
                if ok:
                    det += 1
            fpr = det / len(eval_ids)
            meas = _measure_tamper(
                lambda cand, ref, seed: srr_prompt_detection(cand, ref, scfg, seed, scaled),
                right_eval, eval_ids, srr_cfg=scfg,
            )
            rows.append(ResultRow(
                pair=pair, variant=sname, family="srr",
                tol_mode="checkpoint_specific", percentile=percentile, scale=scale,
                calib_fpr=cfpr, eval_hetero_fpr=fpr,
                eval_tamper_tpr=_tpr_from(meas, "gaussian"), eval_tamper_locacc=_locacc_from(meas, "gaussian"),
                tpr_gaussian=_tpr_from(meas, "gaussian"), tpr_stale=_tpr_from(meas, "stale"),
                tpr_wrong_prompt=_tpr_from(meas, "wrong_prompt"),
                tpr_scale=_tpr_from(meas, "scale"), tpr_layer_skip=_tpr_from(meas, "layer_skip"),
                tpr_null_space=_tpr_from(meas, "null_space"),
                locacc_scale=_locacc_from(meas, "scale"), locacc_layer_skip=_locacc_from(meas, "layer_skip"),
                locacc_null_space=_locacc_from(meas, "null_space"),
                ops_per_tensor=scfg.q * 5, reads_per_tensor=scfg.q, ref_bytes_per_ckpt=scfg.q * 2,
            ))
            print(f"  {sname}: heteroFPR={fpr:.3f} gaussTPR={_tpr_from(meas,'gaussian'):.2f} scaleTPR={_tpr_from(meas,'scale'):.3f} (p{percentile} s{scale})")

        print(f"  ({time.time()-t0:.1f}s)")

    # write CSV
    fields = [f.name for f in ResultRow.__dataclass_fields__.values()]
    with (out / "srr_vs_baseline.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r.__dict__)


def _apply_attack(
    aname: str, base_bundle: Dict[str, np.ndarray], seed: int,
    eval_ids: Sequence[str], right_eval: Dict[str, Dict[str, np.ndarray]], idx: int,
    srr_cfg=None,
) -> Dict[str, np.ndarray]:
    """Build an attacked bundle. Donor-based attacks use a neighbor prompt."""
    from attacks import (
        inject_gaussian, inject_scale, inject_stale, inject_layer_skip, inject_null_space,
    )
    if aname == "gaussian":
        return inject_gaussian(base_bundle, TAMPER_STRENGTH, seed)
    if aname == "scale":
        return inject_scale(base_bundle, SCALE_EPS, seed)
    if aname == "layer_skip":
        return inject_layer_skip(base_bundle)
    if aname in ("stale", "wrong_prompt"):
        # donor = a *different* prompt's right-eval C2 (cross-prompt substitution)
        donor_idx = (idx + 1) % len(eval_ids)
        donor_pid = eval_ids[donor_idx]
        donor = right_eval[donor_pid]
        return inject_stale(base_bundle, donor)
    if aname == "null_space":
        if srr_cfg is None:
            from srr import SRRConfig
            srr_cfg = SRRConfig(q=64, n_groups=4, coords_per_group=16)
        return inject_null_space(base_bundle, srr_cfg, seed, NULL_EPS)
    raise ValueError(aname)


ATTACK_NAMES = ("gaussian", "stale", "wrong_prompt", "scale", "layer_skip", "null_space")


def _measure_tamper(
    detect_fn, right_eval: Dict[str, Dict[str, np.ndarray]], eval_ids: Sequence[str],
    srr_cfg=None,
) -> Dict[str, Tuple[float, float]]:
    """For each attack: (TPR, LocAcc) where ref = same prompt's clean right bundle."""
    out: Dict[str, Tuple[float, float]] = {}
    n = len(eval_ids)
    for aname in ATTACK_NAMES:
        ok_all = 0
        loc = 0
        for idx, pid in enumerate(eval_ids):
            clean = right_eval[pid]
            cand = _apply_attack(aname, clean, _prompt_seed(pid), eval_ids, right_eval, idx, srr_cfg)
            detected, mm = detect_fn(cand, clean, _prompt_seed(pid))
            if detected:
                ok_all += 1
            if detected and mm == TAMPER_CHECKPOINT:
                loc += 1
        out[aname] = (ok_all / n, loc / max(1, ok_all))
    return out


def _tpr_from(meas: Dict[str, Tuple[float, float]], aname: str) -> float:
    return meas[aname][0]


def _locacc_from(meas: Dict[str, Tuple[float, float]], aname: str) -> float:
    return meas[aname][1]


def _ops_baseline(name, tok, chan, pdim):
    if name == "scalar16": return 16 * 2
    if name == "scalar64": return 64 * 2
    if name == "projscalar1_abs": return 16 * 1024 * 1
    return 16 * 1024 * pdim


def _reads_baseline(name, tok, chan, pdim):
    if name.startswith("scalar"): return chan
    if name == "projscalar1_abs": return 16
    return 16 * 1024


def _bytes_baseline(name, tok, chan, pdim):
    if name == "scalar16": return 64
    if name == "scalar64": return 256
    if name == "projscalar1_abs": return 64
    return {4: 256, 8: 512, 16: 1024}[pdim]


if __name__ == "__main__":
    main()
