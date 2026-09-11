"""Combined fast synthetic experiments: P2b, P2b2, P3b, P5a.

- P2b  : balanced per-channel scaling (alpha ~ {0.8, 1.2}) — SignRadial's hard case
- P2b2 : per-token scaling (different alpha per token)
- P3b  : partial replay (10..100% tokens from a previous prompt)
- P5a  : layer-wise robustness — honest SignRadial p99 at C1/C2/C3, is a global
         threshold feasible?

All run on existing captures (synthetic injection), no model inference.
SignRadial uses q=256 (the robust default), calibrated per checkpoint on the
40 calib prompts, threshold = p99 x scale_mult.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_srr_offline import load_split, MAIN, PAIRS
from radial import sign_radial, sign_radial_stat
from attacks import inject_scale, inject_per_channel_scale, inject_per_token_scale, inject_partial_replay
from baselines import baseline_detect, calibrate_proj_delta

Q = 256
PCTL = 99.0
SC = 3.0
SEED = 1
CKPTS = ["C1", "C2", "C3"]
PAIR = "A/B"


def setup():
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re))

    def calib_gamma(ck):
        ratios = []
        for pid in sorted(set(Lc) & set(Rc)):
            P, B = sign_radial_stat(Lc[pid][f"prefill__{ck}"], Rc[pid][f"prefill__{ck}"], SEED, n=Q)
            ratios.append(abs(P) / (B + 1e-12))
        return float(np.percentile(ratios, PCTL))

    gm = {c: calib_gamma(c) * SC for c in CKPTS}

    def srr_det(cand, ref):
        for ck in CKPTS:
            a, _, _, _ = sign_radial(cand[f"prefill__{ck}"], ref[f"prefill__{ck}"], SEED, n=Q, gamma=gm[ck])
            if a:
                return True
        return False

    # projcos4 for complement checks
    d4 = calibrate_proj_delta(Lc, Rc, 99.0, 16, 4, 911, SEED, "tstc_projcos")
    sd4 = {"prefill": {c: d4["prefill"][c] * 1.5 for c in CKPTS}}

    def pc_det(cand, ref):
        ok, _ = baseline_detect("projcos4", cand, ref, SEED, sd4, 16, 0, 4, 911, "tstc_projcos")
        return ok

    return Re, eval_ids, srr_det, pc_det


def tpr(det, cand_fn, refs, ids):
    return sum(1 for pid in ids if det(cand_fn(refs[pid]), refs[pid])) / len(ids)


def main():
    Re, ids, srr, pc = setup()
    n = len(ids)
    print(f"=== SignRadial fast synthetic experiments ({PAIR}, q={Q}, p{PCTL}x{SC}) ===")

    print("\n--- P2b: balanced per-channel scaling (half up, half down) ---")
    print(f"{'alpha_up/dn':16s} {'SignRadial':>11s} {'ProjCos4':>9s}")
    for au, ad in [(1.1, 0.9), (1.2, 0.8), (1.3, 0.7), (1.5, 0.5)]:
        s = tpr(srr, lambda b: inject_per_channel_scale(b, au, ad, SEED), Re, ids)
        p = tpr(pc, lambda b: inject_per_channel_scale(b, au, ad, SEED), Re, ids)
        print(f"  {au:.1f}/{ad:.1f}:      {s:>11.3f} {p:>9.3f}")

    print("\n--- P2b2: per-token scaling (alternating alpha) ---")
    for amp in [0.1, 0.2, 0.3]:
        s = tpr(srr, lambda b: inject_per_token_scale(b, [1 + amp if i % 2 == 0 else 1 - amp for i in range(32)], "C2"), Re, ids)
        p = tpr(pc, lambda b: inject_per_token_scale(b, [1 + amp if i % 2 == 0 else 1 - amp for i in range(32)], "C2"), Re, ids)
        print(f"  amp={amp:.1f} (alt tokens): SignRadial={s:.3f} ProjCos4={p:.3f}")

    print("\n--- P3b: partial replay (p_replay fraction of tokens from prev prompt) ---")
    print(f"{'p_replay':10s} {'SignRadial':>11s} {'ProjCos4':>9s}")
    for pr in [0.1, 0.25, 0.5, 0.75, 1.0]:
        s = tpr(srr, lambda b: inject_partial_replay(b, Re["eval_002"], pr, SEED), Re, ids)
        p = tpr(pc, lambda b: inject_partial_replay(b, Re["eval_002"], pr, SEED), Re, ids)
        print(f"  {pr:<10.2f} {s:>11.3f} {p:>9.3f}")

    print("\n--- P5a: layer-wise honest SignRadial p99 (global threshold feasibility) ---")
    pcfg = PAIRS[PAIR]
    base = pcfg["base"]
    Lc = load_split(base, pcfg["left_calib"])
    Rc = load_split(base, pcfg["right_calib"])
    Le = load_split(base, pcfg["left_eval"])
    Re_ = load_split(base, pcfg["right_eval"])
    eval_ids = sorted(set(Le) & set(Re_))
    for ck in CKPTS:
        hon = []
        for pid in eval_ids:
            P, B = sign_radial_stat(Le[pid][f"prefill__{ck}"], Re_[pid][f"prefill__{ck}"], SEED, n=Q)
            hon.append(abs(P) / (B + 1e-12))
        h = np.array(hon)
        print(f"  {ck}: honest p50={np.percentile(h,50):.4f} p90={np.percentile(h,90):.4f} p99={np.percentile(h,99):.4f} max={h.max():.4f}")
    print("  -> if p99 differs a lot across layers, a single global gamma is risky; per-layer is safer.")


if __name__ == "__main__":
    main()
