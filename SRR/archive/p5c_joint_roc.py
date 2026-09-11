"""Joint OR-gate ROC/FPR: SignRadial + ProjCos.

Combine SignRadial (radial detector) and ProjCos (angular detector) with an OR
gate: alarm if EITHER exceeds its threshold. Sweep both thresholds to build the
joint ROC (TPR vs FPR) across all attack families on the A/B captures.

This answers:
  - does the OR gate cover both methods' blind spots?
  - what is the joint FPR (honest-hetero false positive) at a given TPR?
  - how does joint compare to each alone?

FPR uses honest heterogeneous pairs (left vs right stack, same prompt). TPR
uses each attack family (scale, sign-balanced, balanced-channel, replay, ...).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN, PAIRS
from radial import sign_radial_stat, sign_radial
from baselines import baseline_detect, calibrate_proj_delta
from p1a_sign_balanced import sign_balanced_attack
from attacks import (
    inject_scale, inject_per_channel_scale,
    inject_stale, inject_partial_replay, inject_layer_skip,
)

PAIR = "A/B"
Q = 256
SEED = 1
CKPTS = ["C1", "C2", "C3"]


def load():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    return Lc, Rc, Le, Re, sorted(set(Le) & set(Re))


def srr_scores(cand, ref, gamma_map):
    """Per-prompt max SignRadial score across checkpoints (raw, no threshold)."""
    mx = 0.0
    for ck in CKPTS:
        P, B = sign_radial_stat(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], SEED, n=Q)
        # raw score (unnormalized by gamma)
        mx = max(mx, abs(P) / (B + 1e-12))
    return mx


def proj_gap(cand, ref, sd4):
    """Max checkpoint projcos mean-gap (raw score for ROC, no threshold)."""
    import sys as _s
    _s.path.insert(0, "/Users/siyuan/Developer/ndss2027/reproduction/VeriEdge/workspace/sanity_20260727/frozen_snapshot/artifacts/thc/src")
    import hash_chain as hc
    from baselines import _ckpts
    cfg = hc.HashConfig(mode="tstc_projcos", seed_base=SEED, delta_map=dict(sd4),
                        prefill_token_samples=16, prefill_projection_dim=4,
                        decode_channel_samples=1, projection_seed=911)
    lc = hc.compute_hash_chain(_ckpts(cand), list(CKPTS), "prefill", cfg)
    rc = hc.compute_hash_chain(_ckpts(ref), list(CKPTS), "prefill", cfg)
    mx = 0.0
    for i, ck in enumerate(CKPTS):
        li = lc[i]["token_idx"]; ri = rc[i]["token_idx"]
        ls = lc[i]["summary"]; rs = rc[i]["summary"]
        if li.shape == ri.shape and np.array_equal(li, ri) and ls.shape == rs.shape:
            denom = np.maximum(np.linalg.norm(ls, axis=1) * np.linalg.norm(rs, axis=1), 1e-12)
            g = float(np.mean(1.0 - np.sum(ls * rs, axis=1) / denom))
        else:
            g = 1.0
        mx = max(mx, g)
    return mx


def main():
    Lc, Rc, Le, Re, eval_ids = load()
    n = len(eval_ids)

    # SignRadial gamma map (for reference, but we use raw scores for ROC)
    # ProjCos calibrated delta (for gap scores)
    from baselines import calibrate_proj_delta
    d4 = calibrate_proj_delta(Lc, Rc, 99.0, 16, 4, 911, SEED, "tstc_projcos")
    sd4 = {"prefill": {c: d4["prefill"][c] * 1.5 for c in CKPTS}}

    # --- build score arrays ---
    # honest (FPR): left vs right same prompt
    hon_srr = np.array([srr_scores(Re[pid], Le[pid], None) for pid in eval_ids])
    hon_proj = np.array([proj_gap(Re[pid], Le[pid], sd4) for pid in eval_ids])

    # attack families -> (label, cand_fn)
    attacks = {
        "scale_1.10": lambda b: inject_scale(b, 0.10),
        "scale_1.20": lambda b: inject_scale(b, 0.20),
        "sign_balanced": lambda b: sign_balanced_attack(b, 0.5, SEED)[0],
        "balanced_channel": lambda b: inject_per_channel_scale(b, 1.2, 0.8, SEED),
        "stale": lambda b: inject_stale(b, Re["eval_002"]),
        "partial_25": lambda b: inject_partial_replay(b, Re["eval_002"], 0.25, SEED),
        "layer_skip": lambda b: inject_layer_skip(b),
    }
    atk = {}
    for name, fn in attacks.items():
        atk[name] = {
            "srr": np.array([srr_scores(fn(Re[pid]), Re[pid], None) for pid in eval_ids]),
            "proj": np.array([proj_gap(fn(Re[pid]), Re[pid], sd4) for pid in eval_ids]),
        }

    # --- ROC over threshold grid on max of (srr/p99_gamma, proj/thresh) ---
    # Normalize each to a "relative threshold" scale for joint sweep.
    # Use sign-radial p99 gamma and proj p99 as the 1.0 reference.
    srr_p99 = float(np.percentile(hon_srr, 99))
    proj_p99 = float(np.percentile(hon_proj, 99))

    print("=== Joint OR-gate ROC (SignRadial OR ProjCos) ===")
    print(f"honest srr p99 = {srr_p99:.4f}, honest proj p99 = {proj_p99:.4f}")
    print(f"{( 'mult'):>6s} {'srr_thr':>8s} {'proj_thr':>8s} {'jointFPR':>9s} {'scaleTPR':>9s} {'signbalTPR':>10s} {'balchnTPR':>9s} {'staleTPR':>8s} {'partialTPR':>10s} {'layerTPR':>8s}")

    for mult in [0.5, 0.7, 1.0, 1.3, 1.5, 2.0, 3.0, 4.0]:
        ts = srr_p99 * mult
        tp = proj_p99 * mult
        def joint(srr_s, proj_s):
            return (srr_s > ts) | (proj_s > tp)
        fpr = float(np.mean(joint(hon_srr, hon_proj)))
        cells = [fpr]
        for name in ["scale_1.10", "sign_balanced", "balanced_channel", "stale", "partial_25", "layer_skip"]:
            cells.append(float(np.mean(joint(atk[name]["srr"], atk[name]["proj"]))))
        print(f"  {mult:>6.2f} {ts:>8.4f} {tp:>8.4f} " + " ".join(f"{c:>9.3f}" for c in cells))

    print()
    print("Columns after jointFPR: scale1.1, signbalanced, balancedchannel, stale, partial25, layerskip TPR")


if __name__ == "__main__":
    main()
